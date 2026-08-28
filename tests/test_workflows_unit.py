"""
Workflow 单元测试（无真实 LLM / DB 调用）

覆盖：
  1. interview_review_flow  — 面试复盘 Multi-Agent Workflow
  2. job_analysis_flow       — 岗位分析 Workflow（5 个入口函数）
  3. extract_flow            — 结构化抽取 Workflow（4 个入口函数）
  4. interview_prep_flow     — 面试准备 Workflow
  5. question_table_flow     — 问题表生成 Workflow
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============================================================
#  Helpers
# ============================================================


def _fake_record(record_id=1):
    return {
        "id": record_id,
        "title": "一面复盘",
        "company": "字节跳动",
        "position": "后端工程师",
        "round_type": "技术面",
        "raw_text": (
            "面试官: 请介绍一下你自己\n"
            "候选人: 我是一名后端工程师\n"
            "面试官: 说说你做过的项目\n"
            "候选人: 我做过推荐系统\n"
        ),
        "job_analysis_id": 10,
    }


def _fake_qa_pairs():
    return [
        {
            "sequence": 1,
            "speaker": "面试官",
            "question_text": "请介绍一下你自己",
            "my_answer": "我是一名后端工程师",
            "start_time": "",
        },
        {
            "sequence": 2,
            "speaker": "面试官",
            "question_text": "说说你做过的项目",
            "my_answer": "我做过推荐系统",
            "start_time": "",
        },
    ]


def _fake_job_context():
    return {
        "jd_text": "负责后端开发",
        "cards": [
            {"id": 1, "title": "推荐系统", "raw_text": "做过推荐系统优化"},
            {"id": 2, "title": "数据平台", "raw_text": "搭建数据平台"},
        ],
    }


def _fake_ats_profile():
    return {
        "job_title": "后端工程师",
        "required_skills": ["Python", "Go"],
        "preferred_skills": ["Kafka"],
        "dimension_requirements": [],
    }


def _fake_job_analysis_db(job_id=10):
    return {
        "id": job_id,
        "user_id": 1,
        "company": "字节跳动",
        "position": "后端工程师",
        "jd_text": "负责后端开发",
        "jd_requirements": _fake_ats_profile(),
        "dimension_requirements": [],
    }


# ============================================================
#  1. interview_review_flow
# ============================================================


class TestInterviewReviewFlow:
    """面试复盘 Workflow 测试"""

    def test_run_workflow_normal(self, monkeypatch):
        """正常路径：mock 所有 Agent，完整走一遍"""
        from app.workflows.interview_review_flow import run_interview_review_workflow

        # mock db_tools
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.get_interview_record",
            lambda rid: _fake_record(rid),
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow._get_job_context",
            lambda record, user_id=1: _fake_job_context(),
        )

        # mock RouterAgent — 只返回新增字段，避免 LangGraph 并发写 record_id
        def fake_router_run(self, state):
            return {"classified": {"tech": [1], "soft": [2]}}

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.RouterAgent.run", fake_router_run
        )

        # mock TechAnalyzer
        def fake_tech_run(self, state):
            return {
                "tech_results": [
                    {
                        "sequence": 1,
                        "score": 80,
                        "dimension": "D1 技术深度",
                        "level": "L4",
                        "intent": "考察技术基础",
                        "expected_answer": "应描述技术选型",
                        "feedback": ["缺少性能数据"],
                        "suggestions": ["补充量化指标"],
                        "related_card_id": 1,
                    }
                ]
            }

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.TechAnalyzer.run", fake_tech_run
        )

        # mock SoftAnalyzer
        def fake_soft_run(self, state):
            return {
                "soft_results": [
                    {
                        "sequence": 2,
                        "score": 70,
                        "dimension": "D7 协作沟通",
                        "level": "L3",
                        "intent": "考察项目经验",
                        "expected_answer": "应描述协作过程",
                        "feedback": ["沟通偏简略"],
                        "suggestions": ["增加细节"],
                        "related_card_id": 2,
                    }
                ]
            }

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.SoftAnalyzer.run", fake_soft_run
        )

        # mock GateAgent
        def fake_gate_run(self, state):
            return {"gate_report": {"status": "ok"}}

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.GateAgent.run", fake_gate_run
        )

        # mock DB 写入
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.update_interview_record_analysis",
            lambda rid, data: None,
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.delete_interview_qa_pairs_by_record",
            lambda rid: None,
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.insert_interview_qa_pair",
            lambda data: 1,
        )

        result = run_interview_review_workflow(
            record_id=1, selected_sequences=[1, 2], user_id=1
        )
        assert result is not None
        assert "overall_score" in result
        assert result["company"] == "字节跳动"
        assert len(result["questions"]) == 2

    def test_run_workflow_no_selected_qa_pairs(self, monkeypatch):
        """边界：selected_sequences 不匹配任何 qa_pair"""
        from app.workflows.interview_review_flow import run_interview_review_workflow

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.get_interview_record",
            lambda rid: _fake_record(rid),
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow._get_job_context",
            lambda record, user_id=1: _fake_job_context(),
        )

        # 选择不存在的 sequence → _load_data 会抛 ValueError
        with pytest.raises(ValueError, match="未选中任何有效问题"):
            run_interview_review_workflow(
                record_id=1, selected_sequences=[999], user_id=1
            )

    def test_run_workflow_record_not_found(self, monkeypatch):
        """边界：record_id 不存在"""
        from app.workflows.interview_review_flow import run_interview_review_workflow

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.get_interview_record",
            lambda rid: None,
        )

        with pytest.raises(ValueError, match="面试记录不存在"):
            run_interview_review_workflow(
                record_id=999, selected_sequences=[1], user_id=1
            )

    def test_run_workflow_tech_only(self, monkeypatch):
        """只有技术类问题，无 soft 分支"""
        from app.workflows.interview_review_flow import run_interview_review_workflow

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.get_interview_record",
            lambda rid: _fake_record(rid),
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow._get_job_context",
            lambda record, user_id=1: _fake_job_context(),
        )

        def fake_router_run(self, state):
            return {"classified": {"tech": [1, 2], "soft": []}}

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.RouterAgent.run", fake_router_run
        )

        def fake_tech_run(self, state):
            return {
                "tech_results": [
                    {
                        "sequence": 1,
                        "score": 85,
                        "dimension": "D1 技术深度",
                        "level": "L4",
                        "intent": "技术",
                        "expected_answer": "技术答案",
                        "feedback": [],
                        "suggestions": [],
                        "related_card_id": None,
                    },
                    {
                        "sequence": 2,
                        "score": 75,
                        "dimension": "D3 问题拆解",
                        "level": "L3",
                        "intent": "拆解",
                        "expected_answer": "拆解答案",
                        "feedback": [],
                        "suggestions": [],
                        "related_card_id": None,
                    },
                ]
            }

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.TechAnalyzer.run", fake_tech_run
        )

        def fake_gate_run(self, state):
            return {"gate_report": {"status": "ok"}}

        monkeypatch.setattr(
            "app.workflows.interview_review_flow.GateAgent.run", fake_gate_run
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.update_interview_record_analysis",
            lambda rid, data: None,
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.delete_interview_qa_pairs_by_record",
            lambda rid: None,
        )
        monkeypatch.setattr(
            "app.workflows.interview_review_flow.db_tools.insert_interview_qa_pair",
            lambda data: 1,
        )

        result = run_interview_review_workflow(
            record_id=1, selected_sequences=[1, 2], user_id=1
        )
        assert result is not None
        assert result["overall_score"] == 80


# ============================================================
#  2. job_analysis_flow
# ============================================================


class TestJobAnalysisFlow:
    """岗位分析 Workflow 测试"""

    def test_step1_workflow_normal(self, monkeypatch):
        """Step1: ATS 解析 + 推荐卡片"""
        from app.workflows.job_analysis_flow import run_step1_workflow

        def fake_ats_run(self, data):
            return {
                "ats": _fake_ats_profile(),
                "recommended_cards": [{"id": 1, "title": "推荐系统", "match": 0.8}],
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.AtsRecommendAgent.run", fake_ats_run
        )

        result = run_step1_workflow(
            user_id=1,
            company="字节",
            position="后端",
            jd_text="负责后端开发",
            cards=[{"id": 1, "raw_text": "做过推荐系统"}],
        )
        assert result is not None
        assert "ats" in result

    def test_step2_workflow_normal(self, monkeypatch):
        """Step2: 缺口分析 + 润色建议"""
        from app.workflows.job_analysis_flow import run_step2_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_card",
            lambda cid: {
                "id": cid,
                "title": "卡",
                "raw_text": "文本",
                "is_active": True,
            },
        )

        def fake_gap_run(self, data):
            return {
                "gap_polish": {
                    "per_card": [{"card_id": 1, "gap_score": 70}],
                    "global_suggestions": ["提升表达"],
                }
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.GapPolishAgent.run", fake_gap_run
        )

        def fake_fuse(ats, selected_cards, per_card_raw):
            return {
                "per_card": [{"card_id": 1, "score": 75}],
                "overall_score": 75,
                "match_level": "中",
                "score_weights": {"local": 0.4, "llm": 0.6},
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.jobcraft_analyze.fuse_gap_scores",
            fake_fuse,
        )

        result = run_step2_workflow(job_analysis_id=10, card_ids=[1])
        assert result is not None
        assert "per_card" in result
        assert result["overall_score"] == 75

    def test_step2_workflow_analysis_not_found(self, monkeypatch):
        """Step2: job_analysis 不存在"""
        from app.workflows.job_analysis_flow import run_step2_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_job_analysis",
            lambda jid: None,
        )

        with pytest.raises(ValueError, match="不存在"):
            run_step2_workflow(job_analysis_id=999, card_ids=[1])

    def test_legacy_workflow_normal(self, monkeypatch):
        """旧版完整岗位分析"""
        from app.schemas.jobcraft import PerCardScore
        from app.workflows.job_analysis_flow import run_job_analysis_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_card",
            lambda cid: {
                "id": cid,
                "title": "卡",
                "raw_text": "文本",
                "is_active": True,
            },
        )

        def fake_jd_ats_run(self, data):
            return {"ats": _fake_ats_profile()}

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.JdAtsAgent.run", fake_jd_ats_run
        )

        def fake_sm_run(self, data):
            return {
                "llm_match_items": {
                    "1": {"match": 80.0},
                    "2": {"match": 60.0},
                }
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.ScoreMatchAgent.run", fake_sm_run
        )

        def fake_compute_match(cards, jd_req, llm_scores=None):
            return {
                "overall": 72,
                "per_card": [
                    PerCardScore(
                        card_id=1,
                        score=80,
                        local_score=70,
                        llm_score=85,
                        matched=[],
                        missing=[],
                    ),
                    PerCardScore(
                        card_id=2,
                        score=64,
                        local_score=60,
                        llm_score=67,
                        matched=[],
                        missing=[],
                    ),
                ],
                "gap": {"missing": ["Kafka"]},
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.jobcraft_analyze.compute_match",
            fake_compute_match,
        )

        def fake_sug_run(self, data):
            return {
                "suggestions": {
                    "gap_analysis": "缺少分布式经验",
                    "gap_items": ["Kafka"],
                    "suggestions": [],
                }
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.SugAgent.run", fake_sug_run
        )

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.insert_job_analysis",
            lambda data: 42,
        )
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.upsert_job_mapping",
            lambda jid, cid: None,
        )

        result = run_job_analysis_workflow(
            user_id=1,
            company="字节",
            position="后端",
            jd_text="负责后端开发",
            card_ids=[1, 2],
        )
        assert result is not None
        assert result["job_analysis_id"] == 42
        assert result["match_score"] == 72

    def test_legacy_workflow_no_cards(self, monkeypatch):
        """旧版分析：所有卡片不可用"""
        from app.workflows.job_analysis_flow import run_job_analysis_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_card",
            lambda cid: None,
        )

        with pytest.raises(ValueError, match="所选卡片均不可用"):
            run_job_analysis_workflow(
                user_id=1,
                company="字节",
                position="后端",
                jd_text="负责后端开发",
                card_ids=[1],
            )

    def test_analyze_ats_workflow_normal(self, monkeypatch):
        """仅 ATS 解析"""
        from app.workflows.job_analysis_flow import run_analyze_ats_workflow

        def fake_jd_ats_run(self, data):
            return {"ats": _fake_ats_profile()}

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.JdAtsAgent.run", fake_jd_ats_run
        )

        result = run_analyze_ats_workflow(jd_text="负责后端开发")
        assert result is not None
        assert result["job_title"] == "后端工程师"

    def test_resume_preview_workflow_normal(self, monkeypatch):
        """简历预览重新匹配"""
        from app.workflows.job_analysis_flow import run_resume_preview_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_card",
            lambda cid: {
                "id": cid,
                "title": "卡",
                "raw_text": "文本",
                "is_active": True,
            },
        )

        def fake_jd_ats_run(self, data):
            return {"ats": _fake_ats_profile()}

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.JdAtsAgent.run", fake_jd_ats_run
        )

        def fake_sm_run(self, data):
            return {
                "llm_match_items": {
                    "1": {"match": 80.0},
                }
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.ScoreMatchAgent.run", fake_sm_run
        )

        def fake_compute_match(cards, jd_req, llm_scores=None):
            return {
                "overall": 78,
                "per_card": [
                    {
                        "card_id": 1,
                        "score": 78,
                        "local_score": 70,
                        "llm_score": 85,
                        "matched": [],
                        "missing": [],
                    },
                ],
            }

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.jobcraft_analyze.compute_match",
            fake_compute_match,
        )

        def fake_gen_md(**kwargs):
            return "# 简历\n\n这是生成的简历内容"

        monkeypatch.setattr(
            "app.tools.jobcraft_resume_gen.generate_resume_markdown", fake_gen_md
        )

        result = run_resume_preview_workflow(job_id=10, selected_card_ids=[1])
        assert result is not None
        assert result["job_analysis_id"] == 10
        assert "简历" in result["resume_markdown"]
        assert result["match_score"] == 78

    def test_resume_preview_no_cards(self, monkeypatch):
        """简历预览：无可用卡片"""
        from app.workflows.job_analysis_flow import run_resume_preview_workflow

        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        monkeypatch.setattr(
            "app.workflows.job_analysis_flow.db_tools.get_card",
            lambda cid: None,
        )

        with pytest.raises(ValueError, match="无可用经历卡"):
            run_resume_preview_workflow(job_id=10, selected_card_ids=[1])


# ============================================================
#  3. extract_flow
# ============================================================


class TestExtractFlow:
    """结构化抽取 Workflow 测试"""

    def test_extract_structured_normal(self, monkeypatch):
        """正常抽取结构化成就"""
        from app.workflows.extract_flow import run_extract_structured_workflow

        def fake_run(self, data):
            return {
                "cache": {
                    "summary": "负责推荐系统",
                    "achievements": [{"title": "重构召回", "result": "CTR+20%"}],
                }
            }

        monkeypatch.setattr(
            "app.workflows.extract_flow.ExtractStructuredAgent.run", fake_run
        )

        result = run_extract_structured_workflow(raw_text="我负责推荐系统")
        assert result is not None
        assert result["summary"] == "负责推荐系统"

    def test_extract_structured_empty_input(self, monkeypatch):
        """空输入抽取"""
        from app.workflows.extract_flow import run_extract_structured_workflow

        def fake_run(self, data):
            return {"cache": None}

        monkeypatch.setattr(
            "app.workflows.extract_flow.ExtractStructuredAgent.run", fake_run
        )

        result = run_extract_structured_workflow(raw_text="")
        assert result is None

    def test_recommend_tags_normal(self, monkeypatch):
        """正常推荐标签"""
        from app.workflows.extract_flow import run_recommend_tags_workflow

        def fake_run(self, data):
            return {"tags": ["推荐系统", "Python", "机器学习"]}

        monkeypatch.setattr(
            "app.workflows.extract_flow.RecommendTagsAgent.run", fake_run
        )

        result = run_recommend_tags_workflow(raw_text="我做推荐系统开发")
        assert result == ["推荐系统", "Python", "机器学习"]

    def test_recommend_tags_empty(self, monkeypatch):
        """空输入标签推荐"""
        from app.workflows.extract_flow import run_recommend_tags_workflow

        def fake_run(self, data):
            return {"tags": []}

        monkeypatch.setattr(
            "app.workflows.extract_flow.RecommendTagsAgent.run", fake_run
        )

        result = run_recommend_tags_workflow(raw_text="")
        assert result == []

    def test_parse_resume_entries_normal(self, monkeypatch):
        """正常解析简历条目"""
        from app.workflows.extract_flow import run_parse_resume_entries_workflow

        def fake_run(self, data):
            return {
                "entries": [
                    {"company": "字节", "role": "工程师", "title": "推荐系统"},
                ]
            }

        monkeypatch.setattr(
            "app.workflows.extract_flow.ParseResumeEntriesAgent.run", fake_run
        )

        result = run_parse_resume_entries_workflow(resume_text="简历内容")
        assert len(result) == 1
        assert result[0]["company"] == "字节"

    def test_backfill_workflow_normal(self, monkeypatch):
        """Backfill 正常拆卡"""
        from app.workflows.extract_flow import run_backfill_workflow

        def fake_list_full(user_id, min_chars):
            return [
                {"id": 1, "title": "长卡", "raw_text": "很长的文本" * 50},
            ]

        monkeypatch.setattr(
            "app.workflows.extract_flow.db_tools.list_full_resume_cards", fake_list_full
        )
        monkeypatch.setattr(
            "app.workflows.extract_flow.db_tools.list_cards",
            lambda uid, include_inactive=False: [{"id": 1}],
        )

        def fake_parse_run(self, data):
            return {
                "entries": [
                    {"company": "A", "title": "经历1"},
                    {"company": "B", "title": "经历2"},
                ]
            }

        monkeypatch.setattr(
            "app.workflows.extract_flow.ParseResumeEntriesAgent.run", fake_parse_run
        )
        monkeypatch.setattr(
            "app.workflows.extract_flow.db_tools.split_resume_card_by_entries",
            lambda uid, card, entries: [10, 11],
        )

        result = run_backfill_workflow(user_id=1, min_chars=100)
        assert result["checked"] >= 1
        assert len(result["splits"]) == 1
        assert result["splits"][0]["created_ids"] == [10, 11]

    def test_backfill_workflow_no_cards(self, monkeypatch):
        """Backfill：无可拆卡片"""
        from app.workflows.extract_flow import run_backfill_workflow

        monkeypatch.setattr(
            "app.workflows.extract_flow.db_tools.list_full_resume_cards",
            lambda uid, min_chars: [],
        )

        result = run_backfill_workflow(user_id=1)
        assert result["checked"] == 0
        assert result["splits"] == []


# ============================================================
#  4. interview_prep_flow
# ============================================================


class TestInterviewPrepFlow:
    """面试准备 Workflow 测试"""

    def _mock_prep_deps(self, monkeypatch):
        """统一 mock 面试准备依赖"""
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_card",
            lambda cid: {
                "id": cid,
                "title": "推荐系统",
                "raw_text": "做过推荐系统",
                "is_active": True,
            },
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_card_versions_by_source",
            lambda source, jid: [],
        )

    def test_prep_workflow_normal(self, monkeypatch):
        """正常面试准备"""
        from app.workflows.interview_prep_flow import run_interview_prep_workflow

        self._mock_prep_deps(monkeypatch)

        def fake_build_prompt(**kwargs):
            return "这是一个面试准备 prompt"

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.interview_pre._build_interview_prompt",
            fake_build_prompt,
        )

        def fake_agent_run(self, data):
            return {
                "prep_result": {
                    "job_analysis_id": 10,
                    "round_type": "技术面",
                    "duration": "15 分钟",
                    "elevator_pitch": "我是后端工程师",
                    "dimension_questions": [
                        {
                            "dimension": "D1 技术深度",
                            "question": "说说技术选型",
                            "answer_points": ["A", "B"],
                        }
                    ],
                    "full_version": "完整版本内容",
                    "html_content": "<div>预览</div>",
                }
            }

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.InterviewPrepAgent.run", fake_agent_run
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.insert_interview_prep",
            lambda data: 1,
        )

        result = run_interview_prep_workflow(
            job_analysis_id=10,
            round_type="技术面",
            card_ids=[1],
            user_id=1,
        )
        assert result is not None
        assert result["duration"] == "15 分钟"
        assert result["round_type"] == "技术面"
        assert result["job_analysis_id"] == 10

    def test_prep_workflow_analysis_not_found(self, monkeypatch):
        """job_analysis 不存在"""
        from app.workflows.interview_prep_flow import run_interview_prep_workflow

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_job_analysis",
            lambda jid: None,
        )

        with pytest.raises(ValueError, match="不存在"):
            run_interview_prep_workflow(
                job_analysis_id=999,
                round_type="技术面",
                card_ids=[1],
            )

    def test_prep_workflow_no_cards(self, monkeypatch):
        """所选经历卡不可用"""
        from app.workflows.interview_prep_flow import run_interview_prep_workflow

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_card",
            lambda cid: None,
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.get_card_versions_by_source",
            lambda source, jid: [],
        )

        with pytest.raises(ValueError, match="所选经历卡不可用"):
            run_interview_prep_workflow(
                job_analysis_id=10,
                round_type="技术面",
                card_ids=[1],
            )

    def test_prep_workflow_with_optional_params(self, monkeypatch):
        """带可选参数的面试准备"""
        from app.workflows.interview_prep_flow import run_interview_prep_workflow

        self._mock_prep_deps(monkeypatch)

        def fake_build_prompt(**kwargs):
            assert kwargs.get("company_research") is not None
            assert kwargs.get("resume_markdown") == "# 简历"
            assert kwargs.get("previous_review_summary") == "上轮总结"
            return "prompt"

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.interview_pre._build_interview_prompt",
            fake_build_prompt,
        )

        def fake_agent_run(self, data):
            return {
                "prep_result": {
                    "job_analysis_id": 10,
                    "round_type": "HR面",
                    "duration": "10 分钟",
                    "elevator_pitch": "pitch",
                    "dimension_questions": [],
                    "full_version": "full",
                    "html_content": "",
                }
            }

        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.InterviewPrepAgent.run", fake_agent_run
        )
        monkeypatch.setattr(
            "app.workflows.interview_prep_flow.db_tools.insert_interview_prep",
            lambda data: 1,
        )

        result = run_interview_prep_workflow(
            job_analysis_id=10,
            round_type="HR面",
            card_ids=[1],
            user_id=1,
            submission_id=5,
            company_research={"basic": {"name": "字节"}},
            resume_markdown="# 简历",
            previous_review_summary="上轮总结",
        )
        assert result is not None
        assert result["round_type"] == "HR面"


# ============================================================
#  5. question_table_flow
# ============================================================


class TestQuestionTableFlow:
    """问题表生成 Workflow 测试"""

    def test_question_table_normal(self, monkeypatch):
        """正常生成问题表"""
        from app.workflows.question_table_flow import run_question_table_workflow

        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_interview_record",
            lambda rid: _fake_record(rid),
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        # mock 解析函数，返回预设的 QA 对
        monkeypatch.setattr(
            "app.workflows.question_table_flow._parse_dialogue",
            lambda text: [
                {"speaker": "面试官", "content": "问题1", "time": ""},
                {"speaker": "候选人", "content": "回答1", "time": ""},
            ],
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow._build_qa_pairs",
            lambda dialogue: _fake_qa_pairs(),
        )

        def fake_agent_run(self, data):
            return {
                "intent_by_seq": {
                    1: {
                        "intent": "考察自我介绍",
                        "dimension": "D8 职业规划",
                        "level": "L2",
                    },
                    2: {
                        "intent": "考察项目经验",
                        "dimension": "D1 技术深度",
                        "level": "L4",
                    },
                }
            }

        monkeypatch.setattr(
            "app.workflows.question_table_flow.QuestionTableAgent.run", fake_agent_run
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.delete_interview_qa_pairs_by_record",
            lambda rid: None,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.insert_interview_qa_pair",
            lambda data: 1,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.update_interview_record_status",
            lambda rid, status: None,
        )

        result = run_question_table_workflow(record_id=1, user_id=1)
        assert len(result) == 2
        assert result[0]["dimension"] == "D8 职业规划"
        assert result[1]["level"] == "L4"

    def test_question_table_record_not_found(self, monkeypatch):
        """record 不存在"""
        from app.workflows.question_table_flow import run_question_table_workflow

        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_interview_record",
            lambda rid: None,
        )

        with pytest.raises(ValueError, match="面试记录不存在"):
            run_question_table_workflow(record_id=999)

    def test_question_table_empty_qa_pairs(self, monkeypatch):
        """对话无法解析出 QA 对"""
        from app.workflows.question_table_flow import run_question_table_workflow

        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_interview_record",
            lambda rid: {"id": rid, "raw_text": "", "job_analysis_id": None},
        )

        # 无 QA 对时 agent 返回空 intent
        def fake_agent_run(self, data):
            return {"intent_by_seq": {}}

        monkeypatch.setattr(
            "app.workflows.question_table_flow.QuestionTableAgent.run", fake_agent_run
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.delete_interview_qa_pairs_by_record",
            lambda rid: None,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.insert_interview_qa_pair",
            lambda data: 1,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.update_interview_record_status",
            lambda rid, status: None,
        )

        result = run_question_table_workflow(record_id=1, user_id=1)
        # raw_text 为空时 _parse_dialogue 可能返回空，qa_pairs 为空
        # generate_intents 会返回空 dict，persist 返回空列表
        assert isinstance(result, list)

    def test_question_table_with_job_analysis(self, monkeypatch):
        """有关联 job_analysis，jd_text 应被填充"""
        from app.workflows.question_table_flow import run_question_table_workflow

        record = _fake_record(1)
        record["job_analysis_id"] = 10

        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_interview_record",
            lambda rid: record,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.get_job_analysis",
            lambda jid: _fake_job_analysis_db(jid),
        )
        # mock 解析函数，返回预设的 QA 对
        monkeypatch.setattr(
            "app.workflows.question_table_flow._parse_dialogue",
            lambda text: [
                {"speaker": "面试官", "content": "问题1", "time": ""},
                {"speaker": "候选人", "content": "回答1", "time": ""},
            ],
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow._build_qa_pairs",
            lambda dialogue: _fake_qa_pairs(),
        )

        captured_inputs = []

        def fake_agent_run(self, data):
            captured_inputs.append(data)
            return {
                "intent_by_seq": {
                    1: {
                        "intent": "自我介绍",
                        "dimension": "D8 职业规划",
                        "level": "L2",
                    },
                    2: {"intent": "项目", "dimension": "D1 技术深度", "level": "L3"},
                }
            }

        monkeypatch.setattr(
            "app.workflows.question_table_flow.QuestionTableAgent.run", fake_agent_run
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.delete_interview_qa_pairs_by_record",
            lambda rid: None,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.insert_interview_qa_pair",
            lambda data: 1,
        )
        monkeypatch.setattr(
            "app.workflows.question_table_flow.db_tools.update_interview_record_status",
            lambda rid, status: None,
        )

        result = run_question_table_workflow(record_id=1, user_id=1)
        assert len(result) == 2
        # 验证 agent 收到了 jd_text
        assert captured_inputs[0]["jd_text"] == "负责后端开发"
