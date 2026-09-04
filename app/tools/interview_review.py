"""
面试复盘分析模块（Phase 1：无 RAG）

功能：
1. 解析面试记录文本为结构化对话
2. 识别面试官问题及意图
3. 生成标准答案、诊断反馈、改进建议
4. 关联最相关的经历卡
5. 把结果写入 interview_records / interview_qa_pairs
"""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.prompts import load_prompt
from app.tools import db_tools


# 8 维能力矩阵定义
ABILITY_DIMENSIONS = [
    ("D1", "技术深度"),
    ("D2", "业务理解"),
    ("D3", "问题拆解"),
    ("D4", "方案设计"),
    ("D5", "落地执行"),
    ("D6", "数据复盘"),
    ("D7", "协作沟通"),
    ("D8", "职业规划"),
]

# 8 维能力评分 rubric（精简但保留关键区分度）
DIMENSION_RUBRIC = {
    "D1 技术深度": "L5 原理+选型+优化+踩坑；L3 原理和步骤清楚；L1 概念错误或答不出",
    "D2 业务理解": "L5 关联商业目标并量化；L3 知道场景但缺深度；L1 对业务无理解",
    "D3 问题拆解": "L5 有框架，定位根因；L3 能列原因缺框架；L1 无法定位或思路错",
    "D4 方案设计": "L5 多方案对比+路线图；L3 基本方案缺细节/风险；L1 无方案或明显错误",
    "D5 落地执行": "L5 项目管理+协作+可验证结果；L3 能讲做了什么但较粗；L1 无细节或结果不可验证",
    "D6 数据复盘": "L5 指标体系完整+AB/归因；L3 有数据缺体系/关键指标；L1 无数据支撑",
    "D7 协作沟通": "L5 结构化+说服力+推动对齐；L3 能沟通但欠打磨；L1 表达混乱难理解",
    "D8 职业规划": "L5 目标清晰且匹配岗位；L3 模糊但方向对；L1 敷衍或与岗位无关",
}
RUBRIC_TEXT = "\n".join(f"{k}: {v}" for k, v in DIMENSION_RUBRIC.items())
LEVEL_SCORE_MAP = "L5=90-100 L4=80-89 L3=60-79 L2=40-59 L1=0-39"

# 分析时最多处理的 QA 对数（受 Groq TPM 限制）
MAX_ANALYSIS_QA_PAIRS = 8


def _detect_role(speaker: str) -> str:
    """根据讲话人名称判断角色"""
    s = speaker.strip().lower()
    if "面试官" in s or s in ("interviewer", "面", "q", "问"):
        return "interviewer"
    if (
        "候选人" in s
        or "面试者" in s
        or "我" in s
        or "应试者" in s
        or "应聘者" in s
        or s in ("candidate", "interviewee", "a", "答")
    ):
        return "candidate"
    return "unknown"


# 常见说话人前缀，支持“面试官/候选人/我/面试者”等关键词以及 Q/A、问/答
_SPEAKER_PREFIX_RE = re.compile(
    r"^(?P<prefix>面试官|候选人|面试者|我|应试者|应聘者|interviewer|candidate|interviewee|q|a|问|答)\s*[:：]?\s+(?P<content>.+)$",
    re.IGNORECASE,
)
_TIME_SEP_RE = re.compile(
    r"^(?P<speaker>.+?)\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<content>.+)$"
)
_TIME_ONLY_RE = re.compile(r"^\s*(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<content>.+)$")
_COLON_RE = re.compile(r"^(?P<speaker>.*?)\s*[:：]\s*(?P<content>.+)$")
# 语音转文字常见格式：讲话人1 - 0:00 / 说话人1 - 0:00 / Speaker 1 - 0:00 / 发言者1 - 0:00
_SPEAKER_TIME_DASH_RE = re.compile(
    r"^(?P<speaker>(?:讲话人|说话人|发言人|Speaker|发言者|人|Person)\s*\d+)\s*[-–—~]\s*(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*(?P<content>.*)$",
    re.IGNORECASE,
)


