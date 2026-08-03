"""
简历生成器单元测试（纯模板，无 LLM/DB 依赖）

覆盖:
  - _split_bullets: 拆要点
  - _card_header: 标题行
  - _personal_info_lines: 个人信息
  - generate_resume_markdown: Markdown 输出
  - generate_resume_html: HTML 输出（预设排版 / 打印样式 / 个人信息注入）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.jobcraft import ResumePersonalInfo
from app.tools.jobcraft_resume_gen import (
    _card_header,
    _personal_info_lines,
    _split_bullets,
    generate_resume_html,
    generate_resume_markdown,
)


def _make_card(**overrides):
    card = {
        "id": 1,
        "title": "AI 推荐策略优化",
        "company": "测试科技有限公司",
        "role": "高级产品经理",
        "period": "2021.03 - 2023.05",
        "raw_text": "- 重构召回策略，CTR +12%\n- 协调算法/工程团队\n",
        "tags": ["推荐", "增长"],
        "ai_structured": None,
    }
    card.update(overrides)
    return card


# ---------- _split_bullets ----------


def test_split_bullets_removes_markdown_noise():
    text = (
        "### 成就标题\n**背景**：xxx\n- 第一点内容\n- 第二点内容\n*标签：推荐、增长*\n"
    )
    bullets = _split_bullets(text)
    assert bullets == ["第一点内容", "第二点内容"]


def test_split_bullets_handles_empty_and_blank():
    assert _split_bullets("") == []
    assert _split_bullets("  \n\n  ") == []


# ---------- _card_header ----------


def test_card_header_prefers_company_role_period():
    card = _make_card()
    header = _card_header(card)
    assert header == "测试科技有限公司 · 高级产品经理 · 2021.03 - 2023.05"


def test_card_header_falls_back_to_title():
    card = _make_card(company="", role="", period="")
    assert _card_header(card) == "AI 推荐策略优化"


def test_card_header_omits_empty_parts():
    card = _make_card(role="", period="")
    assert _card_header(card) == "测试科技有限公司"


# ---------- _personal_info_lines ----------


def test_personal_info_lines_formats_all_fields():
    info = ResumePersonalInfo(
        name="张三",
        phone="13800000000",
        email="z@e.com",
        city="北京",
        github="https://github.com/zhang",
        education="本科·计算机",
        years="5 年",
    )
    line = _personal_info_lines(info)
    assert "电话：13800000000" in line
    assert "邮箱：z@e.com" in line
    assert "城市：北京" in line
    assert "学历：本科·计算机" in line
    assert "年限：5 年" in line
    assert "GitHub/作品" in line


def test_personal_info_lines_empty_when_no_info():
    assert _personal_info_lines(None) == ""
    assert _personal_info_lines(ResumePersonalInfo()) == ""


# ---------- generate_resume_markdown ----------


def test_markdown_uses_personal_info_and_position():
    md = generate_resume_markdown(
        user_id=1,
        company="字节跳动",
        position="高级产品经理",
        jd_text="",
        ats=None,
        company_ctx=None,
        cards=[_make_card()],
        personal_info=ResumePersonalInfo(name="张三", phone="13800000000"),
    )
    assert "# 张三" in md
    assert "电话：13800000000" in md
    assert "求职意向：高级产品经理" in md
    assert "目标公司：字节跳动" in md
    assert "测试科技有限公司 · 高级产品经理 · 2021.03 - 2023.05" in md


def test_markdown_default_name_placeholder_when_no_info():
    md = generate_resume_markdown(
        user_id=1,
        company="",
        position="产品",
        jd_text="",
        ats=None,
        company_ctx=None,
        cards=[_make_card()],
    )
    assert "【你的名字】" in md


# ---------- generate_resume_html ----------


def test_html_contains_a4_print_style():
    html = generate_resume_html(
        company="字节跳动", position="产品经理", ats=None, cards=[_make_card()]
    )
    assert "@page { size: A4" in html
    assert "@media print" in html


def test_html_injects_personal_info():
    info = ResumePersonalInfo(
        name="张三", phone="13800000000", email="z@e.com", education="本科"
    )
    html = generate_resume_html(
        company="",
        position="产品",
        ats=None,
        cards=[_make_card()],
        personal_info=info,
    )
    assert "<h1>张三</h1>" in html
    assert "13800000000" in html
    assert "z@e.com" in html


def test_html_renders_card_header_and_bullets():
    html = generate_resume_html(
        company="", position="产品", ats=None, cards=[_make_card()]
    )
    assert "测试科技有限公司 · 高级产品经理" in html
    assert "重构召回策略，CTR +12%" in html
    assert "协调算法/工程团队" in html


def test_html_escapes_user_content():
    card = _make_card(raw_text="- <script>alert('x')</script>\n")
    html = generate_resume_html(company="", position="产品", ats=None, cards=[card])
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_html_empty_cards_shows_placeholder():
    html = generate_resume_html(company="", position="产品", ats=None, cards=[])
    assert "暂无经历卡片" in html
