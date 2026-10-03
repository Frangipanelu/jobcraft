"""
定制简历生成入口

读取 card_versions（优先）或原卡 raw_text，按 STAR 模板拼装 Markdown 简历并落盘。
同时生成预设排版的 HTML 简历（用于前端预览 + 打印导出 PDF）。
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.jobcraft import ATSProfile, ResumePersonalInfo
from app.tools import db_tools
from app.tools.jobcraft_resume_gen import (
    generate_resume_html,
    generate_resume_markdown,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "output" / "job_resume"


def _sanitize_filename(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9_-]", "_", text).strip("_")[:40]


def generate_resume(
    job_analysis_id: int,
    selected_card_ids: List[int],
    card_versions: Optional[Dict[int, str]] = None,
    personal_info: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    生成定制简历

    :param card_versions: {card_id: edited_text}，前端保存后的版本 map
    :param personal_info: {name/phone/email/city/github/education/years}
    :param user_id: 按用户过滤所有权（越权时 404）
    :return: {job_analysis_id, resume_path, resume_markdown, resume_html}
    """
    analysis = db_tools.get_job_analysis(job_analysis_id, user_id)
    if not analysis:
        raise ValueError(f"job_analysis #{job_analysis_id} 不存在")

    cards = []
    for cid in selected_card_ids:
        c = db_tools.get_card(cid, user_id)
        if c and c.get("is_active"):
            try:
                from app.tools.db_expression import (
                    get_active_expression_content,
                    increment_active_expression_usage,
                )

                c["active_expression"] = get_active_expression_content(cid, user_id)
                if c["active_expression"]:
                    increment_active_expression_usage(cid, user_id)
            except Exception:
                c["active_expression"] = None
            cards.append(c)
    if not cards:
        raise ValueError("无可用经历卡")

    position = analysis.get("position", "")
    company = analysis.get("company", "")

    # BE-ATS-01：核心能力/技能标签段来自 job_analysis.ats_profile（V0011），
    # 原硬编码 ats=None 使该段永不渲染
    ats = None
    raw_ats = analysis.get("ats_profile") or {}
    if raw_ats:
        try:
            ats = ATSProfile(**raw_ats)
        except (TypeError, ValueError) as e:
            logger.warning("ats_profile 解析失败，简历跳过核心能力块: %s", e)

    info = ResumePersonalInfo(**(personal_info or {})) if personal_info else None

    md = generate_resume_markdown(
        user_id=analysis.get("user_id", 1),
        company=company,
        position=position,
        jd_text=analysis.get("jd_text", ""),
        ats=ats,
        company_ctx=None,
        cards=cards,
        card_versions=card_versions or {},
        personal_info=info,
    )
    html = generate_resume_html(
        company=company,
        position=position,
        ats=ats,
        cards=cards,
        card_versions=card_versions or {},
        personal_info=info,
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_part = _sanitize_filename(company or "目标公司")
    position_part = _sanitize_filename(position or "岗位")
    base = f"{ts}_{company_part}_{position_part}"
    md_path = OUTPUT_ROOT / f"{base}.md"
    html_path = OUTPUT_ROOT / f"{base}.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    # 写关联
    for c in cards:
        db_tools.upsert_job_mapping(job_analysis_id, c["id"])

    # T-M6-2：产物写入 resume_version（M5-Q2 裁决——投递前不再 insert submission；
    # 存量 submission 的简历正文由 V0022 一次性迁为 v1，这里只读其 id 做岗位链接）。
    # 失败容忍（与原 submission 块同构）：简历文件已落盘，版本落库失败不阻断返回。
    resume_version_id = None
    try:
        from app.tools.db_job_entity import find_or_create_job, get_job_id_by_analysis
        from app.tools.db_resume_version import create_resume_version
        from app.tools.db_submission import get_submission_by_analysis

        uid = user_id or analysis.get("user_id") or 1
        legacy_submission_id = None
        try:
            legacy = get_submission_by_analysis(job_analysis_id, uid)
            legacy_submission_id = legacy["id"] if legacy else None
        except Exception:
            logger.debug("无存量 submission（job_analysis_id=%s）", job_analysis_id)

        job_id = get_job_id_by_analysis(job_analysis_id, uid)
        if job_id is None:
            # 存量岗位可能尚无 job 行：按分析结果懒回填（find_or_create 按
            # 公司+岗位名幂等匹配，并回链 analysis/submission 防 FE 地图双行）
            job_id = find_or_create_job(
                uid,
                position=position,
                company=company,
                job_analysis_id=job_analysis_id,
                submission_id=legacy_submission_id,
            )
        if job_id is None:
            raise ValueError("岗位归属缺失（job_id=None）")
        version = create_resume_version(
            user_id=uid,
            job_id=job_id,
            job_analysis_id=job_analysis_id,
            resume_markdown=md,
        )
        resume_version_id = version["id"]
    except Exception:
        logger.warning(
            "保存简历到 resume_version 失败，job_analysis_id=%s",
            job_analysis_id,
            exc_info=True,
        )

    return {
        "job_analysis_id": job_analysis_id,
        # submission_id 保留为 None（FE 切换到 resume_version_id 前的契约过渡）
        "submission_id": None,
        "resume_version_id": resume_version_id,
        "resume_path": str(md_path),
        "resume_markdown": md,
        "resume_html": html,
        "resume_html_path": str(html_path),
    }
