"""
投递记录（resume_submission）状态机

统一 `status` 字段为英文枚举，中文仅用于前端显示。
合法流转见 docs/domain-model-v2.md §4.2。
"""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set


class SubmissionStatus(str, Enum):
    """投递记录状态枚举（DB / API 内部统一使用英文码）"""

    APPLIED = "APPLIED"
    INVITED = "INVITED"
    ROUND_1 = "ROUND_1"
    ROUND_2 = "ROUND_2"
    OFFER = "OFFER"
    CLOSED = "CLOSED"


SUBMISSION_STATUS_CN: Dict[SubmissionStatus, str] = {
    SubmissionStatus.APPLIED: "已投递",
    SubmissionStatus.INVITED: "面试邀约",
    SubmissionStatus.ROUND_1: "一面",
    SubmissionStatus.ROUND_2: "二面",
    SubmissionStatus.OFFER: "Offer",
    SubmissionStatus.CLOSED: "已关闭",
}

# 合法流转（§4.2）：顺向推进 + 任意阶段可提前 CLOSED
_ALLOWED_TRANSITIONS: Dict[SubmissionStatus, FrozenSet[SubmissionStatus]] = {
    SubmissionStatus.APPLIED: frozenset({SubmissionStatus.INVITED, SubmissionStatus.CLOSED}),
    SubmissionStatus.INVITED: frozenset({SubmissionStatus.ROUND_1, SubmissionStatus.CLOSED}),
    SubmissionStatus.ROUND_1: frozenset({SubmissionStatus.ROUND_2, SubmissionStatus.CLOSED}),
    SubmissionStatus.ROUND_2: frozenset({SubmissionStatus.OFFER, SubmissionStatus.CLOSED}),
    SubmissionStatus.OFFER: frozenset(),
    SubmissionStatus.CLOSED: frozenset(),
}

# 存量数据里的旧中文字符串 → 新枚举（读时归一化，前向兼容）
_LEGACY_CN_TO_STATUS: Dict[str, SubmissionStatus] = {
    "已投递": SubmissionStatus.APPLIED,
    "面试邀约": SubmissionStatus.INVITED,
    "一面": SubmissionStatus.ROUND_1,
    "二面": SubmissionStatus.ROUND_2,
    "offer": SubmissionStatus.OFFER,
    "Offer": SubmissionStatus.OFFER,
    "已关闭": SubmissionStatus.CLOSED,
}


def normalize_status(value: Optional[str]) -> Optional[SubmissionStatus]:
    """
    把任意输入（枚举值 / 旧中文字符串 / 大小写变体）归一化为英文枚举。

    :param value: 待归一化的状态字符串
    :return: 归一化后的枚举；无法识别返回 None
    """
    if value is None:
        return None
    raw = str(value).strip()
    if raw in _LEGACY_CN_TO_STATUS:
        return _LEGACY_CN_TO_STATUS[raw]
    try:
        return SubmissionStatus(raw)
    except ValueError:
        return None


def status_to_cn(value: Optional[str]) -> str:
    """
    状态码 → 中文显示；未知状态回退为原始值。

    :param value: 状态（枚举值或字符串）
    :return: 中文显示文本
    """
    status = normalize_status(value)
    if status is None:
        return str(value or "")
    return SUBMISSION_STATUS_CN[status]


def is_valid_transition(current: Optional[str], target: Optional[str]) -> bool:
    """
    判断 `current -> target` 是否为合法流转。

    :param current: 当前状态
    :param target: 目标状态
    :return: 合法返回 True
    """
    from_status = normalize_status(current)
    to_status = normalize_status(target)
    if from_status is None or to_status is None:
        return False
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, frozenset())


def next_statuses(current: Optional[str]) -> Set[SubmissionStatus]:
    """
    返回 `current` 可合法流转到的状态集合。

    :param current: 当前状态
    :return: 可达状态集合
    """
    from_status = normalize_status(current)
    if from_status is None:
        return set()
    return set(_ALLOWED_TRANSITIONS.get(from_status, frozenset()))
