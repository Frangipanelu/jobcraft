"""
定制简历生成入口

读取 card_versions（优先）或原卡 raw_text，按 STAR 模板拼装 Markdown 简历并落盘。
同时生成预设排版的 HTML 简历（用于前端预览 + 打印导出 PDF）。
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.jobcraft import ResumePersonalInfo
from app.tools import db_tools
from app.tools.jobcraft_resume_gen import (
    generate_resume_html,
    generate_resume_markdown,
)

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
            cards.append(c)
    if not cards:
        raise ValueError("无可用经历卡")

    position = analysis.get("position", "")
    company = analysis.get("company", "")

    info = ResumePersonalInfo(**(personal_info or {})) if personal_info else None

    md = generate_resume_markdown(
        user_id=analysis.get("user_id", 1),
        company=company,
        position=position,
        jd_text=analysis.get("jd_text", ""),
        ats=None,
        company_ctx=None,
        cards=cards,
        card_versions=card_versions or {},
        personal_info=info,
    )
    html = generate_resume_html(
        company=company,
        position=position,
        ats=None,
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

    return {
        "job_analysis_id": job_analysis_id,
        "resume_path": str(md_path),
        "resume_markdown": md,
        "resume_html": html,
        "resume_html_path": str(html_path),
    }
