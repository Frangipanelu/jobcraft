"""简历规则分块器（零 LLM，EXPERIENCE_SPEC §25/§26/§34.3）。

职责：把整篇简历文本按「章节 + 时间锚点 + 段落 + 叙述式句法」拆成经历条目，
产物与 schemas.jobcraft.ResumeExperience 兼容（company/role/period/title/card_type）。
规则无法得体切分时返回 ``None``，调用方（API preview）据此走 LLM 兜底。

原则：
- 只做「分块 + 元数据」，不做 STAR 语义提取（STAR 归 extract_structured）。
- **分块判定与公司提取解绑**：分块只依赖结构信号（时间锚点 / 章节标题 / 段落，
  叙述式段按段落切分即可，不依赖能否提取 company）。
- 动词表只降级为 role 提取器；公司锚用「于在於 + 动词位/句读/时间锚/行尾」，
  动词表盲区只造成 role 留空（LLM 兜底），不再整条丢失 / company 丢失 / 块误判。
- `[个人项目]` 占位仅用于 ``card_type=="project"`` 且 company 为空时；
  work/intern 卡空公司保持留空（不编造）。
- 教育背景 / 技能 / 自我评价 / 获奖等非经历章节不产生经历条目。

评测：tests/fixtures/resume_samples/ 12 份脱敏样本 + expected.json，
回归见 tests/test_resume_splitter_unit.py。
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# ---- 与 db_experience._RANGE_RE 同源的时间范围匹配（保持单份规范，避免漂移） ----
_RANGE_RE = re.compile(
    r"(?:19|20)\d{2}\s*[年.\-/]?\s*\d{0,2}\s*[月]?\s*[-~–—至到]\s*"
    r"(?:(?:19|20)\d{2}\s*[年.\-/]?\s*\d{0,2}\s*[月]?|至今|现在)"
)

# 章节标题（经历类 → 产卡；非经历类 → 剔除）
_EXPERIENCE_SECTION_RE = re.compile(
    r"^\s*(工作经历|项目经历|实习经历|工作經驗|實習經歷)\s*[：:]?\s*$"
)
_EXCLUDE_SECTION_RE = re.compile(
    r"^\s*(教育背景|教育经历|专业技能|个人技能|职业技能|自我评价|获奖经历|荣誉奖项"
    r"|证书|兴趣爱好|其他|联系方式|技术栈)\s*[：:（(]?"
)
# 素材库式经历标题：`#### 经历1：xxx` / `经历1：xxx`
_ENTRY_HEADER_RE = re.compile(r"^\s*#{0,6}\s*经历\s*\d*[\s：:\.、]\s*(.*)$")
# 项目类行内标题常见形式：`个人项目：Tree 记账本` / `开源贡献：...`
_PROJECT_TITLE_RE = re.compile(
    r"^\s*[（(]?\*?\**[（(]?(个人项目|团队项目|开源贡献|课程项目|毕业设计|毕设项目)"
    r"[、:：\s]*(.*)$"
)
# 叙述式公司锚：`于在於 + company + 动词位/句读/时间锚/行尾`
# 仅用于锚定 company 截止位置，**不依赖动词表**（动词表盲区只造成 role 留空，不再丢公司）
_NARRATIVE_COMPANY_RE = re.compile(
    r"[于在於]([^于在於，。；;\s：:]{2,20}?)(?="
    r"(?:担任|任职|从事|负责|做|开发|主导|牵头|参与|协作|协同|搭建|构建|设计|迭代|"
    r"重构|落地|引入|推动|制定|编写|实现|优化|研发|带领|维护|创建)"
    r"|[，。；;,、:：]|(?:19|20)\d{2}|至今|现在|$)"
)
# 叙述式 role 提取器（动词表**仅**提取 role，不参与分块判定/公司提取）
_NARRATIVE_ROLE_RE = re.compile(r"(?:担任|任职|从事|负责|做|开发)([^。；;，,]{2,30})")
# 元数据行后的 company/role 常见分隔为多空格 / 全角空格 / Tab
_HEADER_SEP_RE = re.compile(r"[\u3000\t\s]{1,}")
_ENTRY_HEADER_ONLY_RE = re.compile(r"^\s*经历\s*\d*\s*$")
# 英文引导词（开源项目标题前常见），仅用于清洗标题
_LEADIN_EN_RE = re.compile(
    r"^contributing\s+to\s+|^contribute\s+to\s+|^contributes?\s+to\s+", re.I
)


class ResumeSplitter:
    """纯规则简历分块器（无状态，可独立测试）。"""

    def split(self, raw_text: str) -> Optional[List[Dict[str, Any]]]:
        """把整篇简历文本拆成经历条目。

        :param raw_text: 简历纯文本
        :return: 与 ResumeExperience 兼容的条目列表；规则无法切分时返回 None
        """
        if not raw_text or not raw_text.strip():
            return None

        # 主路径 1：时间锚点切块（覆盖规整经历 + 部分叙述式）
        lines = self._filtered_lines(raw_text)
        blocks = self._split_by_time_ranges(lines)
        if blocks:
            entries = []
            for blk, sec in blocks:
                block = [b for b in blk if b.strip()]
                entries.append(
                    self._parse_block(block, sec, fallback=False, raw_block=block)
                )
        else:
            # 主路径 2：无时间锚点 → 段落切块 + 叙述式句法
            para_blocks = self._split_by_paragraphs(raw_text)
            if not para_blocks:
                return None
            entries = []
            for blk, sec in para_blocks:
                block = [b for b in blk if b.strip()]
                entries.append(
                    self._parse_block(block, sec, fallback=True, raw_block=block)
                )

        entries = [e for e in entries if self._looks_like_entry(e)]
        entries = self._dedupe(entries)
        return entries if entries else None

    # ---------------- 文本预处理 ----------------

    def _filtered_lines(self, raw_text: str) -> List[Tuple[str, str]]:
        """剔除空行 / 头噪声行 / 非经历章节，返回 (行文本, 所在章节类型)。

        :param raw_text: 待过滤的原始文本
        :return: (stripped_line, section_type) 列表；section_type ∈
            {'work','intern','project',''}（''=未进入任何经历章节）
        """
        out: List[Tuple[str, str]] = []
        in_exclude = False
        section_type = ""
        for ln in raw_text.splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            if _EXCLUDE_SECTION_RE.match(stripped):
                in_exclude = True
                section_type = ""
                continue
            if _EXPERIENCE_SECTION_RE.match(stripped):
                in_exclude = False
                section_type = self._section_type_of(stripped)
                continue
            if in_exclude or _is_noise_header(stripped):
                continue
            out.append((stripped, section_type))
        return out

    # ---------------- 切块 ----------------

    def _split_by_time_ranges(
        self, lines: List[Tuple[str, str]]
    ) -> List[Tuple[List[str], str]]:
        """按时间锚点行切块：时间行开新块，后续行并入直到下一条时间行或末尾。

        :param lines: (line, section_type) 列表
        :return: [(block_lines, section_type)] 列表
        """
        blocks: List[Tuple[List[str], str]] = []
        current: List[str] = []
        current_type = ""
        for ln, sec in lines:
            if _RANGE_RE.search(ln):
                if current:
                    blocks.append((current, current_type))
                current = [ln]
                current_type = sec
            elif current:
                current.append(ln)
            # 无时间锚点行且当前无块 → 丢弃（头噪声已在过滤阶段剔除）
        if current:
            blocks.append((current, current_type))
        return blocks

    def _split_by_paragraphs(self, raw_text: str) -> List[Tuple[List[str], str]]:
        """无时间锚点时按空行分段落；段内再按项目标题行二次切分。"""
        blocks: List[Tuple[List[str], str]] = []
        for para in re.split(r"\n\s*\n+", raw_text):
            lines = self._filtered_lines(para)
            if not lines:
                continue
            current: List[str] = []
            current_type = lines[0][1]
            for ln, sec in lines:
                if self._is_block_start(ln) and current:
                    blocks.append((current, current_type))
                    current = [ln]
                    current_type = sec
                else:
                    current.append(ln)
            if current:
                blocks.append((current, current_type))
        return blocks

    def _is_block_start(self, line: str) -> bool:
        """段落内明显的新块起始行。"""
        return bool(
            _PROJECT_TITLE_RE.match(line)
            or _ENTRY_HEADER_RE.match(line)
            or _ENTRY_HEADER_ONLY_RE.match(line)
            or bool(re.match(r"^\s*[（(]?\d+[）)。、.]", line))
        )

    # ---------------- 元数据解析 ----------------

    def _parse_block(
        self,
        block: List[str],
        section_type: str = "",
        fallback: bool = False,
        raw_block: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """从单块提取 metadata（company/role/period/title/card_type）。

        :param block: 单个经历的文本行
        :param section_type: 所在经历章节类型（'work'/'intern'/'project'/''）
        :param fallback: 无时间锚点的叙述式/段落分块
        :param raw_block: 原始文本行（附带给调用方展示，不参与元数据）
        """
        head = block[0]
        card_type = self._detect_section_type(block, section_type)

        # 项目标题行优先识别
        raw_text = "\n".join(raw_block or block).strip()
        pm = _PROJECT_TITLE_RE.match(head)
        if pm:
            title = self._clean_title(pm.group(2), head)
            return self._entry("", "", "", title, "project", raw_text)

        # 时间行：period + 尾部 tokens
        m = _RANGE_RE.search(head)
        if m:
            period = m.group(0).strip()
            rest = head[m.end() :].strip()
            tokens = [t for t in _HEADER_SEP_RE.split(rest) if t] if rest else []
            tokens = [t.strip("[]{}(()）：:，,。.．") for t in tokens]
            tokens = [t for t in tokens if t and not _is_noise_token(t)]
            if card_type == "project":
                title = tokens[0] if tokens else self._clean_title(None, head)
                return self._entry("", "", period, title, "project", raw_text)
            company = tokens[0] if tokens else ""
            role = tokens[1] if len(tokens) >= 2 else ""
            return self._entry(
                company, role, period, company or role, card_type, raw_text
            )

        if fallback:
            # 叙述式：公司锚与 role 解耦提取（互不依赖）
            cm = _NARRATIVE_COMPANY_RE.search(head)
            rm = _NARRATIVE_ROLE_RE.search(head)
            company = cm.group(1).strip() if cm else ""
            role = rm.group(1).strip() if rm else ""
            title = company or role or self._clean_title(None, head)
            return self._entry(company, role, "", title, card_type, raw_text)

        # 时间行缺失但块存在（主路径不应触发）
        title = self._clean_title(None, head)
        return self._entry("", "", "", title, card_type, raw_text)

    def _entry(
        self,
        company: str,
        role: str,
        period: str,
        title: str,
        card_type: str,
        raw_text: str = "",
    ) -> Dict[str, Any]:
        """构造与 ResumeExperience 兼容的条目 dict。

        project 卡 company 为空时填 ``[个人项目]`` 占位；
        work/intern 卡空公司保持留空（不编造）。
        """
        entry = {
            "company": company,
            "role": role,
            "period": period,
            "title": title,
            "summary": "",
            "card_type": card_type,
            "achievements": [],
            "raw_text": raw_text,
        }
        if card_type == "project" and not str(company or "").strip():
            entry["company"] = "[个人项目]"
        return entry

    def _clean_title(self, raw: Optional[str], head: str) -> str:
        """清洗标题：去括号技术栈、去英文引导词。"""
        t = (raw or "").strip("（()） \t：:")
        if not t:
            t = head.strip("：: ")
        t = _LEADIN_EN_RE.sub("", t).strip()
        t = t.split("（")[0].split("(")[0].strip()
        return t

    # ---------------- 辅助 ----------------

    def _section_type_of(self, header: str) -> str:
        """由经历章节标题推导卡类型。"""
        if re.match(r"^\s*(实习经历|實習經歷)\s*[：:]?\s*$", header):
            return "intern"
        if re.match(r"^\s*(项目经历|項目經歷)\s*[：:]?\s*$", header):
            return "project"
        return "work"

    def _detect_section_type(self, block: List[str], section_type: str = "") -> str:
        """根据章节信号与内容特征推断经历类型。"""
        if section_type in ("work", "intern", "project"):
            return section_type
        joined = "\n".join(block)
        if re.search(r"实习", joined):
            return "intern"
        if _PROJECT_TITLE_RE.match(block[0]) or (
            not _RANGE_RE.search(block[0]) and re.search(r"项目|系统|平台", joined)
        ):
            return "project"
        return "work"

    def _looks_like_entry(self, e: Dict[str, Any]) -> bool:
        """是否构成一条可呈现的经历。"""
        blob = " ".join(
            str(e.get(k) or "") for k in ("company", "role", "period", "title")
        ).strip()
        if len(blob) < 4:
            return False
        return not _is_noise_header(blob)

    def _dedupe(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for e in entries:
            key = (
                str(e.get("company") or ""),
                str(e.get("role") or ""),
                str(e.get("period") or "") or str(e.get("title") or ""),
                str(e.get("title") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
        return out


def _is_noise_header(line: str) -> bool:
    """姓名 / 求职意向 / 联系方式 / 链接等噪声行（不构成经历）。"""
    if re.match(r"^[（(]?\d{11}[）)]?$", line):
        return True
    if re.match(r"^\d{3,4}-\d{4,}", line):
        return True
    if "邮箱" in line or "@" in line:
        return True
    if "作品集链接" in line or line.startswith("http"):
        return True
    if re.match(
        r"^(求职意向|应聘岗位|应聘职位|联系电话|姓名|联系方式|学校|专业)", line
    ):
        return True
    return False


def _is_noise_token(token: str) -> bool:
    return token in {"至今", "现在", "至"} or re.match(r"^\d{6,}$", str(token))


def split_resume_text(raw_text: str) -> Optional[List[Dict[str, Any]]]:
    """模块入口：规则分块整篇简历。规则无法处理返回 None（调用方走 LLM 兜底）。"""
    return ResumeSplitter().split(raw_text)


__all__ = ["ResumeSplitter", "split_resume_text", "_RANGE_RE"]
