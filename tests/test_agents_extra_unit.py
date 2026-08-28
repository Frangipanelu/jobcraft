"""
Agent 节点额外 Mock 单测（无真实 LLM 调用）

通过 monkeypatch 替换各 agent 模块内的 invoke_structured，
验证 agent 的输入→输出转换逻辑与容错分支。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- RouterAgent ----------


def test_router_agent_empty_input(monkeypatch):
    from app.agents.router_agent import RouterAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(classified=[])

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run({"selected_qa_pairs": []})
    assert out["classified"] == {"tech": [], "soft": []}


def test_router_agent_with_mock_llm(monkeypatch):
    from app.agents.router_agent import RouterAgent

    fake = {
        "classified": [
            {"sequence": 1, "category": "tech"},
            {"sequence": 2, "category": "soft"},
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run(
        {
            "selected_qa_pairs": [
                {"sequence": 1, "question_text": "聊聊你的技术栈"},
                {"sequence": 2, "question_text": "你如何与团队协作？"},
            ]
        }
    )
    assert out["classified"]["tech"] == [1]
    assert out["classified"]["soft"] == [2]


def test_router_agent_unknown_category_to_soft(monkeypatch):
    from app.agents.router_agent import RouterAgent

    fake = {
        "classified": [
            {"sequence": 1, "category": "unknown"},
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.base_agent.invoke_structured", _fake_invoke)
    out = RouterAgent().run(
        {"selected_qa_pairs": [{"sequence": 1, "question_text": "问题"}]}
    )
    assert out["classified"]["soft"] == [1]


# ---------- TechAnalyzer ----------


def test_tech_analyzer_empty_input(monkeypatch):
    from app.agents.tech_analyzer import TechAnalyzer

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.tech_analyzer.llm_call", _fail)
    out = TechAnalyzer().run({"classified": {"tech": [], "soft": []}})
    assert out["tech_results"] == []


def test_tech_analyzer_with_mock_llm(monkeypatch):
    from app.agents.tech_analyzer import TechAnalyzer

    fake = {
        "analyses": [
            {
                "sequence": 1,
                "dimension": "D1 技术深度",
                "level": "L4",
                "intent": "考察系统设计能力",
                "expected_answer": "核心观点：需要高可用设计",
                "score": 85,
                "feedback": ["回答较完整"],
                "suggestions": ["可以补充更多细节"],
                "related_card_id": 1,
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.tech_analyzer.llm_call", _fake_invoke)
    out = TechAnalyzer().run(
        {
            "classified": {"tech": [1], "soft": []},
            "selected_qa_pairs": [
                {
                    "sequence": 1,
                    "question_text": "聊聊你的项目经验",
                    "my_answer": "我负责了推荐系统开发",
                    "start_time": "2:12",
                }
            ],
            "position": "后端工程师",
            "company": "字节跳动",
            "round_type": "技术面",
        }
    )
    assert len(out["tech_results"]) == 1
    assert out["tech_results"][0]["score"] == 85


# ---------- SoftAnalyzer ----------


def test_soft_analyzer_empty_input(monkeypatch):
    from app.agents.soft_analyzer import SoftAnalyzer

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.soft_analyzer.llm_call", _fail)
    out = SoftAnalyzer().run({"classified": {"tech": [], "soft": []}})
    assert out["soft_results"] == []


def test_soft_analyzer_with_mock_llm(monkeypatch):
    from app.agents.soft_analyzer import SoftAnalyzer

    fake = {
        "analyses": [
            {
                "sequence": 1,
                "dimension": "D7 协作沟通",
                "level": "L3",
                "intent": "考察沟通能力",
                "expected_answer": "结构化表达，推动对齐",
                "score": 70,
                "feedback": ["表达清晰但缺少说服力"],
                "suggestions": ["可以加入更多具体案例"],
                "related_card_id": None,
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.soft_analyzer.llm_call", _fake_invoke)
    out = SoftAnalyzer().run(
        {
            "classified": {"tech": [], "soft": [1]},
            "selected_qa_pairs": [
                {
                    "sequence": 1,
                    "question_text": "你如何与团队协作？",
                    "my_answer": "我们定期开会讨论进度",
                    "start_time": "5:30",
                }
            ],
            "position": "产品经理",
            "company": "腾讯",
            "round_type": "业务面",
        }
    )
    assert len(out["soft_results"]) == 1
    assert out["soft_results"][0]["score"] == 70


# ---------- GateAgent ----------


def test_gate_agent_empty_input(monkeypatch):
    from app.agents.gate_agent import GateAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.gate_agent.GateAgent._invoke", _fail)
    out = GateAgent().run({"tech_results": [], "soft_results": []})
    assert out["gate_report"]["issues"] == []
    assert out["gate_report"]["overall_quality"] == "high"


def test_gate_agent_with_mock_llm(monkeypatch):
    from app.agents.gate_agent import GateAgent

    fake = {
        "issues": [
            {
                "type": "contradiction",
                "description": "两个技术问题评分差异过大",
                "related_sequences": [1, 2],
            }
        ],
        "overall_quality": "medium",
    }

    def _fake_invoke(self_agent, schema, prompt):
        return schema(**fake)

    monkeypatch.setattr("app.agents.gate_agent.GateAgent._invoke", _fake_invoke)
    out = GateAgent().run(
        {
            "tech_results": [
                {"sequence": 1, "score": 90, "dimension": "D1"},
                {"sequence": 2, "score": 40, "dimension": "D1"},
            ],
            "soft_results": [],
        }
    )
    assert len(out["gate_report"]["issues"]) == 1
    assert out["gate_report"]["overall_quality"] == "medium"


# ---------- GapPolishAgent ----------


def test_gap_polish_agent_empty_input(monkeypatch):
    from app.agents.gap_polish_agent import GapPolishAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(per_card=[], global_suggestions=[])

    monkeypatch.setattr("app.agents.gap_polish_agent.invoke_structured", _fake_invoke)
    out = GapPolishAgent().run({"ats": {}, "selected_cards": []})
    assert out["gap_polish"]["per_card"] == []
    assert out["gap_polish"]["global_suggestions"] == []


def test_gap_polish_agent_with_mock_llm(monkeypatch):
    from app.agents.gap_polish_agent import GapPolishAgent

    fake = {
        "per_card": [
            {
                "card_id": 1,
                "score": 80.0,
                "local_score": 70.0,
                "llm_score": 85.0,
                "matched": ["python", "推荐系统"],
                "missing": ["大数据"],
                "action": "polish",
                "rewrite_suggestion": "建议增加大数据相关经验描述",
            }
        ],
        "global_suggestions": [
            {
                "missing_ability": "团队管理",
                "priority": "medium",
                "action": "supplement",
                "steps": ["补充团队管理经验", "描述项目协调能力"],
            }
        ],
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.gap_polish_agent.invoke_structured", _fake_invoke)
    out = GapPolishAgent().run(
        {
            "ats": {
                "job_title": "高级后端工程师",
                "required_skills": ["python", "推荐系统", "大数据"],
                "preferred_skills": ["go"],
                "responsibilities": ["设计高可用系统"],
            },
            "selected_cards": [
                {
                    "id": 1,
                    "title": "推荐系统开发",
                    "tags": ["python", "推荐系统"],
                    "raw_text": "负责推荐系统开发，使用Python和TensorFlow",
                }
            ],
        }
    )
    assert len(out["gap_polish"]["per_card"]) == 1
    assert out["gap_polish"]["per_card"][0]["score"] == 80.0
    assert len(out["gap_polish"]["global_suggestions"]) == 1


# ---------- ScoreMatchAgent ----------


def test_score_match_agent_empty_input(monkeypatch):
    from app.agents.score_match_agent import ScoreMatchAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.score_match_agent.invoke_structured", _fail)
    out = ScoreMatchAgent().run({"jd_req": {}, "cards": []})
    assert out["llm_match_items"] == {}


def test_score_match_agent_with_mock_llm(monkeypatch):
    from app.agents.score_match_agent import ScoreMatchAgent

    fake = {
        "items": [
            {
                "card_id": 1,
                "match": 85.0,
                "covered": ["python", "推荐系统"],
                "missing": ["大数据"],
                "reason": "技能匹配度高，但缺少大数据经验",
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.score_match_agent.invoke_structured", _fake_invoke)
    out = ScoreMatchAgent().run(
        {
            "jd_req": {
                "hard_skills": ["python", "推荐系统", "大数据"],
                "soft_skills": ["团队协作"],
                "keywords": ["机器学习"],
                "responsibilities": ["设计推荐系统"],
            },
            "cards": [
                {
                    "id": 1,
                    "title": "推荐系统开发",
                    "summary": "负责推荐系统开发",
                    "tags": ["python", "推荐系统"],
                    "raw_text": "使用Python开发推荐系统",
                }
            ],
        }
    )
    assert len(out["llm_match_items"]) == 1
    assert out["llm_match_items"][1]["match"] == 85.0


# ---------- SugAgent ----------


def test_sug_agent_empty_input(monkeypatch):
    from app.agents.sug_agent import SugAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(gap_analysis="", gap_items=[], suggestions=[])

    monkeypatch.setattr("app.agents.sug_agent.invoke_structured", _fake_invoke)
    out = SugAgent().run({"jd_req": {}, "cards": [], "per_card_scores": []})
    assert out["suggestions"]["suggestions"] == []


def test_sug_agent_with_mock_llm(monkeypatch):
    from app.agents.sug_agent import SugAgent

    fake = {
        "gap_analysis": "技能匹配度一般",
        "gap_items": ["缺少大数据经验"],
        "suggestions": [
            {
                "card_id": 1,
                "type": "gap",
                "message": "建议补充大数据相关项目经验",
                "priority": 4,
                "optimization": "在简历中增加Hadoop/Spark相关描述",
            }
        ],
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.sug_agent.invoke_structured", _fake_invoke)
    out = SugAgent().run(
        {
            "jd_req": {
                "hard_skills": ["python", "大数据"],
                "soft_skills": ["团队协作"],
            },
            "cards": [
                {
                    "id": 1,
                    "title": "推荐系统开发",
                    "summary": "负责推荐系统开发",
                    "tags": ["python"],
                    "raw_text": "使用Python开发推荐系统",
                }
            ],
            "per_card_scores": [
                {
                    "card_id": 1,
                    "score": 60.0,
                    "matched": ["python"],
                    "missing": ["大数据"],
                }
            ],
        }
    )
    assert out["suggestions"]["gap_analysis"] == "技能匹配度一般"
    assert len(out["suggestions"]["suggestions"]) == 1


# ---------- QuestionIntentAgent ----------


def test_question_intent_agent_empty_input(monkeypatch):
    from app.agents.question_intent_agent import QuestionIntentAgent

    def _fail(*args, **kwargs):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr("app.agents.question_intent_agent.invoke_structured", _fail)
    out = QuestionIntentAgent().run({"qa_pairs": []})
    assert out["qa_pairs"] == []


def test_question_intent_agent_with_mock_llm(monkeypatch):
    from app.agents.question_intent_agent import QuestionIntentAgent

    fake = {
        "questions": [
            {
                "sequence": 1,
                "intent": "考察项目深度",
                "dimension": "D3 问题拆解",
                "level": "L4",
            }
        ]
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr(
        "app.agents.question_intent_agent.invoke_structured", _fake_invoke
    )
    out = QuestionIntentAgent().run(
        {
            "company": "字节",
            "position": "后端",
            "round_type": "技术面",
            "qa_pairs": [{"sequence": 1, "question_text": "聊聊你的项目"}],
            "jd_text": "",
        }
    )
    assert len(out["qa_pairs"]) == 1
    assert out["qa_pairs"][0]["dimension"] == "D3 问题拆解"
    assert out["qa_pairs"][0]["level"] == "L4"


# ---------- CompanyResearchAgent ----------


def test_company_research_agent_empty_input(monkeypatch):
    from app.agents.company_research_agent import CompanyResearchAgent

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(
            basic={}, business={}, funding={}, team={}, industry={}, news=[], sources=[]
        )

    monkeypatch.setattr(
        "app.agents.company_research_agent.invoke_structured", _fake_invoke
    )
    out = CompanyResearchAgent().run({"company": "", "search_data": {}})
    assert out["info"]["basic"] == {}
    assert out["info"]["business"] == {}


def test_company_research_agent_with_mock_llm(monkeypatch):
    from app.agents.company_research_agent import CompanyResearchAgent

    fake = {
        "basic": {
            "name": "字节跳动",
            "founded": "2012",
            "headquarters": "北京",
            "size": "10万+",
        },
        "business": {
            "main_products": ["抖音", "今日头条"],
            "business_model": "广告+电商",
        },
        "funding": {"latest_round": "Pre-IPO", "valuation": "1000亿美元"},
        "team": {"founders": "张一鸣"},
        "industry": {"sector": "互联网", "trends": ["AI", "短视频"]},
        "news": [{"title": "字节跳动发布新AI产品", "date": "2026-01-15"}],
        "sources": ["https://example.com"],
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr(
        "app.agents.company_research_agent.invoke_structured", _fake_invoke
    )
    out = CompanyResearchAgent().run(
        {
            "company": "字节跳动",
            "search_data": {"search_results": [{"query": "字节跳动", "result": {}}]},
        }
    )
    assert out["info"]["basic"]["name"] == "字节跳动"
    assert out["info"]["business"]["main_products"] == ["抖音", "今日头条"]


# ---------- StructuredCaller ----------


def test_structured_caller_invoke(monkeypatch):
    from app.agents.structured_caller import invoke_structured
    from pydantic import BaseModel

    class TestSchema(BaseModel):
        name: str = ""
        value: int = 0

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(name="test", value=42)

    monkeypatch.setattr("app.agents.structured_caller._invoke_structured", _fake_invoke)
    result = invoke_structured(
        TestSchema,
        "测试提示词",
        debug_label="test_caller",
        context={"test_key": "test_value"},
    )
    assert result.name == "test"
    assert result.value == 42


def test_structured_caller_with_temperature(monkeypatch):
    from app.agents.structured_caller import invoke_structured
    from pydantic import BaseModel

    class TestSchema(BaseModel):
        result: str = ""

    call_kwargs = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        call_kwargs.update(kwargs)
        return schema(result="success")

    monkeypatch.setattr("app.agents.structured_caller._invoke_structured", _fake_invoke)
    result = invoke_structured(
        TestSchema,
        "测试提示词",
        temperature=0.7,
        max_tokens=1024,
        debug_label="test_caller_temp",
    )
    assert result.result == "success"
    assert call_kwargs.get("temperature") == 0.7
    assert call_kwargs.get("max_tokens") == 1024
