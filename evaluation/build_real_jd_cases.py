"""把填好的真实 JD 表格转换为 real_jd_cases.jsonl。

用法（不新增项目依赖，openpyxl 走临时环境）：
    uv run --with openpyxl python -m evaluation.build_real_jd_cases [xlsx 路径]
    缺省读 evaluation/datasets/real_jd_cases_completed.xlsx（已填写）

输入：填好的 xlsx（手工填写）
输出：evaluation/datasets/real_jd_cases.jsonl（合并保留已有条目）

gold 解析规则：
- 逗号/顿号/分号/换行/项目编号 分隔列表字段；dimensions 形如 "D1:4,D2:3"；
  subtext 每条 "表面|潜台词|关键能力|如何证明|置信度"，多条用 ; 分隔。
- gold_pending：required_skills / preferred_skills / responsibilities 任一为空 → True。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from openpyxl import load_workbook

DATASETS = Path(__file__).parent / "datasets"
TEMPLATE = DATASETS / "real_jd_cases_template.xlsx"
COMPLETED = DATASETS / "real_jd_cases_completed.xlsx"
OUT = DATASETS / "real_jd_cases.jsonl"

_LIST_SEP = re.compile(r"[,，、;；/\n\t]+")
_DIM_RE = re.compile(r"^(D\d):(\d)$")
_BULLET_RE = re.compile(r"^\s*(?:\d+[\.、\)）]|[-–—•·*/]|\(?\d+\)?)\s*")


def _split(value: str | None, default: list[str] | None = None) -> list[str]:
    if not value or not str(value).strip():
        return list(default or [])
    out = []
    for seg in _LIST_SEP.split(str(value)):
        seg = _BULLET_RE.sub("", seg).strip()
        if seg:
            out.append(seg)
    return out


def _parse_dimensions(value: str | None) -> list[dict[str, object]]:
    dims: list[dict[str, object]] = []
    for seg in _split(value):
        m = _DIM_RE.match(seg.strip())
        if m and 1 <= int(m.group(2)) <= 5:
            dims.append({"dimension": m.group(1), "level": int(m.group(2))})
    return dims


def _parse_subtext(value: str | None) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    if not value:
        return out
    for text in str(value).split(";"):
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 2 and parts[0]:
            record: dict[str, object] = {
                "surface_requirement": parts[0],
                "hidden_meaning": parts[1] if len(parts) > 1 else "",
                "key_ability": parts[2] if len(parts) > 2 else "",
                "how_to_prove": parts[3] if len(parts) > 3 else "",
                "confidence": 0.5,
            }
            try:
                record["confidence"] = float(parts[4])
            except (IndexError, ValueError):
                pass
            out.append(record)
    return out


def _row_to_case(row_idx: int, row: tuple) -> dict | None:
    name, source, job_title, jd_text, salary = row[0], row[1], row[2], row[3], row[4]
    req, pref, resp, culture = row[5], row[6], row[7], row[8]
    dims, subtext, notes = row[9], row[10], row[11]
    if not jd_text or not str(jd_text).strip():
        return None
    if "示例" in str(name or ""):
        return None
    required = _split(req)
    preferred = _split(pref)
    responsibilities = _split(resp)
    culture_keywords = _split(culture)
    gold_pending = not (required and preferred and responsibilities)
    case_id = str(name or f"real_{row_idx:03d}").strip()
    gold: dict[str, object] = {
        "required_skills": required,
        "preferred_skills": preferred,
        "responsibilities": responsibilities,
        "culture_keywords": culture_keywords,
        "dimensions": {d["dimension"]: d["level"] for d in _parse_dimensions(dims)},
        "salary": str(salary or "").strip(),
        "subtext": _parse_subtext(subtext),
    }
    return {
        "case_id": case_id,
        "job_title": str(job_title or "").strip(),
        "source": str(source or "").strip(),
        "gold_pending": gold_pending,
        "jd_text": str(jd_text).strip(),
        "gold": gold,
        "notes": str(notes or "").strip(),
    }


def build(in_path: Path) -> int:
    wb = load_workbook(in_path)
    ws = wb["真实JD-填写"]
    rows = list(ws.iter_rows(min_row=2, max_col=12, values_only=True))
    new_cases = [
        c for c in (_row_to_case(i, r) for i, r in enumerate(rows, start=2)) if c
    ]
    new_ids = {c["case_id"] for c in new_cases}

    existing: list[dict] = []
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                case = json.loads(line)
                if case.get("case_id") not in new_ids:
                    existing.append(case)

    merged = existing + new_cases
    OUT.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in merged) + "\n",
        encoding="utf-8",
    )
    return len(new_cases), len(merged), merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="真实 JD 表格 → jsonl")
    parser.add_argument(
        "xlsx", nargs="?", default=str(COMPLETED), help="已填写的 xlsx 路径"
    )
    args = parser.parse_args()
    added, total, built = build(Path(args.xlsx))
    pending = [c["case_id"] for c in built if c["gold_pending"]]
    print(
        f"新增 {added} 条，合并后共 {total} 条 --> {OUT.name}；"
        f"gold_pending {len(pending)} 条：{','.join(pending)}"
    )
