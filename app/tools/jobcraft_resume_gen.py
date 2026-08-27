"""
定制简历生成器（纯模板，无 LLM）

支持两种输出：
  - Markdown：`generate_resume_markdown()`，兼容旧流程（resume_markdown 落库）
  - HTML：`generate_resume_html()`，预设 A4 排版，供前端 iframe 预览 + window.print() 导出 PDF

模板策略：
  - 每条经历卡渲染为「公司 - 职位 - 时间段」标题行 + 要点列表
  - 内容源优先 card_versions（用户编辑终稿）→ ai_structured.achievements → raw_text
"""

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

from app.schemas.jobcraft import ResumePersonalInfo


def _get_card_text(
    card: Dict[str, Any], versions: Optional[Dict[int, str]] = None
) -> str:
    """获取卡片最终文本：优先 card_versions，次之 ai_structured，最后 raw_text"""
    if versions and card["id"] in versions:
        return versions[card["id"]]
    ai_struct = card.get("ai_structured")
    if ai_struct and isinstance(ai_struct, dict):
        achievements = ai_struct.get("achievements") or []
        if achievements:
            parts = []
            for ach in achievements:
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
    return card.get("raw_text") or card.get("content") or card.get("summary") or ""


def _split_bullets(text: str) -> List[str]:
    """把卡片文本拆成要点行（去掉 markdown 标题/标签行）"""
    bullets = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("###"):
            continue
        if line.startswith("**"):
            continue
        if line.startswith("*标签"):
            continue
        # 去掉行首的列表符号
        line = line.lstrip("-•·#* ").strip()
        if line:
            bullets.append(line)
    return bullets


def _personal_info_lines(info: Optional[ResumePersonalInfo]) -> str:
    """个人信息单行展示：姓名（求职意向）电话 | 邮箱 | 城市 | 学历 | 年限"""
    if not info:
        return ""
    parts = []
    if info.phone:
        parts.append(f"电话：{info.phone}")
    if info.email:
        parts.append(f"邮箱：{info.email}")
    if info.city:
        parts.append(f"城市：{info.city}")
    if info.education:
        parts.append(f"学历：{info.education}")
    if info.years:
        parts.append(f"年限：{info.years}")
    if info.github:
        parts.append(f"GitHub/作品：{info.github}")
    return " | ".join(parts)


def _card_header(card: Dict[str, Any]) -> str:
    """卡片标题行：公司 · 职位 · 时间段（缺省回退 title）"""
    company = card.get("company") or ""
    role = card.get("role") or ""
    period = card.get("period") or ""
    if company or role or period:
        parts = [company, role, period]
        return " · ".join(p for p in parts if p)
    return card.get("title") or f"卡片 #{card['id']}"


def generate_resume_markdown(
    user_id: int,
    company: str,
    position: str,
    jd_text: str,
    ats: Optional[Any],
    company_ctx: Optional[Dict[str, Any]],
    cards: List[Dict[str, Any]],
    per_card_scores: Optional[List[Any]] = None,
    suggestions: Optional[List[Any]] = None,
    gap_items: Optional[List[str]] = None,
    card_versions: Optional[Dict[int, str]] = None,
    personal_info: Optional[ResumePersonalInfo] = None,
) -> str:
    """
    生成 Markdown 简历（纯模板，无 LLM）

    :param card_versions: {card_id: edited_text}，由前端保存后传入
    :param personal_info: 用户补充的个人信息
    """
    lines = []
    today = datetime.now().strftime("%Y-%m-%d")

    # 标题
    name = (personal_info.name if personal_info else "") or "【你的名字】"
    lines.append(f"# {name}")
    contact = _personal_info_lines(personal_info)
    if contact:
        lines.append(contact)
    lines.append(f"求职意向：{position}")
    if company:
        lines.append(f"目标公司：{company}")
    lines.append(f"更新日期：{today}")
    lines.append("")

    # 核心能力（来自 ATS）
    if ats:
        skills = []
        if hasattr(ats, "required_skills") and ats.required_skills:
            skills.extend(ats.required_skills)
        if hasattr(ats, "preferred_skills") and ats.preferred_skills:
            skills.extend(ats.preferred_skills[:3])
        if skills:
            lines.append("## 核心能力")
            lines.append("、".join(skills))
            lines.append("")

    # 工作经历
    lines.append("## 工作经历")
    lines.append("")
    for card in cards:
        lines.append(f"### {_card_header(card)}")
        lines.append("")
        text = _get_card_text(card, card_versions)
        lines.append(text)
        tags = card.get("tags") or []
        if tags:
            lines.append(f"*标签：{'、'.join(tags)}*")
        lines.append("")

    # 全篇拼装
    return "\n".join(lines)


