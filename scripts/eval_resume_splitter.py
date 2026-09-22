"""临时评测脚本：规则分块器 vs expected.json（EXP-P1-02 迭代用，非正式测试）。"""

import glob
import json
import os

from app.tools.resume_splitter import split_resume_text

SAMPLES = "tests/fixtures/resume_samples"


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
