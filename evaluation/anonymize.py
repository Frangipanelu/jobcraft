"""面试素材脱敏管线（T-EVAL-2 A2）。

把用户提供的真实面试逐字稿 / JD 文本清洗为可入库的评测 case，
写入 ``evaluation/datasets/review_cases.jsonl`` 或 ``prep_cases.jsonl``。

脱敏规则（evaluation-design-v1.md §数据来源）：

1. **清除候选人 PII**：
   - 手机号（大陆 1[3-9]xxxxxxxxx / +86 前缀）→ ``[手机]``
   - 邮箱 → ``[邮箱]``
   - 微信号 / QQ 号（上下文含"微信/QQ"）→ ``[微信]`` / ``[QQ]``
   - 身份证号 → ``[身份证]``
   - 姓名：用户在 ``--name`` 参数显式提供候选人姓名时逐个替换为 ``[候选人]``；
     未提供则不猜测替换（避免误伤常用词）
2. **公司名保留**（评测需要真实公司语境），仅当与候选人姓名相同时替换。
3. **学校名**：``--school`` 参数显式提供时替换为 ``[学校]``。
4. JD 文本除联系方式（手机/邮箱/微信/QQ）外基本原样保留。

用法::

    # 逐字稿 → review_cases（.txt / .md / .docx 均可）
    python -m evaluation.anonymize evaluation/datasets/real/raw_review_01.docx \\
        --kind review --company 字节跳动 --position 后端开发工程师 \\
        --round-type 技术面 --out evaluation/datasets/review_cases.jsonl --append

    # JD → prep_cases
    python -m evaluation.anonymize evaluation/datasets/real/raw_jd_01.txt \\
        --kind prep --company 美团 --position 后端开发工程师 \\
        --out evaluation/datasets/prep_cases.jsonl --append

    # 多次脱敏复核（不落盘，只打印）
    python -m evaluation.anonymize evaluation/datasets/real/raw.txt --kind review --dry-run

注意：本模块只做**确定性正则替换**，不做语义改写；姓名/学校依赖调用方
显式传入（自动化命名识别误伤率过高，不符合"暴露问题而非隐藏"准则）。
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


def load_text_file(path: Path) -> str:
    """按扩展名读取素材文本（.docx 走 stdlib 提取，其余按 UTF-8 文本读）。

    支持 ``.txt`` / ``.md`` / ``.docx``（docx = zip + word/document.xml，
    用 zipfile + ElementTree 提取 ``w:t`` 段落文本，零第三方依赖）。

    :param path: 素材文件路径
    :return: 提取的纯文本
    :raises ValueError: 扩展名不支持或 docx 损坏
    :raises UnicodeDecodeError: 文本文件非 UTF-8
    """
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ""):
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise ValueError(f"不支持的素材格式: {path.suffix}（支持 .txt / .md / .docx）")


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _extract_docx_text(path: Path) -> str:
    """从 docx 提取段落文本（stdlib：zip + ElementTree，零新依赖）。

    逐段落（``w:p``）收集 ``w:t`` 文本，段内 ``w:tab`` 转制表符，
    段落间以换行连接——保留 ``_parse_dialogue`` 所需的逐行结构。

    :param path: docx 文件路径
    :return: 提取的纯文本
    :raises ValueError: 不是合法 zip 或缺 word/document.xml
    """
    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError(f"非法 docx 文件: {path}（{exc}）") from exc

    root = ElementTree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for p in root.iter(f"{_W_NS}p"):
        parts: list[str] = []
        for node in p.iter():
            if node.tag == f"{_W_NS}t":
                parts.append(node.text or "")
            elif node.tag == f"{_W_NS}tab":
                parts.append("\t")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


# ---- 正则（顺序即替换顺序，先长后短避免子串截断） ----

_PHONE_RE = re.compile(r"(?:\+?86[-\s]?)?1[3-9]\d{9}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WECHAT_QQ_RE = re.compile(
    r"(?:微信|weixin|wechat|QQ|qq)[\s:：]*([A-Za-z][-_A-Za-z0-9]{5,19}|\d{5,12})"
)
_IDCARD_RE = re.compile(r"\d{17}[\dXx]")

# 占位符
_PHONE_PLACEHOLDER = "[手机]"
_EMAIL_PLACEHOLDER = "[邮箱]"
_WECHAT_PLACEHOLDER = "[微信]"
_QQ_PLACEHOLDER = "[QQ]"
_IDCARD_PLACEHOLDER = "[身份证]"
_NAME_PLACEHOLDER = "[候选人]"
_SCHOOL_PLACEHOLDER = "[学校]"


def scrub_text(
    text: str,
    *,
    names: list[str] | None = None,
    school: str | None = None,
) -> str:
    """对单段文本执行脱敏替换（确定性、可重入）。

    :param text: 原始文本
    :param names: 候选人姓名列表（逐个替换为 ``[候选人]``）
    :param school: 学校名称（替换为 ``[学校]``）
    :return: 脱敏后文本
    """
    if not text:
        return text

    # 1. 身份证（先于手机号，避免 18 位数字被手机号正则误伤前缀）
    text = _IDCARD_RE.sub(_IDCARD_PLACEHOLDER, text)

    # 2. 手机号
    text = _PHONE_RE.sub(_PHONE_PLACEHOLDER, text)

    # 3. 邮箱
    text = _EMAIL_RE.sub(_EMAIL_PLACEHOLDER, text)

    # 4. 微信 / QQ（带上下文锚定）
    def _wechat_qq_sub(m: re.Match) -> str:
        keyword = m.group(0)
        if "qq" in keyword.lower():
            return keyword[: keyword.lower().index("qq")] + _QQ_PLACEHOLDER
        return (
            keyword[: keyword.lower().index("微信") if "微信" in keyword else 0]
            + _WECHAT_PLACEHOLDER
        )

    text = _WECHAT_QQ_RE.sub(_wechat_qq_sub, text)

    # 5. 姓名 / 学校（显式传入才替换；长词优先）
    for n in sorted(names or [], key=len, reverse=True):
        if n and n.strip():
            text = text.replace(n.strip(), _NAME_PLACEHOLDER)
    if school and school.strip():
        text = text.replace(school.strip(), _SCHOOL_PLACEHOLDER)

    return text


def build_review_case(
    raw_text: str,
    *,
    case_id: str,
    company: str,
    position: str,
    round_type: str,
    jd_text: str = "",
    cards: list[dict] | None = None,
    names: list[str] | None = None,
    school: str | None = None,
) -> dict:
    """从逐字稿原文构建一条 review 评测 case（脱敏后）。

    :param raw_text: 面试逐字稿原文
    :param case_id: case 唯一 id（如 ``rev_real_01``）
    :param company: 公司名（保留）
    :param position: 岗位名
    :param round_type: 轮次（技术面/业务面/HR面）
    :param jd_text: 关联 JD（可空）
    :param cards: 经历卡列表（可空；每卡 dict 含 title/summary/content）
    :param names: 候选人姓名列表
    :param school: 学校名
    :return: review case dict（与 review_cases.jsonl 行结构一致）
    """
    return {
        "case_id": case_id,
        "source": "real",
        "company": company,
        "position": position,
        "round_type": round_type,
        "raw_text": scrub_text(raw_text, names=names, school=school),
        "jd_text": scrub_text(jd_text, names=names, school=school) if jd_text else "",
        "cards": cards or [],
    }


def build_prep_case(
    *,
    case_id: str,
    company: str,
    position: str,
    round_type: str,
    jd_text: str,
    cards: list[dict] | None = None,
    dimension_requirements: list[dict] | None = None,
    names: list[str] | None = None,
    school: str | None = None,
) -> dict:
    """从 JD / 经历卡构建一条 prep 评测 case（脱敏后）。

    :param case_id: case 唯一 id（如 ``prep_real_01``）
    :param company: 公司名（保留）
    :param position: 岗位名
    :param round_type: 轮次
    :param jd_text: JD 原文
    :param cards: 经历卡列表（每卡 dict 含 title/summary/content/tags）
    :param dimension_requirements: 维度要求（每 dict 含 dimension/level/evidence）
    :param names: 候选人姓名列表
    :param school: 学校名
    :return: prep case dict（与 prep_cases.jsonl 行结构一致）
    """
    scrubbed_cards = []
    for c in cards or []:
        scrubbed_cards.append(
            {
                "id": c.get("id"),
                "title": scrub_text(c.get("title", ""), names=names, school=school),
                "summary": scrub_text(c.get("summary", ""), names=names, school=school),
                "content": scrub_text(c.get("content", ""), names=names, school=school),
                "tags": c.get("tags", []),
            }
        )
    return {
        "case_id": case_id,
        "source": "real",
        "company": company,
        "position": position,
        "round_type": round_type,
        "jd_text": scrub_text(jd_text, names=names, school=school),
        "cards": scrubbed_cards,
        "dimension_requirements": dimension_requirements or [],
    }


def append_jsonl(path: Path, row: dict) -> None:
    """把一条 case 追加写入 jsonl（UTF-8，无 BOM）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """CLI 入口：读原始文件 → 脱敏 → 追加到目标 jsonl（或 dry-run 打印）。"""
    p = argparse.ArgumentParser(description="面试素材脱敏管线")
    p.add_argument("input", type=Path, help="原始素材文件路径")
    p.add_argument("--kind", choices=["review", "prep"], required=True)
    p.add_argument("--case-id", default="", help="case id（缺省从文件名推断）")
    p.add_argument("--company", default="", help="公司名（保留）")
    p.add_argument("--position", default="", help="岗位名")
    p.add_argument("--round-type", default="技术面", help="轮次")
    p.add_argument(
        "--jd-file", type=Path, default=None, help="关联 JD 文件（review 用）"
    )
    p.add_argument("--names", default="", help="候选人姓名，逗号分隔")
    p.add_argument("--school", default="", help="学校名")
    p.add_argument("--out", type=Path, default=None, help="输出 jsonl 路径")
    p.add_argument("--append", action="store_true", help="追加而非覆盖")
    p.add_argument("--dry-run", action="store_true", help="只打印脱敏结果不落盘")
    args = p.parse_args()

    raw = load_text_file(args.input)
    names = [n.strip() for n in args.names.split(",") if n.strip()]
    case_id = args.case_id or args.input.stem

    if args.kind == "review":
        jd_text = load_text_file(args.jd_file) if args.jd_file else ""
        case = build_review_case(
            raw,
            case_id=case_id,
            company=args.company,
            position=args.position,
            round_type=args.round_type,
            jd_text=jd_text,
            names=names,
            school=args.school or None,
        )
    else:
        case = build_prep_case(
            case_id=case_id,
            company=args.company,
            position=args.position,
            round_type=args.round_type,
            jd_text=raw,
            names=names,
            school=args.school or None,
        )

    if args.dry_run or not args.out:
        print(json.dumps(case, ensure_ascii=False, indent=2))
        return

    if args.append:
        append_jsonl(args.out, case)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"写入 {args.out}（case_id={case_id}）")


if __name__ == "__main__":
    main()
