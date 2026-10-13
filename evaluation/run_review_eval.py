"""复盘链评测 runner（T-EVAL-2 B1）。

在 ``review_cases.jsonl`` 上驱动完整复盘链（Router → Tech/Soft → Gate → assemble），
绕过 DB（不调用 db_tools），执行 L1 结构合规 + L2 LLM-as-judge。

用法::

    # 跑全部 case（需已配置 Zhipu API key 与 .env）
    python -m evaluation.run_review_eval

    # 只跑指定 case
    python -m evaluation.run_review_eval --case-id rev_synth_01

    # 只跑 L1（跳过 L2 裁判，链本身仍需 LLM）
    python -m evaluation.run_review_eval --l1-only

设计说明（evaluation-design-v1.md §runner）：
- 复盘 workflow 的 ``_load_data`` 与 ``_assemble_result`` 强依赖 DB（读记录 + 写分析）。
  评测路径复用纯函数层（``_parse_dialogue`` / ``_build_qa_pairs`` / ``_format_cards_for_prompt``），
  自行组装 state 并直接驱动 4 个 Agent，不触发任何 DB 读写。
- 裁判模型默认 ``glm-4.7``（付费），可通过 ``JC_EVAL_JUDGE_MODEL`` 覆盖。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.tools.llm_json import register_usage_observer
from evaluation.datasets import load_cases
from evaluation.surface_schemas import (
    JudgeScore,
    check_review_l1,
    summarize_l1,
)

logger = logging.getLogger("jobcraft.evaluation.review")

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "review_cases.jsonl"
DEFAULT_OUT_DIR = Path(__file__).parent / "results"

# 裁判 prompt 路径（版本化，AGENTS §7）
JUDGE_PROMPT_PATH = Path(__file__).parent / "prompts" / "judge_review_v1.md"
JUDGE_PROMPT_VERSION = "1"


class UsageCollector:
    """从 llm_json observer 采集单次运行内的调用次数、耗时与 token 用量。"""

    def __init__(self) -> None:
        self.calls = 0
        self.calls_cached = 0
        self.duration_s = 0.0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def __call__(self, info: dict[str, Any]) -> None:
        if info.get("from_cache"):
            self.calls_cached += 1
            return
        self.calls += 1
        self.duration_s += float(info.get("duration_s") or 0.0)
        self.prompt_tokens += int(info.get("prompt_tokens") or 0)
        self.completion_tokens += int(info.get("completion_tokens") or 0)

    def snapshot(self) -> dict[str, Any]:
        """汇总采样结果。"""
        return {
            "llm_calls": self.calls,
            "llm_calls_cached": self.calls_cached,
            "duration_s": round(self.duration_s, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }


def _build_state_from_case(case: dict[str, Any]) -> dict[str, Any]:
    """从评测 case 构建复盘 workflow 初始 state（绕过 DB）。

    :param case: review case dict（含 raw_text / jd_text / cards / company / position / round_type）
    :return: 与 InterviewReviewState 兼容的 state dict
    """
    from app.tools.interview_review import (
        _build_qa_pairs,
        _format_cards_for_prompt,
        _parse_dialogue,
    )

    raw_text = case.get("raw_text", "")
    dialogue = _parse_dialogue(raw_text)
    all_qa_pairs = _build_qa_pairs(dialogue)
    if not all_qa_pairs:
        raise ValueError(f"case {case.get('case_id')} 未识别到任何面试官问题")

    # 默认选中全部问题
    selected_sequences = [qa["sequence"] for qa in all_qa_pairs]
    selected_set = set(selected_sequences)
    selected_qa_pairs = [qa for qa in all_qa_pairs if qa["sequence"] in selected_set]

    cards = case.get("cards", [])
    cards_text = _format_cards_for_prompt(cards, max_cards=5)

    return {
        "record_id": 0,
        "user_id": 0,
        "selected_sequences": selected_sequences,
        "record": {},
        "dialogue": dialogue,
        "all_qa_pairs": all_qa_pairs,
        "selected_qa_pairs": selected_qa_pairs,
        "job_context": {"cards": cards},
        "jd_text": case.get("jd_text", ""),
        "cards_text": cards_text,
        "company": case.get("company", ""),
        "position": case.get("position", ""),
        "round_type": case.get("round_type", ""),
        "classified": {},
        "tech_results": [],
        "soft_results": [],
        "gate_report": {},
        "result": None,
    }


def _assemble_offline(state: dict[str, Any], case_id: str) -> dict[str, Any]:
    """离线组装复盘结果（复刻 ``_assemble_result`` 的非 DB 部分）。

    :param state: 已填充 tech/soft/gate 的 state
    :param case_id: case 标识（用于 record_id 占位）
    :return: InterviewReviewResult dict
    """
    from app.schemas.jobcraft import InterviewReviewResult, ReviewedQuestion

    all_qa_pairs = state["all_qa_pairs"]
    selected_set = set(state["selected_sequences"])
    job_context = state["job_context"]

    analysis_by_seq: dict[int, dict[str, Any]] = {}
    for item in state.get("tech_results", []) or []:
        analysis_by_seq[item["sequence"]] = item
    for item in state.get("soft_results", []) or []:
        analysis_by_seq[item["sequence"]] = item

    valid_card_ids = {c["id"] for c in job_context.get("cards", [])}
    card_title_map = {c["id"]: c.get("title", "") for c in job_context.get("cards", [])}

    scores = [a["score"] for a in analysis_by_seq.values() if a.get("score")]
    overall_score = round(sum(scores) / len(scores)) if scores else 0

    questions = []
    for qa in all_qa_pairs:
        seq = qa["sequence"]
        is_selected = seq in selected_set
        analysis = analysis_by_seq.get(seq, {}) if is_selected else {}

        expected = analysis.get("expected_answer", "")
        if isinstance(expected, list):
            expected = "；".join(str(e) for e in expected)

        rid = analysis.get("related_card_id")
        related_card_title = ""
        if rid in valid_card_ids:
            related_card_title = card_title_map.get(rid, "")
        else:
            rid = None

        q_data = {
            "sequence": seq,
            "start_time": qa.get("start_time", ""),
            "speaker": qa.get("speaker", ""),
            "question_text": qa.get("question_text", ""),
            "dimension": analysis.get("dimension", "D7 协作沟通"),
            "level": analysis.get("level", "L3"),
            "intent": analysis.get("intent", ""),
            "expected_answer": expected,
            "my_answer": qa.get("my_answer", ""),
            "score": analysis.get("score", 0) if is_selected else 0,
            "feedback": analysis.get("feedback", []) if is_selected else [],
            "suggestions": analysis.get("suggestions", []) if is_selected else [],
            "related_card_id": rid,
            "related_card_title": related_card_title,
        }
        questions.append(ReviewedQuestion(**q_data))

    strengths, weaknesses, action_items = [], [], []
    for a in analysis_by_seq.values():
        score = a.get("score") or 0
        dim = a.get("dimension", "")
        if score >= 80 and dim:
            strengths.append(f"{dim} 回答表现良好（{score}分）")
        if a.get("feedback"):
            weaknesses.extend(a["feedback"][:1])
        if a.get("suggestions"):
            action_items.extend(a["suggestions"][:1])
    strengths = strengths or ["等待评估"]
    weaknesses = weaknesses or ["等待评估"]
    action_items = action_items or ["等待评估"]

    result = InterviewReviewResult(
        record_id=0,
        user_id=0,
        title=f"{state.get('company', '')}-{state.get('position', '')}",
        company=state.get("company", ""),
        position=state.get("position", ""),
        round_type=state.get("round_type", ""),
        overall_score=overall_score,
        summary="",
        strengths=strengths[:3],
        weaknesses=weaknesses[:3],
        action_items=action_items[:3],
        questions=questions,
    )
    _ = case_id  # 占位，当前未使用；保留签名兼容未来按 case 追踪
    return result.model_dump()


def _run_review_chain(state: dict[str, Any]) -> dict[str, Any]:
    """直接驱动 4 个 Agent 完成复盘链（绕过 DB）。

    :param state: 初始 state（含 selected_qa_pairs / cards_text 等）
    :return: 填充了 classified/tech/soft/gate/result 的 state
    """
    from app.agents.gate_agent import GateAgent
    from app.agents.router_agent import RouterAgent
    from app.agents.soft_analyzer import SoftAnalyzer
    from app.agents.tech_analyzer import TechAnalyzer

    # Router
    router_out = RouterAgent().run(state)
    state.update(router_out)

    # Tech / Soft（条件执行）
    classified = state.get("classified", {})
    if classified.get("tech"):
        state.update(TechAnalyzer().run(state))
    if classified.get("soft"):
        state.update(SoftAnalyzer().run(state))

    # Gate
    state.update(GateAgent().run(state))

    # Assemble
    state["result"] = _assemble_offline(state, case_id="")
    return state


def _build_judge_prompt(case: dict[str, Any], result: dict[str, Any]) -> str:
    """构建 L2 裁判 prompt（复盘链）。

    :param case: 评测 case
    :param result: 待评审的复盘结果 dict
    :return: 完整裁判 prompt
    """
    judge_rubric = JUDGE_PROMPT_PATH.read_text(encoding="utf-8")

    qa_summary = "\n".join(
        f"Q{q['sequence']}: {q.get('question_text', '')}\n"
        f"A{q['sequence']}: {q.get('my_answer', '')}"
        for q in result.get("questions", [])
    )

    output_summary = "\n".join(
        f"Q{q['sequence']} dim={q.get('dimension')} level={q.get('level')} "
        f"score={q.get('score')} intent={q.get('intent')} "
        f"expected={str(q.get('expected_answer'))[:200]} "
        f"feedback={q.get('feedback')} suggestions={q.get('suggestions')}"
        for q in result.get("questions", [])
    )

    return (
        f"{judge_rubric}\n\n"
        f"## 输入材料\n"
        f"岗位：{case.get('position', '')} / 公司：{case.get('company', '')} / "
        f"轮次：{case.get('round_type', '')}\n"
        f"JD：\n{case.get('jd_text', '')[:800]}\n\n"
        f"逐字稿（摘要）：\n{qa_summary[:2000]}\n\n"
        f"## 待评审的 AI 输出\n"
        f"overall_score={result.get('overall_score')} "
        f"strengths={result.get('strengths')} "
        f"weaknesses={result.get('weaknesses')} "
        f"action_items={result.get('action_items')}\n\n"
        f"逐题分析：\n{output_summary[:3000]}\n\n"
        f"请按 JudgeScore schema 输出 JSON。"
    )


def _judge(
    case: dict[str, Any], result: dict[str, Any], judge_model: Any
) -> JudgeScore:
    """调用裁判模型对单条复盘结果打分（L2）。

    :param case: 评测 case
    :param result: 复盘结果 dict
    :param judge_model: 裁判 LLM 实例（GLM-4.7）
    :return: JudgeScore 实例
    """
    from app.tools.llm_json import invoke_structured

    prompt = _build_judge_prompt(case, result)
    return invoke_structured(
        judge_model,
        JudgeScore,
        prompt,
        temperature=0.0,
        debug_label="judge_review",
        prompt_version=JUDGE_PROMPT_VERSION,
    )


def run_eval(
    dataset_path: Path | None = None,
    case_id: str | list[str] | None = None,
    l1_only: bool = False,
    out_dir: Path | None = None,
    case_retries: int = 0,
    case_retry_wait: float = 60.0,
    judge_retries: int = 0,
    judge_retry_wait: float = 30.0,
) -> dict[str, Any]:
    """执行复盘链评测主流程。

    :param dataset_path: 数据集路径，缺省 ``review_cases.jsonl``
    :param case_id: 只跑指定 case（单个 id 或 id 列表）
    :param l1_only: 只跳过 L2 裁判（链本身仍执行）
    :param out_dir: 结果输出目录，缺省 ``evaluation/results``
    :param case_retries: 链执行失败（含 429 限流）后整 case 重试次数
    :param case_retry_wait: case 重试基础间隔秒数（按 2^n 递增）
    :param judge_retries: 裁判失败后重试次数
    :param judge_retry_wait: 裁判重试基础间隔秒数（按 2^n 递增）
    :return: 评测报告 dict
    """
    path = dataset_path or DEFAULT_DATASET
    cases = load_cases(path)
    if case_id:
        wanted = {case_id} if isinstance(case_id, str) else set(case_id)
        cases = [c for c in cases if c.get("case_id") in wanted]
        if not cases:
            raise ValueError(f"case_id={sorted(wanted)} 不在 {path}")

    out = out_dir or DEFAULT_OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    usage = UsageCollector()
    register_usage_observer(usage)

    judge_model = None
    if not l1_only:
        from app.core.llm import init_chat_model

        judge_model = init_chat_model(
            model=os.getenv("JC_EVAL_JUDGE_MODEL", "glm-4.7"),
            model_provider="openai",
            # 必须显式传 timeout：langchain 传 None 会禁用 openai SDK 默认超时，
            # 上游挂起连接（accept 后不回包）将无限阻塞评测进程
            timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "180")),
        )

    all_findings = []
    judge_scores: list[dict[str, Any]] = []
    per_case: list[dict[str, Any]] = []
    out_file = out / "surface_review_report.json"

    def _flush() -> dict[str, Any]:
        """构建并落盘当前进度报告（逐 case 写，中断可保留已完成结果）。"""
        report = _make_report(
            path=path,
            n_cases=len(cases),
            l1_only=l1_only,
            all_findings=all_findings,
            judge_scores=judge_scores,
            usage=usage,
            per_case=per_case,
        )
        out_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report

    for case in cases:
        cid = case.get("case_id", "?")
        t0 = time.perf_counter()

        # 链执行（带限流重试：整 case 重启，已完成步骤视缓存可用性可能复用）
        result: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in range(case_retries + 1):
            try:
                state = _build_state_from_case(case)
                state = _run_review_chain(state)
                result = state["result"]
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                logger.error(
                    "case %s 执行失败（%d/%d）: %s",
                    cid,
                    attempt + 1,
                    case_retries + 1,
                    exc,
                )
                if attempt < case_retries:
                    wait = case_retry_wait * (2**attempt)
                    logger.warning("case %s 链 %.0fs 后重试", cid, wait)
                    time.sleep(wait)

        if result is None:
            per_case.append({"case_id": cid, "error": str(last_exc)})
            _flush()
            continue

        # L1
        findings = check_review_l1(cid, result)
        all_findings.extend(findings)
        l1_report = summarize_l1(findings)

        entry: dict[str, Any] = {
            "case_id": cid,
            "l1": l1_report,
            "overall_score": result.get("overall_score"),
            "n_questions": len(result.get("questions", [])),
            "elapsed_s": round(time.perf_counter() - t0, 2),
        }
        # 链成功即落盘（judge 可能因限流/连接挂起丢失，不拖累链结果）
        per_case.append(entry)
        _flush()

        # L2（带限流重试）
        if not l1_only and judge_model is not None:
            for j_attempt in range(judge_retries + 1):
                try:
                    js = _judge(case, result, judge_model)
                    entry["judge"] = js.model_dump()
                    judge_scores.append(js.model_dump())
                    break
                except Exception as exc:
                    logger.error(
                        "case %s 裁判失败（%d/%d）: %s",
                        cid,
                        j_attempt + 1,
                        judge_retries + 1,
                        exc,
                    )
                    if j_attempt < judge_retries:
                        wait = judge_retry_wait * (2**j_attempt)
                        logger.warning("case %s 裁判 %.0fs 后重试", cid, wait)
                        time.sleep(wait)
                    else:
                        entry["judge_error"] = str(exc)

        # judge 结果回写该 case 条目并再次落盘
        _flush()

    report = _flush()
    logger.info("报告已写入 %s", out_file)
    return report


def _make_report(
    *,
    path: Path,
    n_cases: int,
    l1_only: bool,
    all_findings: list[Any],
    judge_scores: list[dict[str, Any]],
    usage: UsageCollector,
    per_case: list[dict[str, Any]],
) -> dict[str, Any]:
    """汇总当前累积状态为完整报告 dict。

    :param path: 数据集路径
    :param n_cases: 本次运行的 case 总数
    :param l1_only: 是否只跑 L1
    :param all_findings: 累积的 L1 findings
    :param judge_scores: 累积的裁判打分
    :param usage: 用量采集器
    :param per_case: 逐 case 结果
    :return: 报告 dict
    """
    l1_total = summarize_l1(all_findings)
    judge_agg: dict[str, Any] = {}
    if judge_scores:
        n = len(judge_scores)
        for key in ("accuracy", "completeness", "actionability", "safety", "overall"):
            judge_agg[f"{key}_mean"] = round(sum(s[key] for s in judge_scores) / n, 3)

    return {
        "chain": "review",
        "dataset": str(path),
        "n_cases": n_cases,
        "l1_only": l1_only,
        "chain_model": os.getenv("LLM_model"),
        "judge_model": (
            os.getenv("JC_EVAL_JUDGE_MODEL", "glm-4.7") if not l1_only else None
        ),
        "l1_summary": l1_total,
        "judge_summary": judge_agg,
        "usage": usage.snapshot(),
        "per_case": per_case,
    }


def main() -> None:
    """CLI 入口。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="复盘链评测 runner")
    p.add_argument("--dataset", type=Path, default=None)
    p.add_argument("--case-id", nargs="+", default=None, help="只跑指定 case（可多个）")
    # 只跑 L1（跳过 L2 裁判；链本身仍需 LLM）
    p.add_argument("--l1-only", action="store_true")
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument(
        "--case-retries", type=int, default=0, help="链失败（含429）后整 case 重试次数"
    )
    p.add_argument(
        "--case-retry-wait",
        type=float,
        default=60.0,
        help="case 重试基础间隔（秒，2^n 递增）",
    )
    p.add_argument("--judge-retries", type=int, default=0, help="裁判失败后重试次数")
    p.add_argument(
        "--judge-retry-wait",
        type=float,
        default=30.0,
        help="裁判重试基础间隔（秒，2^n 递增）",
    )
    args = p.parse_args()
    report = run_eval(
        dataset_path=args.dataset,
        case_id=args.case_id,
        l1_only=args.l1_only,
        out_dir=args.out_dir,
        case_retries=args.case_retries,
        case_retry_wait=args.case_retry_wait,
        judge_retries=args.judge_retries,
        judge_retry_wait=args.judge_retry_wait,
    )
    print(
        json.dumps(
            {
                "n_cases": report["n_cases"],
                "l1_pass_rate": report["l1_summary"]["pass_rate"],
                "judge_summary": report["judge_summary"],
                "usage": report["usage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
