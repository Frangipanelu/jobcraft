"""Pipeline 分层评测（无 LLM · 确定性基线）。

v0.5 §二十六 落地。给定 40 条 gold 语料，仅跑确定性 L1 管道
（jd_structurer → jd_classifier → jd_extractor → 空 inference merge），
产出分层基线：

- L1-Structurer：区块命中、item span 完整（切片==原文、零失配）；
- L1-Classifier：UNKNOWN 占比、bucket 相对规模；
- L1-Extractor：gold token 近似命中（required/preferred/responsibilities）、
  education/years 覆盖、key_metrics 数量；
- ATS-Safety：合并后 ATSProfile 的值是否被 Evidence Span 支撑
  （EXACT/CONTAINED→accept，PARAPHRASE/INFERRED→review，UNSUPPORTED→reject）。

culture/D1-D8/subtext 属 L2（LLM），本层不评测（merge 时空 inference）。

用法：
    uv run python -m evaluation.run_pipeline_eval [数据集路径]
    缺省用 evaluation/datasets/jd_cases.jsonl（40 条 gold）；
    传 real_jd_cases.jsonl 即真实语料评测。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.agents.jd_ats_agent import merge_ats
from app.pipeline.evidence_builder import EvidenceRelation, grade_relation, to_verdict
from app.pipeline.jd_classifier import classify_jd
from app.pipeline.jd_extractor import extract_jd, normalize
from app.pipeline.jd_structurer import structure_jd
from app.schemas.jobcraft import AtsInference
from evaluation.datasets import load_cases

CASES = Path(__file__).parent / "datasets" / "jd_cases.jsonl"
REPORT = Path(__file__).parent / "reports" / "ats_pipeline_l1_report.md"


def _approx_hit(gold: str, skills: set[str]) -> bool:
    g = normalize(gold)
    if not g:
        return False
    return any(g in sk or (len(g) >= 4 and sk in g) for sk in skills)


def _supported(value: str, span: str) -> str:
    """单个输出值是否被某证据 span 支撑。

    先走 grade_relation 五级判定；对短 token（SQL/Go/K8s/LLM 等，子串含
    len>=4 规则照顾不到）额外做归一化子串包含兜底——L1 的值全部源自 span，
    此处主要用作幻觉监控而非语义打分。
    """
    rel = grade_relation(value, span)
    if rel is not EvidenceRelation.UNSUPPORTED:
        return to_verdict(rel)
    nv, ns = normalize(value), normalize(span)
    return "accept" if nv and nv in ns else "reject"


def _evidence_by_span_outputs(
    ats: dict[str, Any], span_texts: list[str]
) -> dict[str, int]:
    """统计每个列表输出值被证据 span 支撑的关系级别。"""
    counts = {"accept": 0, "review": 0, "reject": 0, "total": 0}
    for field in (
        "required_skills",
        "preferred_skills",
        "responsibilities",
        "soft_skills",
        "key_metrics",
    ):
        for value in ats.get(field, []):
            best = "reject"
            for span in span_texts:
                verdict = _supported(value, span)
                if verdict == "accept":
                    best = "accept"
                    break
                if verdict == "review" and best == "reject":
                    best = "review"
            counts[best] += 1
            counts["total"] += 1
    return counts


def run(cases_path: Path) -> tuple[dict[str, Any], int]:
    cases = load_cases(cases_path)
    stats = {
        "structurer": {"sections_hit": {}, "span_mismatch": 0},
        "classifier": {"unknown": 0, "items": 0},
        "extractor": {
            "required": [0, 0],
            "preferred": [0, 0],
            "responsibility": [0, 0],
            "education": 0,
            "years": 0,
            "metrics": 0,
            "keywords": {"high": 0, "medium": 0, "low": 0},
        },
        "safety": {"accept": 0, "review": 0, "reject": 0, "total": 0},
    }
    section_tracker: set[str] = set()
    for c in cases:
        jd = c["jd_text"]
        structured = structure_jd(jd)
        # L1-1 structurer
        if not structured.items:
            stats["structurer"]["span_mismatch"] += 1
            continue
        for item in structured.items:
            if jd[item.start : item.end] != item.text:
                stats["structurer"]["span_mismatch"] += 1
        section_tracker.update(item.section.value for item in structured.items)
        # L1-2 classifier buckets
        classified = classify_jd(structured)
        stats["classifier"]["items"] += len(classified)
        stats["classifier"]["unknown"] += sum(
            c.label.value == "unknown" for c in classified
        )
        # L1-3 extractor gold-hit
        extraction = extract_jd(structured, classified)
        ats = merge_ats(
            extraction, classified, AtsInference(job_title=""), jd
        ).model_dump()
        reqs = {normalize(x) for x in ats["required_skills"]}
        prefs = {normalize(x) for x in ats["preferred_skills"]}
        resps = {normalize(x) for x in ats["responsibilities"]}
        for bucket, skills in (
            ("required", reqs),
            ("preferred", prefs),
            ("responsibility", resps),
        ):
            field = {
                "required": "required_skills",
                "preferred": "preferred_skills",
                "responsibility": "responsibilities",
            }[bucket]
            for g in c.get("gold", {}).get(field, []):
                stats["extractor"][bucket][1] += 1
                stats["extractor"][bucket][0] += int(_approx_hit(g, skills))
        if extraction.education:
            stats["extractor"]["education"] += 1
        if extraction.years_of_experience:
            stats["extractor"]["years"] += 1
        stats["extractor"]["metrics"] += len(extraction.key_metrics)
        for kw in extraction.core_keywords:
            stats["extractor"]["keywords"][kw.importance] += 1
        # ATS-Safety 无 LLM
        spans = [item.text for item in structured.items]
        sv = _evidence_by_span_outputs(ats, spans)
        for k in ("accept", "review", "reject", "total"):
            stats["safety"][k] += sv[k]
    stats["structurer"]["sections_hit"]["见区块"] = sorted(section_tracker)
    return stats, len(cases)


def format_report(stats: dict[str, Any], n: int, dataset_name: str) -> str:
    s = stats
    lines = [
        "# Pipeline 分层评测报告（L1 无 LLM 基线）",
        "",
        f"- 语料：{dataset_name}（{n} 条）",
        "- 范围：L1 确定性管道 + 空 inference 的 ATS 合并；L2（culture/D1-D8/subtext）不在本层",
        "",
        "## L1-1 Structurer",
        f"span 失配：{s['structurer']['span_mismatch']}",
        "",
        "## L1-2 Classifier",
        f"条目数：{s['classifier']['items']}；UNKNOWN：{s['classifier']['unknown']}"
        f"（{s['classifier']['unknown'] / max(s['classifier']['items'], 1):.1%}）",
        "",
        "## L1-3 Extractor（gold 近似命中）",
        "| field | hit/total | rate |",
        "|---|---|---|",
    ]
    for bucket, label in (
        ("required", "required"),
        ("preferred", "preferred"),
        ("responsibility", "responsibility"),
    ):
        h, t = s["extractor"][bucket]
        lines.append(
            f"| {label} | {h}/{t} | {h / t:.2%}" if t else f"| {label} | 0/0 | - |"
        )
    lines += [
        "",
        f"- education 覆盖：{s['extractor']['education']}/{n}；years 覆盖：{s['extractor']['years']}/{n}",
        f"- key_metrics 总计：{s['extractor']['metrics']}",
        f"- core_keywords 分布：high {s['extractor']['keywords']['high']} / medium {s['extractor']['keywords']['medium']} / low {s['extractor']['keywords']['low']}",
        "",
        "## ATS-Safety（每个输出值是否被证据 span 支撑）",
        f"- accept（EXACT/CONTAINED）：{s['safety']['accept']}",
        f"- review（PARAPHRASE/INFERRED）：{s['safety']['review']}",
        f"- reject（UNSUPPORTED）：{s['safety']['reject']}",
        f"- 支撑率 = (accept+review)/total：{((s['safety']['accept'] + s['safety']['review']) / s['safety']['total']):.2%}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline 分层评测（L1 无 LLM 基线）")
    parser.add_argument(
        "dataset", nargs="?", default=str(CASES), help="gold 数据集路径"
    )
    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    stats, n = run(dataset_path)
    dataset_name = dataset_path.name or CASES.name
    report = format_report(stats, n, dataset_name)
    report_path = (
        REPORT
        if dataset_path == CASES
        else REPORT.with_name(f"ats_pipeline_{dataset_path.stem}_report.md")
    )
    report_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
