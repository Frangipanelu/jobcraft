"""临时评测脚本：规则分块器 vs expected.json（EXP-P1-02 迭代用，非正式测试）。

反编造红线：company/role/period/title 只允许原文子串或白名单占位
（``[个人项目]`` 为 project 卡专用占位，非原文子串）。
"""

import glob
import json
import os

from app.tools.resume_splitter import split_resume_text

SAMPLES = "tests/fixtures/resume_samples"

# project 卡空 company 的占位（非原文子串，但属合规产物）
_PLACEHOLDER = "[个人项目]"


def _assert_no_invention(got, raw_text: str, base: str) -> None:
    """反编造断言：非白名单字段必须为原文子串。"""
    for g in got:
        for field in ("period", "company", "role", "title"):
            v = g.get(field) or ""
            if not v or v == _PLACEHOLDER:
                continue
            assert v in raw_text, f"{base}: 编造 {field}={v}"


def main() -> None:
    total_cards = 0
    hit_cards = 0
    mismatches = []
    for txt in sorted(glob.glob(os.path.join(SAMPLES, "*.txt"))):
        base = os.path.basename(txt)[: -len(".txt")]
        expected = json.load(
            open(os.path.join(SAMPLES, base + ".expected.json"), encoding="utf-8")
        )
        raw = open(txt, encoding="utf-8").read()
        got = split_resume_text(raw)
        exp_entries = expected["entries"]
        if got is None:
            got = []
        _assert_no_invention(got, raw, base)
        # 块数匹配
        count_ok = len(got) == len(exp_entries)
        # 逐块字段匹配（company/role/period/title 任一命中即算块命中）
        block_hits = 0
        for eg in exp_entries:
            if any(
                (g.get("company") == eg["company"] and eg["company"])
                or (g.get("role") == eg["role"] and eg["role"])
                or (g.get("period") == eg["period"] and eg["period"])
                or (g.get("title") == eg["title"] and eg["title"])
                for g in got
            ):
                block_hits += 1
        total_cards += len(exp_entries)
        hit_cards += block_hits
        flag = "OK" if (count_ok and block_hits == len(exp_entries)) else "FAIL"
        mismatches.append((base, flag, exp_entries, got))
        print(
            f"[{flag}] {base}: exp={len(exp_entries)} got={len(got)} block_hit={block_hits}/{len(exp_entries)}"
        )

    print(
        f"\n块级命中率: {hit_cards}/{total_cards} = {hit_cards / max(total_cards, 1):.1%}"
    )
    for base, flag, exp_entries, got in mismatches:
        if flag == "OK":
            continue
        print(f"\n--- {base} ---")
        print("EXPECTED:", json.dumps(exp_entries, ensure_ascii=False, indent=1))
        print("GOT     :", json.dumps(got, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
