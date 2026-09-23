"""
经历卡统一消费入口（§32 Consumer Chain）

get_card_render_text() 定义所有下游消费方读取经历卡文本的唯一入口，
优先级：版本链 → 结构化 STAR → raw_text → content → summary → title。

下游 resume 生成 / 面试准备 / 缺口分析 / 匹配打分均收敛至此，不再各自拼装。
"""

from typing import Any, Dict, List, Optional


def _star_achievements(ai_struct: Dict[str, Any]) -> List[Dict[str, Any]]:
    """取出结构化 STAR 的 achievements 列表（非法结构返回空）"""
    achievements = ai_struct.get("achievements") or []
    return achievements if isinstance(achievements, list) else []


def _star_markdown(ai_struct: Dict[str, Any]) -> str:
    """结构化 STAR → markdown 渲染（简历正文用：### 标题 + **背景/行动/困难/解决/结果**）"""
    parts: List[str] = []
    for ach in _star_achievements(ai_struct):
        parts.append(f"### {ach.get('title', '')}")
        if ach.get("situation"):
            parts.append(f"**背景**：{ach['situation']}")
        action = ach.get("action") or {}
        if action.get("main"):
            parts.append(f"**行动**：{action['main']}")
        if action.get("difficulty"):
            parts.append(f"**困难**：{action['difficulty']}")
        if action.get("resolution"):
            parts.append(f"**解决**：{action['resolution']}")
        if ach.get("result"):
            parts.append(f"**结果**：{ach['result']}")
        parts.append("")
    return "\n".join(parts)


def _star_plain(ai_struct: Dict[str, Any]) -> str:
    """结构化 STAR → 纯文本（关键词匹配 / LLM 提示词用，去掉 markdown 标签词）"""
    parts: List[str] = []
    for ach in _star_achievements(ai_struct):
        if ach.get("situation"):
            parts.append(str(ach["situation"]))
        action = ach.get("action")
        if isinstance(action, dict):
            if action.get("main"):
                parts.append(str(action["main"]))
            if action.get("difficulty"):
                parts.append(str(action["difficulty"]))
            if action.get("resolution"):
                parts.append(str(action["resolution"]))
        if ach.get("result"):
            parts.append(str(ach["result"]))
    return " ".join(parts)


def get_card_render_text(
    card: Dict[str, Any],
    versions: Optional[Dict[int, str]] = None,
    *,
    markdown: bool = False,
    include_tags: bool = False,
) -> str:
    """
    获取经历卡渲染文本（统一消费入口）。

    :param card: 经历卡 dict
    :param versions: {card_id: 用户编辑终稿}，命中直接返回
    :param markdown: True 时结构化 STAR 渲染为 markdown（简历用）；False 纯文本
    :param include_tags: 结果末尾拼接扁平标签（关键词匹配 / LLM 提示词用）
    :return: 渲染文本
    """
    if versions and card.get("id") in versions:
        return versions[card["id"]]

    ai_struct = card.get("ai_structured")
    text = ""
    if ai_struct and isinstance(ai_struct, dict):
        text = _star_markdown(ai_struct) if markdown else _star_plain(ai_struct)
    if not text:
        for key in ("raw_text", "content", "summary", "title"):
            value = card.get(key)
            if value:
                text = str(value)
                break

    if include_tags:
        tags = card.get("tags") or []
        if tags:
            tags_text = " ".join(str(t) for t in tags)
            text = f"{text} {tags_text}" if text else tags_text
    return text
