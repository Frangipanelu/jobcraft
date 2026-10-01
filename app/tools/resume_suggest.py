"""
简历 AI 优化建议工具

FE-RESUME-02：以「简历要点 + 岗位分析产物（JD原文 / ATS画像 / gap结论）」为输入，
单次 LLM 调用产出 bullet 级改写建议，统一经由 llm_json.invoke_structured 出口
（审计/缓存/观测）。同步端点与 resume_suggest 任务共用本模块。
"""

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.core.llm import model
from app.core.prompts import load_prompt
from app.tools.llm_json import invoke_structured

logger = logging.getLogger(__name__)

# 单次生成建议条数上限（prompt 同步声明，双侧约束）
MAX_SUGGESTIONS = 12


class ResumeSuggestionItem(BaseModel):
    """LLM 输出的单条改写建议（无 id/status，由工具补齐）"""

    type: Literal["keyword", "metric", "order", "prune", "polish"] = Field(
        ..., description="建议类型"
    )
    title: str = Field("", description="卡片标题，如「补充 JD 关键词」")
    original_text: str = Field(..., description="要点原文（逐字复制输入）")
    suggested_text: str = Field(..., description="改写后的完整要点文本")
    reason: str = Field("", description="一句话依据")
    item_index: int = Field(..., ge=0, description="所属卡片序号")
    bullet_index: int = Field(..., ge=0, description="卡片内要点序号")


class ResumeSuggestOutput(BaseModel):
    """LLM 结构化输出容器"""

    suggestions: List[ResumeSuggestionItem] = Field(default_factory=list)


def load_suggest_context(
    submission: Dict[str, Any], user_id: Optional[int] = None
) -> Dict[str, Any]:
    """装配建议生成的岗位上下文（服务端自取，前端不传 JD 数据）。

    取数链：submission.jd_text（兜底）→ job_analysis.jd_text / ats_profile /
    gap_items（P4-1 落库产物）。analysis 缺失或读取失败时降级为 submission
    自身上下文，不阻断生成。

    :param submission: db_submission.get_submission 结果
    :param user_id: 归属过滤（可选）
    :return: {"jd_text": str, "ats": dict, "gap_items": list}
    """
    from app.tools import db_job

    jd_text = submission.get("jd_text") or ""
    ats: Dict[str, Any] = {}
    gap_items: List[str] = []
    analysis_id = submission.get("job_analysis_id")
    if analysis_id:
        try:
            analysis = db_job.get_job_analysis(analysis_id, user_id)
        except Exception as e:  # 读取失败降级，不阻断
            logger.warning("岗位分析读取失败（analysis_id=%s）: %s", analysis_id, e)
            analysis = None
        if analysis:
            jd_text = analysis.get("jd_text") or jd_text
            ats = analysis.get("ats_profile") or {}
            raw_gaps = analysis.get("gap_items") or []
            gap_items = [str(g) for g in raw_gaps if g]
    return {"jd_text": jd_text, "ats": ats, "gap_items": gap_items}


def _build_job_context(jd_text: str, ats: Dict[str, Any], gap_items: List[str]) -> str:
    """把岗位上下文拼成 prompt 段落；全空时给明确的降级说明。"""
    if not jd_text and not ats:
        return "（无岗位上下文：按通用简历标准优化，不得臆造岗位关键词）"

    parts: List[str] = []
    if ats.get("job_title"):
        parts.append(f"目标岗位：{ats['job_title']}")
    if ats.get("required_skills"):
        parts.append(f"硬性技能：{'、'.join(ats['required_skills'])}")
    if ats.get("preferred_skills"):
        parts.append(f"加分技能：{'、'.join(ats['preferred_skills'])}")
    if ats.get("responsibilities"):
        parts.append(f"核心职责：{'、'.join(ats['responsibilities'])}")
    if ats.get("key_metrics"):
        parts.append(f"关键指标：{'、'.join(ats['key_metrics'])}")
    if ats.get("culture_keywords"):
        parts.append(f"文化关键词：{'、'.join(ats['culture_keywords'])}")
    if jd_text:
        parts.append(f"JD 原文（截断）：{jd_text[:1500]}")
    if gap_items:
        parts.append(f"已有分析的差距结论（参考）：{'；'.join(gap_items[:10])}")
    if not parts:
        return "（无岗位上下文：按通用简历标准优化，不得臆造岗位关键词）"
    return "\n".join(parts)


def suggest_resume_edits(
    bullets: List[Dict[str, Any]],
    jd_text: str = "",
    ats: Optional[Dict[str, Any]] = None,
    gap_items: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """生成简历要点改写建议（1 次 LLM 调用 + 防御性清洗）。

    :param bullets: [{"item_index": int, "bullet_index": int, "text": str}, ...]
    :param jd_text: JD 原文（可空 → 通用优化降级）
    :param ats: ATS 画像 dict（可空）
    :param gap_items: 已有差距结论（可空，仅作参考上下文）
    :return: 建议记录列表（含 id/status，可直接落 resume_suggestions 列）；
             全部被清洗剔除时返回 []
    :raises ValueError: bullets 为空
    :raises RuntimeError: LLM 调用失败
    """
    if not bullets:
        raise ValueError("简历要点为空，无法生成建议")
    ats = ats or {}
    gap_items = gap_items or []

    bullets_section = "\n".join(
        f"[item_index={b['item_index']}, bullet_index={b['bullet_index']}] {b['text']}"
        for b in bullets
    )
    prompt = load_prompt(
        "resume",
        "suggest",
        version=1,
        job_context=_build_job_context(jd_text, ats, gap_items),
        bullets_section=bullets_section,
    )
    parsed = invoke_structured(
        model,
        ResumeSuggestOutput,
        prompt,
        debug_label="resume_suggest",
        prompt_version="1",
    )

    # 定位表：(item_index, bullet_index) → 输入原文（用于剔除 LLM 幻觉定位）
    locator = {
        (int(b["item_index"]), int(b["bullet_index"])): str(b["text"]) for b in bullets
    }
    records: List[Dict[str, Any]] = []
    for item in parsed.suggestions:
        if len(records) >= MAX_SUGGESTIONS:
            break
        expected = locator.get((item.item_index, item.bullet_index))
        if expected is None:
            logger.warning(
                "剔除越界定位建议（item=%s, bullet=%s）",
                item.item_index,
                item.bullet_index,
            )
            continue
        if item.original_text.strip() != expected.strip():
            logger.warning("剔除原文不符建议（幻觉定位，item=%s）", item.item_index)
            continue
        suggested = item.suggested_text.strip()
        if not suggested or suggested == expected.strip():
            continue
        records.append(
            {
                "id": "sg_" + uuid.uuid4().hex[:8],
                "type": item.type,
                "title": item.title.strip(),
                "original_text": expected,
                "suggested_text": suggested,
                "reason": item.reason.strip(),
                "item_index": item.item_index,
                "bullet_index": item.bullet_index,
                "status": "pending",
            }
        )
    return records