def _is_likely_speaker(speaker: str) -> bool:
    """判断一个前缀是否像说话人标识"""
    s = speaker.strip()
    if not s:
        return False
    if _detect_role(s) != "unknown":
        return True
    # 允许简短的人名/编号作为说话人，如 "A", "面试官A", "张三"
    if len(s) <= 12 and not re.search(r"[。，！？,.!?]", s):
        return True
    return False


# 常见语音转文字/代称标签，用于定位“对话从哪一行开始”
_KNOWN_SPEAKER_LABEL_RE = re.compile(
    r"^(面试官|面试者|候选人|我|Interviewer|Interviewee|Candidate|"
    r"Q|A|问|答|讲话人|说话人|发言人|Speaker|发言者|Person|Spk|S|"
    r"甲|乙|男|女)\b",
    re.IGNORECASE,
)


def _is_known_speaker_label(speaker: str) -> bool:
    """判断是否是已知的说话人标签（含中性代称）"""
    s = speaker.strip()
    if not s:
        return False
    if _detect_role(s) != "unknown":
        return True
    if _KNOWN_SPEAKER_LABEL_RE.match(s):
        return True
    if re.fullmatch(
        r"(讲话人|说话人|发言人|speaker|发言者|person|spk|s)\s*\d+|a|b|1|2",
        s,
        re.IGNORECASE,
    ):
        return True
    return False


def _looks_like_dialogue_line(line: str) -> bool:
    """判断一行是否是面试对话的开始行（用于跳过标题/说明等头部）"""
    if _SPEAKER_TIME_DASH_RE.match(line):
        return True
    if _TIME_ONLY_RE.match(line):
        return True
    m = _TIME_SEP_RE.match(line)
    if m and _is_known_speaker_label(m.group("speaker").strip()):
        return True
    m = _COLON_RE.match(line)
    if m and _is_known_speaker_label(m.group("speaker").strip()):
        return True
    if _KNOWN_SPEAKER_LABEL_RE.match(line):
        return True
    return False


def _split_line(line: str) -> tuple[Optional[str], str, str, bool]:
    """
    尝试把一行拆成 (speaker, time, content, is_new_speaker)。
    如果无法拆分为新的说话人，则返回 (None, "", line, False)。
    """
    # 0. 语音转文字格式：讲话人1 - 0:00 [内容可能换行]
    m = _SPEAKER_TIME_DASH_RE.match(line)
    if m:
        speaker = m.group("speaker").strip()
        if _is_likely_speaker(speaker):
            return speaker, m.group("time").strip(), m.group("content").strip(), True

    # 1. 说话人 时间 内容，如“面试官 09:12 请你介绍一下自己”
    m = _TIME_SEP_RE.match(line)
    if m:
        speaker = m.group("speaker").strip()
        # 如果时间戳出现在最前面（如“09:00 ...”），speaker 会被错拆为“09”，这里排除纯时间/数字前缀
        if _is_likely_speaker(speaker) and not re.fullmatch(r"\d[\d:\.]*/?", speaker):
            return speaker, m.group("time").strip(), m.group("content").strip(), True

    # 2. 显式前缀 + 内容，如“面试官 请你介绍一下自己”或“面试官：请你..."
    m = _SPEAKER_PREFIX_RE.match(line)
    if m:
        return m.group("prefix").strip(), "", m.group("content").strip(), True

    # 3. 说话人：内容，如“面试官：请你介绍一下自己”
    m = _COLON_RE.match(line)
    if m:
        speaker = m.group("speaker").strip()
        content = m.group("content").strip()
        if _is_likely_speaker(speaker) and not re.fullmatch(r"\d[\d:\.]*/?", speaker):
            return speaker, "", content, True

    return None, "", line, False


