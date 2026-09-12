"""Task 02 验证脚本：jd_classifier 在 40 条评测语料上的分类诊断。

用法:
    python -m evaluation.run_jd_classifier_stats

输出每 case 的标签分布 + 有限覆盖率（gold 词汇出现在对应标签桶的条数占比）：
- required_skills → REQUIRED 标签桶
- preferred_skills → PREFERRED 标签桶
- responsibilities → RESPONSIBILITY 标签桶

注意：这是 Span 级「召回近似」（gold 词在对应桶内任意一条中出现即计命中），
不是正式 F1；正式指标在 TASK-P5-07 分层评测中建立。
"""

from __future__ import annotations

from pathlib import Path

from app.pipeline.jd_classifier import classify_jd
from app.pipeline.jd_structurer import structure_jd
from evaluation.datasets import load_cases

DATASET = Path(__file__).parent / "datasets" / "jd_cases.jsonl"


def _hitrate(gold_words: list[str], texts: list[str]) -> float:
    if not gold_words:
        return 1.0
    hit = sum(1 for w in gold_words if any(w.lower() in t.lower() for t in texts))
    return hit / len(gold_words)


def main() -> None:
    cases = load_cases(DATASET)
    dist: dict[str, int] = {}
    hits = {"required": [], "preferred": [], "responsibility": []}
    for case in cases:
        doc = structure_jd(case["jd_text"])
        classified = classify_jd(doc)
        buckets: dict[str, list[str]] = {}
        for c in classified:
            buckets.setdefault(c.label.value, []).append(c.text)
            dist[c.label.value] = dist.get(c.label.value, 0) + 1
        hits["required"].append(
            _hitrate(
                (case.get("gold") or {}).get("required_skills", []),
                buckets.get("required", []),
            )
        )
        hits["preferred"].append(
            _hitrate(
                (case.get("gold") or {}).get("preferred_skills", []),
                buckets.get("preferred", []),
            )
        )
        hits["responsibility"].append(
            _hitrate(
                (case.get("gold") or {}).get("responsibilities", []),
                buckets.get("responsibility", []),
            )
        )
    print(f"cases: {len(cases)}")
    print("label distribution:", dict(sorted(dist.items(), key=lambda kv: -kv[1])))
    for name, values in hits.items():
        print(f"gold-token hitrate {name}: {sum(values) / len(values):.3f}")
    print(f"UNKNOWN (to LLM fallback): {dist.get('unknown', 0)}")


if __name__ == "__main__":
    main()
