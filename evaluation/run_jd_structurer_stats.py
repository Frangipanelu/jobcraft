"""Task 01 验证脚本：jd_structurer 在 40 条评测语料上的结构切分诊断。

用法:
    python -m evaluation.run_jd_structurer_stats

输出：每个 case 识别出的区块种类、items 数量、meta(薪资/地点) 是否命中，
以及对"无标题降级" case 的统计。用于验证 L1 Structurer 层（v0.5 §二十），
不做语义分类正确性判断（那是 jd_classifier / jd_extractor 的指标）。
"""

from __future__ import annotations

from pathlib import Path

from app.pipeline.jd_structurer import SectionKind, structure_jd
from evaluation.datasets import load_cases

DATASET = Path(__file__).parent / "datasets" / "jd_cases.jsonl"


def main() -> None:
    cases = load_cases(DATASET)
    stats = {
        "total": len(cases),
        "no_heading": 0,
        "has_meta_salary": 0,
        "has_meta_location": 0,
        "has_requirements": 0,
        "has_responsibilities": 0,
        "has_preferred": 0,
        "items_total": 0,
        "sections_total": 0,
    }
    unknowns: list[str] = []
    for case in cases:
        cid = case["case_id"]
        doc = structure_jd(case["jd_text"])
        kinds = {s.kind for s in doc.sections}
        stats["sections_total"] += len(doc.sections)
        stats["items_total"] += len(doc.items)
        if SectionKind.UNKNOWN in kinds:
            stats["no_heading"] += 1
            unknowns.append(cid)
        if SectionKind.META_SALARY in kinds:
            stats["has_meta_salary"] += 1
        if SectionKind.META_LOCATION in kinds:
            stats["has_meta_location"] += 1
        if SectionKind.REQUIREMENTS in kinds:
            stats["has_requirements"] += 1
        if SectionKind.RESPONSIBILITIES in kinds:
            stats["has_responsibilities"] += 1
        if SectionKind.PREFERRED in kinds:
            stats["has_preferred"] += 1
    print(f"cases: {stats['total']}")
    print(
        f"  sections_total: {stats['sections_total']}  avg items/section: "
        f"{stats['items_total'] / max(stats['sections_total'], 1):.2f}"
    )
    print(f"  requirements block: {stats['has_requirements']}/{stats['total']}")
    print(f"  responsibilities block: {stats['has_responsibilities']}/{stats['total']}")
    print(f"  preferred block: {stats['has_preferred']}/{stats['total']}")
    print(f"  salary meta:   {stats['has_meta_salary']}/{stats['total']}")
    print(f"  location meta: {stats['has_meta_location']}/{stats['total']}")
    print(f"  no-heading fallback: {stats['no_heading']} {unknowns}")


if __name__ == "__main__":
    main()