# 中性/代称说话人对：遇到这些组合时，不应依赖单字母硬编码角色，而要基于内容推断
_AMBIGUOUS_SPEAKER_PAIRS = [
    {"a", "b"},
    {"甲", "乙"},
    {"男", "女"},
    {"speaker1", "speaker2"},
    {"s1", "s2"},
    {"spk1", "spk2"},
    {"发言者1", "发言者2"},
    {"讲话人1", "讲话人2"},
    {"说话人1", "说话人2"},
    {"发言人1", "发言人2"},
    {"person1", "person2"},
    {"1", "2"},
]

# 提问/请求特征（用于推断面试官）
_QUESTION_RE = re.compile(
    r"[？?]|什么|多少|怎么|为什么|如何|怎样|介绍一下|说说|聊聊|谈谈|描述一下|"
    r"有没有|是否|能不能|可以吗|怎么看待|怎么看|请.*(介绍|说|讲|描述|聊聊|谈谈)",
    re.IGNORECASE,
)
_REQUEST_RE = re.compile(
    r"请|麻烦|帮忙|做.*介绍|介绍一下|简单说|开始吧|自我", re.IGNORECASE
)

# 回答/自我介绍特征（用于推断面试者）
_FIRST_PERSON_RE = re.compile(r"我|我们|本人|我的", re.IGNORECASE)
_EXPERIENCE_RE = re.compile(
    r"经历|项目|负责|参与|公司|毕业|实习|工作|职位", re.IGNORECASE
)

# 常见被语音转文字错误合并到面试官问题末尾的面试者简短插话
_CANDIDATE_RESPONSE_MARKERS = {
    "面试官你好",
    "您好",
    "你好",
    "谢谢",
    "感谢",
    "谢谢面试官",
    "麻烦了",
}


def _split_candidate_tail(content: str) -> tuple[str, str]:
    """切掉面试官问题末尾混入的面试者简短插话（如'面试官你好'、'谢谢'）。"""
    if not content:
        return content, ""
    work = content
    # 如果末尾正好是分隔符，先去掉，避免 rpartition 拿到空 tail
    while work and work[-1] in "，,。；;！!？?":
        work = work[:-1]
    # 末尾短句恰好是面试者对面试官的礼貌用语时，切分出来
    for sep in ("，", ",", "。", "；", ";", "！", "!", "？", "?"):
        if sep in work:
            head, _, tail = work.rpartition(sep)
            tail = tail.strip()
            if (
                tail
                and len(tail) <= 12
                and any(
                    tail.startswith(m) or m.startswith(tail)
                    for m in _CANDIDATE_RESPONSE_MARKERS
                )
            ):
                return head.strip() + sep, tail
    return content, ""


# 识别面试官长句中被语音转文字错误合并进来的面试者简短插话
_INTERLEAVED_RESPONSE_RE = re.compile(
    r"(?P<head>.+?)(?P<punct1>[？?])\s*"
    r"(?P<resp>对|嗯|是的|好的|行|可以|没问题|明白了|知道了|了解了|清楚了|对的|没错|是啊|嗯嗯|对对)(?P<punct2>[，,。；;！!？?])\s*"
    r"(?P<rest>.+)",
    re.IGNORECASE,
)


def _split_interleaved_candidate_response(content: str) -> tuple[str, str]:
    """识别面试官长句中混有的面试者简短插话，如'对吧？对，然后...'。"""
    if len(content) < 30:
        return content, ""
    m = _INTERLEAVED_RESPONSE_RE.search(content)
    if m:
        rest = m.group("rest").strip()
        if len(rest) >= 10:
            question = (m.group("head") + (m.group("punct1") or "？")).strip() + rest
            return question, m.group("resp")
    return content, ""


