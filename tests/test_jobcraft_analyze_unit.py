"""
岗位分析工具单元测试（本地匹配 / 缺口 / 匹配等级，无 LLM/DB 依赖）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.jobcraft import ATSProfile, JDRequirements, PerCardScore
from app.tools.jobcraft_analyze import (
    _build_gap_text,
    _match_level,
    _match_term_to_blob,
    _normalize,
    _ats_to_jdreq,
    compute_match,
)


# ---------- _normalize ----------


def test_normalize_removes_punctuation_and_lowercases():
    assert _normalize("Python,开发") == "python开发"
    assert _normalize("  SQL ") == "sql"
    assert _normalize("") == ""


# ---------- _match_term_to_blob ----------


def test_match_tag_exact_has_highest_weight():
    blob = "负责推荐系统重构"
    tags = {"增长"}
    assert _match_term_to_blob("增长", blob, tags) == 2


def test_match_text_substring():
    blob = "负责推荐系统重构与召回策略优化"
    assert _match_term_to_blob("推荐系统", blob, set()) == 1


def test_no_match():
    assert _match_term_to_blob("量子计算", "负责前端页面开发", set()) == 0


# ---------- _ats_to_jdreq ----------


def test_ats_to_jdreq_maps_fields():
    ats = ATSProfile(
        job_title="高级后端工程师",
        required_skills=["python", "redis"],
        preferred_skills=["go"],
        responsibilities=["设计高可用系统"],
        culture_keywords=["owner"],
    )
    jd = _ats_to_jdreq(ats)
    assert jd.position_title == "高级后端工程师"
    assert jd.hard_skills == ["python", "redis"]
    assert jd.soft_skills == ["go"]
    assert "设计高可用系统" in jd.responsibilities


# ---------- _build_gap_text ----------


def test_gap_text_when_fully_covered():
    jd = JDRequirements(hard_skills=["python"], soft_skills=[], keywords=["python"])
    per_card = [PerCardScore(card_id=1, score=80, matched=["python"], missing=[])]
    text = _build_gap_text(jd, per_card)
    assert "覆盖" in text


def test_gap_text_lists_missing_terms():
    jd = JDRequirements(hard_skills=["python", "redis"], keywords=["python", "redis"])
    per_card = [
        PerCardScore(card_id=1, score=40, matched=["python"], missing=["redis"])
    ]
    text = _build_gap_text(jd, per_card)
    assert "redis" in text


# ---------- _match_level ----------


def test_match_level_boundaries():
    assert _match_level(85) == "高度匹配"
    assert _match_level(60) == "基本匹配"
    assert _match_level(50) == "部分匹配"
    assert _match_level(30) == "匹配度低"


# ---------- compute_match ----------


def test_compute_match_no_cards():
    jd = JDRequirements(hard_skills=["python"], keywords=["python"])
    result = compute_match([], jd)
    assert result["overall"] == 0.0
    assert result["per_card"] == []


def test_compute_match_fuses_local_and_llm():
    jd = JDRequirements(hard_skills=["python"], soft_skills=[], keywords=["python"])
    cards = [
        {
            "id": 1,
            "title": "后端开发",
            "raw_text": "负责 python 服务开发",
            "tags": [],
        }
    ]
    result = compute_match(cards, jd, llm_scores={1: 100.0})
    assert result["overall"] >= 60
    assert result["per_card"][0].card_id == 1
    assert "python" in result["per_card"][0].matched


# ---------- 单卡回填: 整份简历识别 ----------


def test_looks_like_full_resume_by_date_ranges():
    from app.tools.db_tools import _looks_like_full_resume

    text = (
        "2019.03 - 2021.06  字节跳动  高级后端工程师\n"
        "负责推荐系统架构\n"
        "2021.07 - 至今  美团  后端专家\n"
        "负责外卖调度系统\n"
    )
    assert _looks_like_full_resume(text, min_chars=30) is True


def test_looks_like_full_resume_by_markers():
    from app.tools.db_tools import _looks_like_full_resume

    text = (
        "工作经历\n某某公司\n负责 xxx\n项目经历\n某某项目\n负责 yyy\n教育背景\n某大学\n"
    )
    assert _looks_like_full_resume(text, min_chars=30) is True


def test_looks_like_full_resume_by_material_library_headers():
    from app.tools.db_tools import _looks_like_full_resume

    text = (
        "# 个人经历与能力素材库\n"
        "## 一、经历梳理汇总\n"
        "#### 经历1：政府云资源交付项目管理\n"
        "内容1\n"
        "#### 经历2：政府信息化咨询项目\n"
        "内容2\n"
        "#### 经历3：智能无人跟随小车项目\n"
        "内容3\n"
    )
    assert _looks_like_full_resume(text, min_chars=30) is True


def test_single_entry_card_not_treated_as_resume():
    from app.tools.db_tools import _looks_like_full_resume

    text = "负责电商交易系统的订单模块开发与性能优化，参与双十一大促保障。"
    assert _looks_like_full_resume(text) is False


def test_short_text_not_treated_as_resume():
    from app.tools.db_tools import _looks_like_full_resume

    assert _looks_like_full_resume("负责推荐系统重构") is False


def test_rebuild_entry_text_joins_achievements():
    from app.tools.db_tools import _rebuild_entry_text

    entry = {
        "company": "某公司",
        "role": "后端工程师",
        "period": "2020.01 - 2022.06",
        "summary": "负责核心服务开发",
        "achievements": [
            {
                "title": "重构订单服务",
                "action": {"main": "拆分模块"},
                "result": "性能提升 30%",
            },
        ],
    }
    text = _rebuild_entry_text(entry)
    assert "某公司 / 后端工程师 / 2020.01 - 2022.06" in text
    assert "性能提升 30%" in text


def test_rebuild_entry_text_empty_achievements():
    from app.tools.db_tools import _rebuild_entry_text

    text = _rebuild_entry_text({"company": "A", "summary": "总括"})
    assert text == "A\n总括"
