"""面试 prep 逐字稿评测 runner（T-EVAL-2 B2）。

在 ``prep_cases.jsonl`` 上驱动 prep 链（``_build_interview_prompt`` →
``InterviewPrepAgent``），绕过 DB，执行 L1 结构合规 + L2 LLM-as-judge。

用法::

    # 跑全部 case（需已配置 Zhipu API key 与 .env）
    python -m evaluation.run_prep_eval

    # 只跑指定 case
    python -m evaluation.run_prep_eval --case-id prep_synth_01

    # 只跑 L1（零 LLM 成本，CI 用）
    python -m evaluation.run_prep_eval --l1-only

设计说明：
- prep workflow 的 ``_generate_prep`` 强依赖 DB（读 job_analysis / cards / 写 interview_preps）。
  评测路径复用纯函数 ``interview_pre._build_interview_prompt``（接受 cards / dimension_requirements
  作为 dict 参数），自行组装 prompt 并直接调用 ``InterviewPrepAgent``，不触发任何 DB 读写。
- 裁判模型默认 ``glm-4.7``（付费），可通过 ``JC_EVAL_JUDGE_MODEL`` 覆盖。
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.tools.llm_json import register_usage_observer
from evaluation.datasets import load_cases
from evaluation.surface_schemas import (
    JudgeScore,
    check_prep_l1,
    summarize_l1,
)

logger = logging.getLogger("jobcraft.evaluation.prep")

DEFAULT_DATASET = Path(__file__).parent / "datasets" / "prep_cases.jsonl"
DEFAULT_OUT_DIR = Path(__file__).parent / "results"

JUDGE_PROMPT_PATH = Path(__file__).parent / "prompts" / "judge_prep_v1.md"
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


def _build_prompt_from_case(case: dict[str, Any]) -> str:
    """从 prep case 构建逐字稿 prompt（纯函数，无 DB）。

    :param case: prep case dict
    :return: 完整 prompt 字符串
    """
    from app.tools.interview_pre import _build_interview_prompt

    return _build_interview_prompt(
        round_type=case.get("round_type", "技术面"),
        position=case.get("position", ""),
        company=case.get("company", ""),
        jd_text=case.get("jd_text", ""),
        cards=case.get("cards", []),
        dimension_requirements=case.get("dimension_requirements", []),
        card_versions=None,
        company_research=None,
        resume_markdown=None,
        previous_review_summary=None,
    )


def _run_prep_chain(case: dict[str, Any]) -> dict[str, Any]:
    """驱动 InterviewPrepAgent 生成逐字稿（绕过 DB）。

    :param case: prep case dict
    :return: InterviewPrepResult dict
    """
    from app.agents.interview_prep_agent import InterviewPrepAgent
    from app.tools.interview_pre import INTERVIEW_PREP_PROMPT_VERSION

    prompt = _build_prompt_from_case(case)
    out = InterviewPrepAgent().run(
        {
            "prompt": prompt,
            "prompt_version": str(INTERVIEW_PREP_PROMPT_VERSION),
        }
    )
    return out["prep_result"]


def _build_judge_prompt(case: dict[str, Any], result: dict[str, Any]) -> str:
    """构建 L2 裁判 prompt（prep 链）。

    :param case: 评测 case
    :param result: 待评审的 prep 结果 dict
    :return: 完整裁判 prompt
    """
    judge_rubric = JUDGE_PROMPT_PATH.read_text(encoding="utf-8")

    dq_summary = "\n".join(
        f"{dq.get('dimension')}: {dq.get('question')} → "
        f"要点={dq.get('answer_points')} cards={dq.get('card_ids')}"
        for dq in result.get("dimension_questions", [])
    )

    return (
        f"{judge_rubric}\n\n"
        f"## 输入材料\n"
        f"岗位：{case.get('position', '')} / 公司：{case.get('company', '')} / "
        f"轮次：{case.get('round_type', '')}\n"
        f"JD：\n{case.get('jd_text', '')[:800]}\n\n"
        f"经历卡：\n"
        + "\n".join(
            f"- {c.get('title')}: {c.get('summary')}" for c in case.get("cards", [])
        )
        + "\n\n"
        f"维度要求：{case.get('dimension_requirements', [])}\n\n"
        f"## 待评审的 AI 输出\n"
        f"elevator_pitch:\n{result.get('elevator_pitch', '')[:600]}\n\n"
        f"dimension_questions:\n{dq_summary[:2000]}\n\n"
        f"full_version（前 2000 字）:\n{result.get('full_version', '')[:2000]}\n\n"
        f"请按 JudgeScore schema 输出 JSON。"
    )


def _judge(
    case: dict[str, Any], result: dict[str, Any], judge_model: Any
) -> JudgeScore:
    """调用裁判模型对单条 prep 结果打分（L2）。

    :param case: 评测 case
    :param result: prep 结果 dict
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
        debug_label="judge_prep",
        prompt_version=JUDGE_PROMPT_VERSION,
    )