def _infer_unknown_roles(dialogue: List[Dict[str, Any]]) -> None:
    """对未知角色对话做推断（不覆盖已识别角色，除中性代称对需要重置）"""
    if not dialogue:
        return

    speakers = list({d["speaker"] for d in dialogue})

    # 如果是中性代称对（A/B、甲/乙等），先重置为 unknown，避免硬编码角色导致颠倒
    speaker_set_lower = {s.strip().lower() for s in speakers}
    is_ambiguous_pair = any(
        speaker_set_lower == pair for pair in _AMBIGUOUS_SPEAKER_PAIRS
    )
    if is_ambiguous_pair:
        for d in dialogue:
            d["role"] = "unknown"

    known_roles = {d["speaker"]: d["role"] for d in dialogue if d["role"] != "unknown"}

    if len(speakers) == 2:
        # 两个发言人场景：优先基于内容推断
        _infer_two_speaker_roles(dialogue, speakers, known_roles)
        return

    if len(known_roles) == len(speakers) - 1 and len(speakers) > 1:
        # 只有一个角色未知，其他都已明确：未知者取反
        known_speaker, known_role = next(iter(known_roles.items()))
        other_role = "candidate" if known_role == "interviewer" else "interviewer"
        for d in dialogue:
            if d["role"] == "unknown" and d["speaker"] != known_speaker:
                d["role"] = other_role


def _infer_two_speaker_roles(
    dialogue: List[Dict[str, Any]],
    speakers: List[str],
    known_roles: Dict[str, str],
) -> None:
    """针对两个发言人的角色推断，结合提问/请求信号与回答/经历信号"""
    # 如果两个角色都已知，无需推断
    if len(known_roles) == 2:
        return

    interviewer_score: Dict[str, float] = {spk: 0.0 for spk in speakers}
    candidate_score: Dict[str, float] = {spk: 0.0 for spk in speakers}
    first_speaker: Optional[str] = None

    for d in dialogue:
        spk = d["speaker"]
        if first_speaker is None:
            first_speaker = spk
        content = d.get("content", "")
        content_len = len(content)

        # 面试官信号：提问、请求
        if _QUESTION_RE.search(content) or content.rstrip().endswith(("?", "？")):
            interviewer_score[spk] += 1.0
        if _REQUEST_RE.search(content):
            interviewer_score[spk] += 0.8

        # 面试者信号：长段自我介绍/经历描述，且含第一人称
        if content_len > 40 and _FIRST_PERSON_RE.search(content):
            candidate_score[spk] += 1.0
        if _EXPERIENCE_RE.search(content):
            candidate_score[spk] += 0.5

    # 先开口的人 slight 倾向于是面试官
    if first_speaker:
        interviewer_score[first_speaker] += 0.2

    # 分别选出最像面试官和最像面试者的人
    interviewer = max(speakers, key=lambda s: interviewer_score[s])
    candidate = max(speakers, key=lambda s: candidate_score[s])

    # 如果同一人同时拿下两个最高分，用分差重新分配
    if interviewer == candidate:
        diff = {s: interviewer_score[s] - candidate_score[s] for s in speakers}
        interviewer = max(speakers, key=lambda s: diff[s])
        candidate = min(speakers, key=lambda s: diff[s])

    for d in dialogue:
        if d["speaker"] == interviewer:
            d["role"] = "interviewer"
        elif d["speaker"] == candidate:
            d["role"] = "candidate"


