"""
fuse_gap_scores 与 db_tools 回填辅助函数单元测试（无 LLM / 无 DB 依赖）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.jobcraft import ATSProfile
from app.tools.jobcraft_analyze import fuse_gap_scores


# ---------- fuse_gap_scores ----------


def _sample_cards():
    return [
        {
            "id": 1,
            "title": "后端开发",
            "raw_text": "负责 python 服务开发与 redis 缓存优化",
            "tags": ["python", "redis"],
        },
        {
            "id": 2,
            "title": "前端开发",
            "raw_text": "负责 React 页面开发",
            "tags": ["react"],
        },
    ]


def _sample_ats():
    return ATSProfile(
        job_title="高级后端工程师",
        required_skills=["python", "redis"],
        preferred_skills=["go"],
    )


def test_fuse_gap_scores_fuses_local_and_llm():
    per_card_raw = [
        {"card_id": 1, "score": 80, "action": "good"},
        {"card_id": 2, "score": 50, "action": "supplement"},
    ]
    result = fuse_gap_scores(_sample_ats(), _sample_cards(), per_card_raw)

    # 卡1: 本地 100（python+redis 都命中）* 0.4 + 80 * 0.6 = 88
    assert result["per_card"][0]["card_id"] == 1
    assert result["per_card"][0]["local_score"] == 100.0
    assert result["per_card"][0]["llm_score"] == 80.0
    assert result["per_card"][0]["score"] == 88.0

    assert result["overall_score"] == 59.0
    assert result["score_weights"] == {"local": 0.4, "llm": 0.6}
    assert result["match_level"] in ("高度匹配", "基本匹配", "部分匹配", "匹配度低")


def test_fuse_gap_scores_empty_per_card():
    result = fuse_gap_scores(_sample_ats(), _sample_cards(), [])
    assert result["per_card"] == []
    assert result["overall_score"] == 0.0


def test_fuse_gap_scores_ignores_unknown_card_id():
    per_card_raw = [{"card_id": 999, "score": 70, "action": "good"}]
    result = fuse_gap_scores(_sample_ats(), _sample_cards(), per_card_raw)
    assert result["per_card"][0]["local_score"] == 0.0
    assert result["per_card"][0]["score"] == 42.0  # 0*0.4 + 70*0.6


def test_fuse_gap_scores_missing_card_does_not_fail():
    result = fuse_gap_scores(_sample_ats(), [], [])
    assert result["per_card"] == []
    assert result["overall_score"] == 0.0


# ---------- _rebuild_entry_text ----------


def test_rebuild_entry_text_with_all_fields():
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
    assert "重构订单服务（性能提升 30%）" in text