def run_eval(
    dataset_path: Path | None = None,
    case_id: str | None = None,
    l1_only: bool = False,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """执行 prep 链评测主流程。

    :param dataset_path: 数据集路径，缺省 ``prep_cases.jsonl``
    :param case_id: 只跑指定 case
    :param l1_only: 只跑 L1（零 LLM 成本）
    :param out_dir: 结果输出目录
    :return: 评测报告 dict
    """
    path = dataset_path or DEFAULT_DATASET
    cases = load_cases(path)
    if case_id:
        cases = [c for c in cases if c.get("case_id") == case_id]
        if not cases:
            raise ValueError(f"case_id={case_id} 不在 {path}")

    out = out_dir or DEFAULT_OUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    usage = UsageCollector()
    register_usage_observer(usage)

    judge_model = None
    if not l1_only:
        from app.core.llm import init_chat_model
        import os

        judge_model = init_chat_model(
            model=os.getenv("JC_EVAL_JUDGE_MODEL", "glm-4.7"),
            model_provider="openai",
            # 必须显式传 timeout：langchain 传 None 会禁用 openai SDK 默认超时，
            # 上游挂起连接将无限阻塞评测进程
            timeout=float(os.getenv("LLM_REQUEST_TIMEOUT", "180")),
        )

    all_findings = []
    judge_scores: list[dict[str, Any]] = []
    per_case: list[dict[str, Any]] = []

    for case in cases:
        cid = case.get("case_id", "?")
        t0 = time.perf_counter()
        try:
            result = _run_prep_chain(case)
        except Exception as exc:
            logger.error("case %s 执行失败: %s", cid, exc)
            per_case.append({"case_id": cid, "error": str(exc)})
            continue

        # L1
        findings = check_prep_l1(cid, result)
        all_findings.extend(findings)
        l1_report = summarize_l1(findings)

        entry: dict[str, Any] = {
            "case_id": cid,
            "l1": l1_report,
            "n_dimension_questions": len(result.get("dimension_questions", [])),
            "elevator_pitch_len": len(result.get("elevator_pitch", "")),
            "full_version_len": len(result.get("full_version", "")),
            "elapsed_s": round(time.perf_counter() - t0, 2),
        }

        # L2
        if not l1_only and judge_model is not None:
            try:
                js = _judge(case, result, judge_model)
                entry["judge"] = js.model_dump()
                judge_scores.append(js.model_dump())
            except Exception as exc:
                logger.error("case %s 裁判失败: %s", cid, exc)
                entry["judge_error"] = str(exc)

        per_case.append(entry)

    # 汇总
    l1_total = summarize_l1(all_findings)
    judge_agg: dict[str, Any] = {}
    if judge_scores:
        n = len(judge_scores)
        for key in ("accuracy", "completeness", "actionability", "safety", "overall"):
            judge_agg[f"{key}_mean"] = round(sum(s[key] for s in judge_scores) / n, 3)

    report = {
        "chain": "prep",
        "dataset": str(path),
        "n_cases": len(cases),
        "l1_only": l1_only,
        "l1_summary": l1_total,
        "judge_summary": judge_agg,
        "usage": usage.snapshot(),
        "per_case": per_case,
    }

    out_file = out / "surface_prep_report.json"
    out_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("报告已写入 %s", out_file)
    return report


def main() -> None:
    """CLI 入口。"""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(description="面试 prep 逐字稿评测 runner")
    p.add_argument("--dataset", type=Path, default=None)
    p.add_argument("--case-id", default=None)
    p.add_argument("--l1-only", action="store_true")
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args()
    report = run_eval(
        dataset_path=args.dataset,
        case_id=args.case_id,
        l1_only=args.l1_only,
        out_dir=args.out_dir,
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