def _parse_dialogue(raw_text: str) -> List[Dict[str, Any]]:
    """
    把原始面试记录文本解析为结构化对话片段。

    支持格式（可混用）：
      面试官 09:12 请你介绍一下自己
      面试官：请你介绍一下自己
      候选人：我叫...
      我：我叫...
      讲话人1 - 0:00 请你介绍一下自己（语音转文字常见格式）
      09:12 请你介绍一下自己（仅时间戳，按轮次交替推断发言人）
      （不含说话人的换行会智能合并到上一条发言或推断为新回答）
    """
    # 去除 UTF-8 BOM 及常见零宽字符，避免上传文件时首行匹配失败
    raw_text = re.sub("[\ufeff\u200b\u200c\u200d\u2060\ufe0f]", "", raw_text)
    lines = raw_text.splitlines()
    dialogue: List[Dict[str, Any]] = []
    last_time_only_speaker: Optional[str] = None
    found_dialogue_start = False
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = raw_line.strip()
        if not line:
            i += 1
            continue

        # 跳过标题/说明等头部，直到遇到明确的对话开始行
        if not found_dialogue_start and not _looks_like_dialogue_line(line):
            i += 1
            continue
        found_dialogue_start = True

        speaker, time_str, content, is_new = _split_line(line)
        if is_new:
            # 说话人+时间行后内容可能换行缩进，如下一行不是新说话人则合并
            if not content:
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n:
                    next_line = lines[j].strip()
                    _, _, _, next_is_new = _split_line(next_line)
                    if not next_is_new and not _TIME_ONLY_RE.match(next_line):
                        content = next_line
                        i = j
            seq = len(dialogue) + 1
            dialogue.append(
                {
                    "sequence": seq,
                    "speaker": speaker or "未知",
                    "time": time_str,
                    "content": content,
                    "role": _detect_role(speaker or ""),
                }
            )
            last_time_only_speaker = None
            i += 1
            continue

        # 仅时间戳开头的行，先尝试解析剩余部分是否含显式说话人（如“09:00 面试官：...”）
        m = _TIME_ONLY_RE.match(line)
        if m:
            time_str = m.group("time").strip()
            rest = m.group("content").strip()
            speaker, _, content, is_new = _split_line(rest)
            if is_new:
                seq = len(dialogue) + 1
                dialogue.append(
                    {
                        "sequence": seq,
                        "speaker": speaker or "未知",
                        "time": time_str,
                        "content": content,
                        "role": _detect_role(speaker or ""),
                    }
                )
                last_time_only_speaker = None
                i += 1
                continue

            # 否则按“仅时间戳”处理，轮次交替推断发言人
            if last_time_only_speaker == "发言者1":
                speaker = "发言者2"
            else:
                speaker = "发言者1"
            last_time_only_speaker = speaker
            seq = len(dialogue) + 1
            dialogue.append(
                {
                    "sequence": seq,
                    "speaker": speaker,
                    "time": time_str,
                    "content": rest,
                    "role": "unknown",
                }
            )
            i += 1
            continue

        _merge_or_create(line, dialogue)
        i += 1

    _infer_unknown_roles(dialogue)
    return dialogue


# 句子结束标点，用于判断无标签行是否应视为新发言
_SENTENCE_END_RE = re.compile(r"[。！？.!?…~]$")

# 续行开头特征：出现这些词，大概率是同一人发言的延续
_CONTINUATION_START_RE = re.compile(
    r"^(然后|另外|还有|其次|比如|例如|而且|并且|不过|但是|因为|所以|于是|接着|最后|"
    r"嗯|啊|呃|就是|其实|可能|大概|对了|对|好|行|可以|没错|当然|首先|第一|第二|第三|"
    r"接下来|后来|之后|之前|除此以外|同时|并且|and|but|so|because|also|then|um|uh)\s*",
    re.IGNORECASE,
)


def _merge_or_create(line: str, dialogue: List[Dict[str, Any]]) -> None:
    """处理不含说话人前缀的行：优先合并续行；若前一条是完整面试官问题，则视为面试者回答。"""
    if not dialogue:
        dialogue.append(
            {
                "sequence": 1,
                "speaker": "未知",
                "time": "",
                "content": line,
                "role": "unknown",
            }
        )
        return

    last = dialogue[-1]
    last_role = last.get("role", "")
    last_content = last.get("content", "").strip()

    # 面试者的回答被拆成多段时，统一合并到同一条回答
    if last_role == "candidate":
        last["content"] += "\n" + line
        return

    # 面试官发言后的无标签行：如果不是明显续行，且前一句已完整结束，则视为面试者新回答
    if last_role == "interviewer":
        if _CONTINUATION_START_RE.match(line) or not _SENTENCE_END_RE.search(
            last_content
        ):
            last["content"] += "\n" + line
            return
        seq = len(dialogue) + 1
        dialogue.append(
            {
                "sequence": seq,
                "speaker": "面试者",
                "time": "",
                "content": line,
                "role": "candidate",
            }
        )
        return

    # 其他情况视为上一条发言的续行
    last["content"] += "\n" + line