def generate_resume_html(
    company: str,
    position: str,
    ats: Optional[Any],
    cards: List[Dict[str, Any]],
    card_versions: Optional[Dict[int, str]] = None,
    personal_info: Optional[ResumePersonalInfo] = None,
) -> str:
    """
    生成预设排版 HTML 简历（A4 打印友好，可 window.print() 导出 PDF）

    :param card_versions: {card_id: edited_text}
    :param personal_info: 用户补充的个人信息
    :return: 完整 HTML 文档字符串
    """
    info = personal_info or ResumePersonalInfo()
    name = escape((info.name or "你的姓名"))
    contact_parts = []
    for v in [info.phone, info.email, info.city, info.education, info.github]:
        if v:
            contact_parts.append(escape(v))
    contact_html = (
        " &nbsp;|&nbsp; ".join(contact_parts) if contact_parts else "电话 / 邮箱待补充"
    )

    # 核心能力
    skills_html = ""
    if ats:
        skills = []
        if getattr(ats, "required_skills", None):
            skills.extend(ats.required_skills)
        if getattr(ats, "preferred_skills", None):
            skills.extend(ats.preferred_skills[:3])
        if skills:
            skills_html = "".join(
                f'<span class="skill-tag">{escape(s)}</span>' for s in skills
            )

    # 工作经历
    entries_html = []
    for card in cards:
        header = escape(_card_header(card))
        bullets = _split_bullets(_get_card_text(card, card_versions))[:4]
        bullet_html = ""
        if bullets:
            bullet_html = (
                "<ul>" + "".join(f"<li>{escape(b)}</li>" for b in bullets) + "</ul>"
            )
        entries_html.append(
            f'<div class="entry"><div class="entry-head">{header}</div>'
            f"{bullet_html}</div>"
        )
    entries_section = (
        "".join(entries_html) if entries_html else '<p class="empty">暂无经历卡片</p>'
    )

    today = datetime.now().strftime("%Y-%m-%d")
    css = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
      color: #262626; font-size: 12.5px; line-height: 1.7;
    }
    @page { size: A4; margin: 16mm 18mm; }
    .resume { max-width: 210mm; margin: 0 auto; padding: 8mm 0; }
    .head { border-bottom: 2px solid #1a237e; padding-bottom: 12px; margin-bottom: 16px; }
    .head h1 { font-size: 26px; color: #1a237e; letter-spacing: 2px; }
    .head .contact { color: #595959; font-size: 12px; margin-top: 6px; }
    .head .meta { color: #8c8c8c; font-size: 11.5px; margin-top: 4px; }
    .section { margin-bottom: 18px; }
    .section h2 {
      font-size: 15px; color: #1a237e;
      border-left: 4px solid #1a237e; padding-left: 8px; margin-bottom: 10px;
    }
    .skill-tag {
      display: inline-block; background: #eef0ff; color: #1a237e;
      padding: 2px 10px; border-radius: 12px; margin: 0 6px 6px 0; font-size: 12px;
    }
    .entry { margin-bottom: 12px; }
    .entry-head { font-weight: 600; font-size: 13.5px; color: #262626; margin-bottom: 4px; }
    .entry ul { padding-left: 20px; }
    .entry li { margin-bottom: 3px; }
    .empty { color: #bfbfbf; }
    .foot { margin-top: 24px; text-align: right; color: #bfbfbf; font-size: 11px; }
    @media print {
      body { padding: 0; }
      .resume { padding: 0; }
    }
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<title>{name} - {escape(position or "求职简历")}</title>
<style>{css}</style>
</head>
<body>
<div class="resume">
  <div class="head">
    <h1>{name}</h1>
    <div class="contact">{contact_html}</div>
    <div class="meta">求职意向：{escape(position or "")} · 目标公司：{escape(company or "")} · 更新日期：{today}</div>
  </div>
  {'<div class="section"><h2>核心能力</h2>' + skills_html + "</div>" if skills_html else ""}
  <div class="section">
    <h2>工作经历</h2>
    {entries_section}
  </div>
  <div class="foot">由 JobCraft 求职助手生成</div>
</div>
</body>
</html>
"""