class _QuestionIntentItem(BaseModel):
    """单个问题的轻量意图识别结果"""

    sequence: int = Field(..., description="QA 对编号")
    intent: str = Field(..., description="面试官真实考察意图，一句话")
    dimension: str = Field(..., description="维度编码与名称，如 D1 技术深度")
    level: str = Field(..., description="难度等级 L1-L5")


class _QuestionTableOut(BaseModel):
    """问题表输出"""

    questions: List[_QuestionIntentItem] = Field(
        ..., description="所有识别到的问题，按 sequence 排序"
    )


def _truncate_text(text: str, max_chars: int) -> str:
    """按字符截断文本，保留前半部分和后半部分，中间用省略号连接"""
    if not text or len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n...[内容过长，已截断]...\n" + text[-half:]


# 纯反问/确认/闲聊型问题，不进入正式分析
_RHETORICAL_RE = re.compile(
    r"^(对|嗯|啊|哦|好|行|可以|没问题|明白了|了解了|知道了|是吧|对吧|是不是|好吗|可以吗|"
    r"清楚吗|懂吗|明白吗|了解吗|知道吧|是吧|对不|ok|okay|嗯嗯|对对)[吧吗呢]?[？?]?$",
    re.IGNORECASE,
)
# 过渡/闲聊开头，后续没有实质问题
_TRANSITION_ONLY_RE = re.compile(
    r"^(行|好|对|嗯|然后|接着|那么|这样|不错|可以|挺好的|明白了|了解了|知道了|"
    r"我们接着|接下来|先这样|先聊|先说一下)[，,。；;！!？?]?\s*(.+)$",
    re.IGNORECASE,
)


def _is_interviewer_question(content: str) -> bool:
    """判断面试官发言是否是值得分析的正式问题/要求"""
    if not content:
        return False

    # 去掉首尾标点后的核心文本
    core = content.strip("，,。；;！!？? ")

    # 纯反问/确认/闲聊，不分析
    if _RHETORICAL_RE.match(core):
        return False

    # 明显提问/请求
    if "?" in content or "？" in content:
        # 但如果整个问题只是反问确认，仍过滤
        if _RHETORICAL_RE.match(core):
            return False
        return True
    if _QUESTION_RE.search(content):
        return True
    if _REQUEST_RE.search(content):
        return len(content) >= 10

    # 兜底：较长的陈述，但需排除纯确认/过渡/重复面试者的话
    if len(content) < 40:
        return False

    # 纯确认/过渡型短句，不单独成问题
    filler_patterns = [
        r"^(就是|行|好|对|嗯|哦|啊|然后|接着|那么|这样|不错|可以|挺好的|明白了|了解了|知道了)[，,。；;！!？?]?$",
        r"^(那|那么)[，,。；;！!？?]?$",
    ]
    if any(re.search(p, content) for p in filler_patterns):
        return False

    # 过渡开头但后续无实质问题：如"行，那我们接着聊项目。"
    m = _TRANSITION_ONLY_RE.match(content)
    if m and not (
        _QUESTION_RE.search(m.group(2)) or "?" in m.group(2) or "？" in m.group(2)
    ):
        return False

    return True


def _build_qa_pairs(dialogue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按顺序把面试官问题与后续面试者回答配对，并过滤伪问题。"""
    qa_pairs: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for d in dialogue:
        role = d.get("role", "unknown")
        content = d.get("content", "").strip()
        if role == "interviewer":
            # 切掉被语音转文字错误合并到问题末尾的面试者插话
            clean_content, candidate_tail = _split_candidate_tail(content)
            # 识别长句中混有的面试者简短插话（如"对吧？对，然后..."）
            final_content, interleaved_resp = _split_interleaved_candidate_response(
                clean_content
            )
            if _is_interviewer_question(final_content):
                if current:
                    qa_pairs.append(current)
                current = {
                    "sequence": len(qa_pairs) + 1,
                    "start_time": d.get("time", ""),
                    "speaker": d.get("speaker", ""),
                    "question_text": final_content,
                    "my_answer": candidate_tail,
                }
                if interleaved_resp:
                    current["my_answer"] = (
                        current["my_answer"] + "\n" + interleaved_resp
                        if current["my_answer"]
                        else interleaved_resp
                    )
            else:
                # 面试官的 filler/过渡语句，合并到当前回答中
                if current is not None:
                    for part in (candidate_tail, interleaved_resp, final_content):
                        if part:
                            current["my_answer"] = (
                                current["my_answer"] + "\n" + part
                                if current["my_answer"]
                                else part
                            )
        elif role == "candidate":
            if current is None:
                continue
            current["my_answer"] = (
                current["my_answer"] + "\n" + content
                if current["my_answer"]
                else content
            )
        else:
            # unknown 角色：如果已有当前问题，则合并为回答续行
            if current is not None:
                current["my_answer"] = (
                    current["my_answer"] + "\n" + content
                    if current["my_answer"]
                    else content
                )

    if current:
        qa_pairs.append(current)

    # 第二遍：合并"伪问题"（无真正提问信号且回答极短）到相邻 QA 对
    merged: List[Dict[str, Any]] = []
    buffer_text = ""
    for i, qa in enumerate(qa_pairs):
        q = qa["question_text"]
        a = qa["my_answer"].strip()
        has_question_signal = bool(
            "?" in q or "？" in q or _QUESTION_RE.search(q) or _REQUEST_RE.search(q)
        )
        is_pseudo = (not has_question_signal) and (len(a) <= 12 or len(q) <= 12)

        if is_pseudo and merged:
            # 合并到上一个 answer 后面，当作过渡/确认语
            prev = merged[-1]
            prev["my_answer"] = (
                (prev["my_answer"] + "\n" if prev["my_answer"] else "")
                + f"[过渡]{q} {a}"
            ).strip()
            buffer_text = ""
        elif is_pseudo:
            # 开头就是伪问题，先缓冲，尝试合并到下一个问题
            buffer_text = f"{q} {a}".strip()
        else:
            if buffer_text:
                qa["my_answer"] = (
                    f"[过渡]{buffer_text}\n" + (qa["my_answer"] or "")
                ).strip()
                buffer_text = ""
            merged.append(qa)

    # 末尾还有缓冲，合并到最后一个 answer
    if buffer_text and merged:
        merged[-1]["my_answer"] = (
            merged[-1]["my_answer"] + "\n[过渡]" + buffer_text
        ).strip()

    # 重排 sequence
    for idx, qa in enumerate(merged, 1):
        qa["sequence"] = idx

    return [qa for qa in merged if qa["question_text"]]


def _find_my_answer(dialogue: List[Dict[str, Any]], question_seq: int) -> str:
    """找到某个面试官问题之后、下一个面试官问题之前的候选人回答"""
    answer_parts = []
    found = False
    for d in dialogue:
        if d["sequence"] == question_seq:
            found = True
            continue
        if found:
            if d.get("role") == "interviewer":
                break
            answer_parts.append(d["content"])
    return " ".join(answer_parts).strip()


def create_interview_record(
    user_id: int,
    title: str,
    company: str,
    position: str,
    round_type: str,
    raw_text: str,
    job_analysis_id: Optional[int] = None,
    submission_id: Optional[int] = None,
) -> int:
    """创建面试记录，仅做解析，不触发 LLM 分析。"""
    parsed_dialogue = _parse_dialogue(raw_text)
    record_id = db_tools.insert_interview_record(
        {
            "user_id": user_id,
            "title": title or f"{company}-{position}-{round_type}",
            "company": company,
            "position": position,
            "round_type": round_type,
            "job_analysis_id": job_analysis_id,
            "submission_id": submission_id,
            "raw_text": raw_text,
            "parsed_dialogue": parsed_dialogue,
            "analysis": {},
            "status": "parsed",
        }
    )
    return record_id


# 问题表可识别的问题上限（轻量意图识别，可略高于详细分析上限）
MAX_QUESTION_TABLE_QA_PAIRS = 20


def _build_question_table_prompt(
    company: str,
    position: str,
    round_type: str,
    qa_pairs: List[Dict[str, Any]],
    jd_text: str = "",
) -> str:
    """构造问题表意图识别 prompt（轻量，不分析回答）。"""
    questions_text = "\n".join(
        f"Q{qa['sequence']} [{qa.get('start_time', '')}] {qa['question_text']}"
        for qa in qa_pairs[:MAX_QUESTION_TABLE_QA_PAIRS]
    )
    jd_section = f"JD:{_truncate_text(jd_text, 400)}\n\n" if jd_text else ""
    return load_prompt(
        "interview",
        "question_table_intent",
        round_type=round_type,
        position=position,
        company=company,
        jd_section=jd_section,
        rubric_text=RUBRIC_TEXT,
        level_score_map=LEVEL_SCORE_MAP,
        questions_text=questions_text,
    )


def preview_question_intents(
    qa_pairs: List[Dict[str, Any]],
    company: str = "",
    position: str = "",
    round_type: str = "",
    jd_text: str = "",
) -> List[Dict[str, Any]]:
    """
    为 QA 对生成轻量意图识别结果，**不写入数据库**，仅用于解析预览。

    当问题数量过多时，只识别前 MAX_QUESTION_TABLE_QA_PAIRS 个。
    """
    if not qa_pairs:
        return []

    from app.agents.question_intent_agent import QuestionIntentAgent

    agent = QuestionIntentAgent()
    out = agent.run(
        {
            "company": company,
            "position": position,
            "round_type": round_type,
            "qa_pairs": qa_pairs,
            "jd_text": jd_text,
        }
    )
    return out["qa_pairs"]


def _get_job_context(record: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    """根据面试记录关联的岗位分析，提取 JD、维度要求、经历卡等上下文。"""
    context = {
        "jd_text": "",
        "dimension_requirements": [],
        "selected_card_ids": [],
        "cards": [],
    }
    job_id = record.get("job_analysis_id")
    if not job_id:
        context["cards"] = db_tools.list_cards(user_id=user_id, include_inactive=False)
        return context

    analysis = db_tools.get_job_analysis(job_id, user_id)
    if analysis:
        context["jd_text"] = analysis.get("jd_text", "")
        context["dimension_requirements"] = analysis.get("dimension_requirements") or []

    selected_ids = db_tools.get_selected_card_ids_by_job(job_id)
    context["selected_card_ids"] = selected_ids
    if selected_ids:
        cards = []
        for cid in selected_ids:
            card = db_tools.get_card(cid, user_id)
            if card:
                cards.append(card)
        context["cards"] = cards

    if not context["cards"]:
        context["cards"] = db_tools.list_cards(user_id=user_id, include_inactive=False)

    return context


def _format_cards_for_prompt(cards: List[Dict[str, Any]], max_cards: int = 5) -> str:
    """把经历卡格式化为 prompt 文本，优先展示完整 STAR 内容。"""
    lines = []
    for c in cards[:max_cards]:
        card_id = c.get("id")
        title = c.get("title") or ""
        summary = c.get("summary") or ""
        content = c.get("content") or ""
        background = c.get("background") or ""
        problem = c.get("problem") or ""
        solution = c.get("solution") or ""
        execution = c.get("execution") or ""
        result = c.get("result") or ""
        metrics = c.get("metrics") or {}
        tags = c.get("tags") or []

        parts = [
            f"ID:{card_id} 标题:{title}",
            f"标签:{','.join(tags)}",
            f"概要:{summary}",
        ]
        if content:
            parts.append(f"完整内容:{content[:300]}")
        else:
            for label, text in [
                ("背景", background),
                ("问题", problem),
                ("方案", solution),
                ("执行", execution),
                ("结果", result),
            ]:
                if text:
                    parts.append(f"{label}:{text[:200]}")
        if metrics:
            parts.append(f"指标:{metrics}")
        lines.append(" | ".join(parts))
    return "\n".join(lines) or "无"
