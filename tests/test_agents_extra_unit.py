"""
Agent 节点额外 Mock 单测（无真实 LLM 调用）

通过 monkeypatch 替换各 agent 模块内的 invoke_structured，
验证 agent 的输入→输出转换逻辑与容错分支。
"""

import sys
from pathlib import Path

import pytest

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

    monkeypatch.setattr("app.agents.gate_agent.invoke_structured", _fail)
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

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(**fake)

    monkeypatch.setattr("app.agents.gate_agent.invoke_structured", _fake_invoke)
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


def test_gate_agent_uses_structured_pipeline(monkeypatch):
    """BE-AI-02：Gate 走 invoke_structured，prompt_version/debug_label 进审计管道。"""
    from app.agents.gate_agent import GateAgent, _GateOut

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        captured["schema"] = schema
        return _GateOut(issues=[], overall_quality="high")

    monkeypatch.setattr("app.agents.gate_agent.invoke_structured", _fake_invoke)
    out = GateAgent().run(
        {
            "tech_results": [{"sequence": 1, "score": 90, "dimension": "D1"}],
            "soft_results": [],
        }
    )
    assert captured["schema"] is _GateOut
    assert captured["prompt_version"] == "1"
    assert captured["debug_label"] == "gate_agent"
    assert out["gate_report"]["overall_quality"] == "high"


def test_gate_agent_llm_failure_raises(monkeypatch):
    """BE-AI-02：LLM 失败必须上抛，不再静默吞成 schema() 默认空实例。"""
    from app.agents.gate_agent import GateAgent

    def _boom(*args, **kwargs):
        raise RuntimeError("结构化调用失败")

    monkeypatch.setattr("app.agents.gate_agent.invoke_structured", _boom)
    with pytest.raises(RuntimeError, match="结构化调用失败"):
        GateAgent().run(
            {
                "tech_results": [{"sequence": 1, "score": 90, "dimension": "D1"}],
                "soft_results": [],
            }
        )


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


def test_sug_agent_prompt_v2_dimensions_and_capability_gaps(monkeypatch):
    """T-M4-2 / Q3：suggestions prompt v2 注入维度要求，capability_gaps 同次输出。"""
    from app.agents.sug_agent import SugAgent

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return schema(
            gap_analysis="缺口概览",
            gap_items=[],
            suggestions=[],
            capability_gaps=[
                {
                    "dimension": "D6",
                    "kind": "rewrite",
                    "status": "weak",
                    "severity": "high",
                    "jd_evidence": "独立完成用户研究并形成决策",
                    "current": "协助完成调研",
                    "rewrite_hint": "突出独立主导与决策闭环",
                    "card_id": 1,
                    "note": "",
                }
            ],
        )

    monkeypatch.setattr("app.agents.sug_agent.invoke_structured", _fake_invoke)
    out = SugAgent().run(
        {
            "jd_req": {
                "hard_skills": ["用户研究"],
                "dimension_requirements": [
                    {
                        "dimension": "D6",
                        "level": 5,
                        "evidence": "独立完成用户研究并形成决策",
                    }
                ],
            },
            "cards": [],
            "per_card_scores": [],
        }
    )
    # 版本化（AGENTS §7）：prompt v2 + 审计 prompt_version=2
    assert captured["prompt_version"] == "2"
    # 维度要求已注入 prompt（D1-D8 尺子对齐 Q3-a）
    assert "D6 等级5：独立完成用户研究并形成决策" in captured["prompt"]
    gaps = out["suggestions"]["capability_gaps"]
    assert gaps[0]["dimension"] == "D6"
    assert gaps[0]["kind"] == "rewrite"
    assert gaps[0]["card_id"] == 1


def test_sug_agent_prompt_v2_empty_dimensions_hint(monkeypatch):
    """无维度要求时 prompt 给出 EXT 兜底提示，不缺占位符实参。"""
    from app.agents.sug_agent import SugAgent

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured["prompt"] = prompt
        return schema(gap_analysis="", gap_items=[], suggestions=[])

    monkeypatch.setattr("app.agents.sug_agent.invoke_structured", _fake_invoke)
    SugAgent().run({"jd_req": {}, "cards": [], "per_card_scores": []})
    assert "（无维度要求，缺口归 EXT）" in captured["prompt"]


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

    captured = {}

    def _fake_invoke(model, schema, prompt, **kwargs):
        captured.update(kwargs)
        captured["prompt"] = prompt
        return schema()

    monkeypatch.setattr(
        "app.agents.company_research_agent.invoke_structured", _fake_invoke
    )
    out = CompanyResearchAgent().run({"company": "", "search_data": {}})
    # T-P7-1：wire 顶层唯一 aspects，六维默认空列表（无据维=空，不编造）
    assert set(out["info"].keys()) == {"aspects"}
    assert out["info"]["aspects"]["overview"] == []
    assert out["info"]["aspects"]["business"] == []
    assert out["info"]["aspects"]["reputation"] == []
    # 版本化：prompt v2 + prompt_version 记账
    assert captured["prompt_version"] == "2"
    assert '"aspects"' in captured["prompt"]
    assert "reputation" in captured["prompt"]


def test_company_research_agent_with_mock_llm(monkeypatch):
    from app.agents.company_research_agent import CompanyResearchAgent

    fake = {
        "overview": [
            {
                "content": "字节跳动 2012 年成立于北京，团队 10 万+",
                "source_url": "https://example.com/about",
                "source_type": "官方",
                "sufficiency": "full",
            }
        ],
        "business": [
            {
                "content": "主营抖音/今日头条，广告+电商盈利（自研）",
                "source_url": "https://example.com/biz",
                "source_type": "官方",
                "sufficiency": "full",
            }
        ],
        "ecosystem": [
            {
                "content": "短视频赛道头部（推断）",
                "source_type": "AI推断",
                "sufficiency": "partial",
            }
        ],
        "team": [
            {
                "content": "创始人张一鸣",
                "source_url": "https://example.com/team",
                "source_type": "官方",
                "sufficiency": "full",
            }
        ],
        "recent": [
            {
                "content": "发布新 AI 产品",
                "source_url": "https://news.example.com/a",
                "date": "2026-01-15",
                "source_type": "新闻",
                "sufficiency": "partial",
            }
        ],
        "reputation": [
            {
                "content": "牛客面经：三轮技术面重项目深挖",
                "source_url": "https://nowcoder.com/m/xxx",
                "source_type": "社交",
                "sufficiency": "partial",
            }
        ],
    }

    def _fake_invoke(model, schema, prompt, **kwargs):
        return schema(aspects=fake)

    monkeypatch.setattr(
        "app.agents.company_research_agent.invoke_structured", _fake_invoke
    )
    out = CompanyResearchAgent().run(
        {
            "company": "字节跳动",
            "search_data": {"search_results": [{"query": "字节跳动", "result": {}}]},
        }
    )
    info = out["info"]
    assert set(info.keys()) == {"aspects"}
    aspects = info["aspects"]
    assert aspects["overview"][0]["content"].startswith("字节跳动")
    assert aspects["business"][0]["source_type"] == "官方"
    assert aspects["recent"][0]["date"] == "2026-01-15"
    assert aspects["reputation"][0]["source_type"] == "社交"
    assert aspects["ecosystem"][0]["source_type"] == "AI推断"


def test_get_or_search_company_merges_metadata_without_collision(monkeypatch):
    """顶层元数据合并：{**info, cached_at, from_cache} 与 aspects 键无碰撞。"""
    from app.agents import company_research_agent as mod

    fake_info = {
        "aspects": {
            "overview": [],
            "business": [],
            "ecosystem": [],
            "team": [],
            "recent": [],
            "reputation": [],
        }
    }

    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr("app.tools.db_tools.upsert_company_research", lambda c, i: None)

    class _FakeSearch:
        def invoke(self, _payload):
            return {
                "results": [
                    {
                        "title": "字节跳动官网",
                        "url": "https://www.bytedance.com/zh/",
                        "content": "字节跳动是一家科技公司",
                    }
                ]
            }

    monkeypatch.setattr("app.tools.tavily_tool.internet_search", _FakeSearch())
    monkeypatch.setattr(
        mod.CompanyResearchAgent, "run", lambda self, state: {"info": fake_info}
    )

    out = mod.get_or_search_company("字节跳动")
    assert out is not None
    assert set(out.keys()) == {"aspects", "cached_at", "from_cache"}
    assert out["aspects"] == fake_info["aspects"]


# ---------- T-P7-2 query 工程（配方表 / 全失败守卫 / include_domains / 体积防线） ----------


def _fake_aspects_info() -> dict:
    """空 aspects 六维 info（P7-1 wire 结构）。"""
    keys = ("overview", "business", "ecosystem", "team", "recent", "reputation")
    return {"aspects": {k: [] for k in keys}}


def _nonempty_aspects_info() -> dict:
    """六维中至少一维非空的 info（M-2b：全空不落库后，成功路径测试须用非空）。"""
    info = _fake_aspects_info()
    info["aspects"]["business"] = [
        {
            "content": "主营 AI 招聘 SaaS",
            "source_type": "官方",
            "source_url": "https://example.com",
        }
    ]
    return info


class _FakeInternetSearch:
    """internet_search 替身：记录全部调用 payload，按传入函数分派响应。"""

    def __init__(self, responder):
        self.calls = []
        self._responder = responder

    def invoke(self, payload):
        self.calls.append(payload)
        return self._responder(payload)


def _patch_company_research_env(monkeypatch, responder):
    """替换缓存/搜索/LLM 三层，返回 (fake_search, upserts, llm_states)。

    M-2b 口径：LLM 全空六维不落库，故默认 run 返回非空 info（需要全空
    语义的用例自行覆写 ``CompanyResearchAgent.run``）。
    """
    from app.agents import company_research_agent as mod

    fake = _FakeInternetSearch(responder)
    upserts = []
    llm_states = []

    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research",
        lambda c, i: upserts.append((c, i)),
    )
    monkeypatch.setattr("app.tools.tavily_tool.internet_search", fake)

    def _fake_run(self, state):
        llm_states.append(state)
        return {"info": _nonempty_aspects_info()}

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _fake_run)
    return fake, upserts, llm_states


def test_query_recipes_seven_with_topic_and_dynamic_year():
    """矩阵「query 配方 7 条」原文 + topic 分布 + 动态年份（清除硬编码）。"""
    from datetime import datetime

    from app.agents.company_research_agent import _QUERY_RECIPES, _render_queries

    assert [r["template"] for r in _QUERY_RECIPES] == [
        "{company} 官网 关于我们 产品服务",
        "{company} 主营业务 产品线 自研",
        "{company} 行业 地位 竞争对手 融资",
        "{company} 创始人 高管 背景",
        "{company} 最新新闻 {year}",
        "{company} 面经 面试经验 牛客",
        "{company} 脉脉 知乎 员工评价",
    ]
    assert [r["topic"] for r in _QUERY_RECIPES] == [
        "general",
        "general",
        "finance",
        "general",
        "news",
        "general",
        "general",
    ]

    year = datetime.now().year
    rendered = _render_queries("字节跳动")
    assert [q["query"] for q in rendered] == [
        "字节跳动 官网 关于我们 产品服务",
        "字节跳动 主营业务 产品线 自研",
        "字节跳动 行业 地位 竞争对手 融资",
        "字节跳动 创始人 高管 背景",
        f"字节跳动 最新新闻 {year}",
        "字节跳动 面经 面试经验 牛客",
        "字节跳动 脉脉 知乎 员工评价",
    ]
    assert [q["topic"] for q in rendered] == [r["topic"] for r in _QUERY_RECIPES]
    # 质量审查 Minor-8：配方 1（官网）+ 配方 5（新闻）带域名聚焦标记
    assert [q["domain_refocus"] for q in rendered] == [
        True,
        False,
        False,
        False,
        True,
        False,
        False,
    ]
    # 硬编码「2025 2026」必须清除，动态年份只出现在新闻配方
    assert all("2025 2026" not in q["query"] for q in rendered)
    # 质量审查 Minor-9：渲染层自防——company strip 后渲染、空串无前导空格
    assert (
        _render_queries("  字节跳动  ")[0]["query"] == "字节跳动 官网 关于我们 产品服务"
    )
    assert _render_queries("")[0]["query"] == "官网 关于我们 产品服务"
    assert _render_queries(" 字节 ")[4]["query"] == f"字节 最新新闻 {year}"


def test_get_or_search_company_all_queries_fail_returns_none(monkeypatch, caplog):
    """全失败守卫①：所有 query 抛错 → 不调 LLM、不写缓存，返回 None。"""
    import logging

    from app.agents import company_research_agent as mod

    def _boom(_payload):
        raise RuntimeError("tavily down")

    fake = _FakeInternetSearch(_boom)
    upserts = []
    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr("app.tools.tavily_tool.internet_search", fake)

    def _no_llm(self, state):
        raise AssertionError("全失败守卫不应调用 CompanyResearchAgent")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _no_llm)

    with caplog.at_level(logging.INFO, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is None
    assert len(fake.calls) == 7  # 7 条配方全部尝试，单条失败不中断
    assert upserts == []
    assert "成功查询=0/7" in caplog.text
    assert "全失败守卫触发" in caplog.text


def test_get_or_search_company_zero_results_returns_none(monkeypatch, caplog):
    """全失败守卫②：查询全成功但 0 结果 → 不调 LLM，返回 None。"""
    import logging

    from app.agents import company_research_agent as mod

    fake = _FakeInternetSearch(lambda _p: {"results": []})
    upserts = []
    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr("app.tools.tavily_tool.internet_search", fake)

    def _no_llm(self, state):
        raise AssertionError("0 结果守卫不应调用 CompanyResearchAgent")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _no_llm)

    with caplog.at_level(logging.INFO, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is None
    assert len(fake.calls) == 7  # 0 结果无可回捞域名，不触发聚焦补检
    assert upserts == []
    assert "累计结果=0 条" in caplog.text
    assert "全失败守卫触发" in caplog.text


def test_get_or_search_company_partial_failure_proceeds(monkeypatch, caplog):
    """单条失败跳过继续：2 条失败/5 条成功照常汇总，LLM 收到瘦身投影。"""
    import logging

    from app.agents import company_research_agent as mod

    def _responder(payload):
        if "官网" in payload["query"] or "面经" in payload["query"]:
            raise RuntimeError("单条超时")
        tail = payload["query"].split()[-1]
        return {
            "results": [
                {
                    "title": "条目-" + payload["query"],
                    "url": f"https://site.example.com/{tail}",
                    "content": "检索摘要内容",
                }
            ]
        }

    fake, upserts, llm_states = _patch_company_research_env(monkeypatch, _responder)

    with caplog.at_level(logging.INFO, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert out["from_cache"] is False
    assert len(upserts) == 1
    # 7 配方 + 配方 5 新闻聚焦补检（官网配方失败 → 无官网聚焦）
    assert len(fake.calls) == 8
    assert "成功查询=6/8" in caplog.text
    assert "累计结果=6 条" in caplog.text
    # 体积防线：进 LLM 的 search_data 是瘦身投影（每条只留 title/url/content）
    items = llm_states[0]["search_data"]["search_results"]
    assert items
    assert all(set(item.keys()) == {"title", "url", "content"} for item in items)
    assert llm_states[0]["company"] == "字节跳动"


def test_get_or_search_company_refocus_uses_include_domains(monkeypatch):
    """include_domains 官网聚焦：白名单只来自首轮结果回捞的域名。"""
    from app.agents import company_research_agent as mod

    def _responder(payload):
        if payload.get("include_domains"):
            assert payload["include_domains"] == ["bytedance.com", "tiktok.com"]
            return {
                "results": [
                    {
                        "title": "聚焦页",
                        "url": "https://www.bytedance.com/about",
                        "content": "官网介绍",
                    }
                ]
            }
        if "官网" in payload["query"]:
            return {
                "results": [
                    {
                        "title": "官网首页",
                        "url": "https://www.bytedance.com/zh/",
                        "content": "官网",
                    },
                    {
                        "title": "国际官网",
                        "url": "https://www.tiktok.com/about",
                        "content": "国际站",
                    },
                ]
            }
        return {"results": []}

    fake, upserts, llm_states = _patch_company_research_env(monkeypatch, _responder)
    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert len(fake.calls) == 8  # 7 条配方 + 1 次官网聚焦
    first, focused = fake.calls[0], fake.calls[1]  # 聚焦紧跟首轮官网查询
    assert "include_domains" not in first
    assert first["query"] == "字节跳动 官网 关于我们 产品服务"
    assert first["topic"] == "general"
    assert focused["include_domains"] == ["bytedance.com", "tiktok.com"]
    assert focused["max_results"] == 2
    assert focused["query"] == first["query"]
    assert focused["topic"] == "general"
    # 首轮 2 条 + 聚焦 1 条（去重后）全部进 LLM
    assert len(llm_states[0]["search_data"]["search_results"]) == 3
    assert len(upserts) == 1


def test_get_or_search_company_refocus_failure_skipped(monkeypatch):
    """聚焦补检失败只跳过：首轮结果照常汇总，不触发全失败守卫。"""
    from app.agents import company_research_agent as mod

    def _responder(payload):
        if payload.get("include_domains"):
            raise RuntimeError("聚焦超时")
        if "官网" in payload["query"]:
            return {
                "results": [
                    {
                        "title": "官网首页",
                        "url": "https://www.example.com/",
                        "content": "官网",
                    }
                ]
            }
        return {"results": []}

    fake, upserts, _states = _patch_company_research_env(monkeypatch, _responder)
    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert len(fake.calls) == 8  # 聚焦被尝试但失败
    assert len(upserts) == 1


def test_slim_search_data_projects_fields_and_drops_query_echo():
    """体积防线①：只留 title/url/content，去掉 query 回显与 Tavily 冗余字段。"""
    import json

    from app.agents.company_research_agent import _slim_search_data

    results = [
        {
            "query": "QUERY_ECHO_MARKER 官网",
            "result": {
                "query": "QUERY_ECHO_MARKER 官网",
                "response_time": 0.42,
                "results": [
                    {
                        "title": "官网标题",
                        "url": "https://www.example.com/about",
                        "content": "内容" * 200,
                        "score": 0.97,
                    }
                ],
            },
        }
    ]
    data = _slim_search_data(results)
    assert list(data.keys()) == ["search_results"]
    item = data["search_results"][0]
    assert set(item.keys()) == {"title", "url", "content"}
    assert item["title"] == "官网标题"
    assert item["url"] == "https://www.example.com/about"
    assert len(item["content"]) <= 180  # 摘要有上限，非盲目全量
    dumped = json.dumps(data, ensure_ascii=False)
    assert "QUERY_ECHO_MARKER" not in dumped
    assert "response_time" not in dumped
    assert "score" not in dumped


def test_slim_search_data_dedups_repeated_urls():
    """体积防线②：跨查询/聚焦重复 URL 去重，不重复占预算。"""
    from app.agents.company_research_agent import _slim_search_data

    entry = {
        "query": "q",
        "result": {
            "results": [
                {"title": "A", "url": "https://same.example.com/p", "content": "一"},
                {"title": "B", "url": "https://same.example.com/p", "content": "二"},
            ]
        },
    }
    data = _slim_search_data([entry, dict(entry)])
    assert len(data["search_results"]) == 1


def test_slim_search_data_fits_budget_for_full_recipe_batch():
    """体积防线③：7 配方×3 结果+聚焦的肥数据整体 ≤8000，尾部口碑配方不被饿死。"""
    import json

    from app.agents.company_research_agent import (
        _build_company_prompt,
        _slim_search_data,
    )

    entries = []
    for i in range(8):  # 构造 24 条肥数据（7 条配方 + 聚焦补检量级）
        entries.append(
            {
                "query": f"query-{i}",
                "result": {
                    "results": [
                        {
                            "title": f"标题{i}-{j} " + "长" * 50,
                            "url": (
                                f"https://news{i}.example.com/path/{j}"
                                "?ref=nav&id=123456&from=search"
                            ),
                            "content": "内容" * 150,  # 300 字符/条，远超摘要上限
                            "score": 0.99,
                        }
                        for j in range(3)
                    ]
                },
            }
        )
    data = _slim_search_data(entries)
    assert len(data["search_results"]) == 24  # 全部配方结果保留，不整条丢弃
    dumped = json.dumps(data, ensure_ascii=False)
    assert len(dumped) <= 8000  # 不触发 _build_company_prompt 的硬截断
    assert data["search_results"][-1]["title"].startswith("标题7-2")
    # prompt 注入的是完整投影（[:8000] 未砍尾）
    assert dumped in _build_company_prompt("字节跳动", data)


def test_slim_search_data_url_cap_floor_drop_and_warning(caplog):
    """体积防线④（Minor-1/6）：url 截 120、floor 实际下限 40、
    超预算按条丢尾并显式 warning（不依赖 [:8000] 静默砍）。"""
    import json
    import logging

    from app.agents import company_research_agent as mod

    entries = [
        {
            "query": f"q{i}",
            "result": {
                "results": [
                    {
                        "title": "T" * mod._TITLE_LIMIT,
                        "url": "u" * 300
                        + str(i),  # 200+ 字超长 url（逐条唯一，不去重）
                        "content": "c" * 200,
                    }
                ]
            },
        }
        for i in range(80)
    ]
    with caplog.at_level(logging.WARNING, logger="jobcraft.agents.company_research"):
        data = mod._slim_search_data(entries)

    dumped = json.dumps(data, ensure_ascii=False)
    assert len(dumped) <= 8000  # 单项 url 击穿被 120 上限拦住
    assert all(len(item["url"]) == 120 for item in data["search_results"])
    # floor 实际下限 = 40（旧减半实现会落到 22）
    assert all(len(item["content"]) == 40 for item in data["search_results"])
    dropped = 80 - len(data["search_results"])
    assert dropped > 0
    # 丢弃条数显式可观测（warning 文案与实际丢弃数一致）
    assert f"按条丢弃尾部检索结果 {dropped} 条" in caplog.text
    # 丢的是尾部：头部条目仍在
    assert data["search_results"][0]["title"] == "T" * 120


def test_slim_search_data_dedup_key_normalization():
    """体积防线⑤（Minor-5）：去 fragment/尾斜杠/小写归一去重，query 串不剥。"""
    from app.agents.company_research_agent import _slim_search_data

    urls = [
        "https://Example.com/Path/",
        "https://example.com/Path",
        "https://example.com/Path#section",
        "https://example.com/Path?a=1",
        "https://example.com/Path?a=2",
    ]
    entry = {
        "result": {
            "results": [
                {"title": f"t{i}", "url": url, "content": "c"}
                for i, url in enumerate(urls)
            ]
        },
    }
    data = _slim_search_data([entry])
    # 前三个变体（大小写/尾斜杠/fragment）归一 → 1 条；query 不剥 → 各留
    assert len(data["search_results"]) == 3
    kept = [item["url"] for item in data["search_results"]]
    assert kept[0] == "https://Example.com/Path/"  # 首见原样保留
    assert "https://example.com/Path?a=1" in kept
    assert "https://example.com/Path?a=2" in kept


def test_harvest_domains_filters_denylist_ip_and_keeps_official():
    """Minor-2：搜索引擎/聚合站 denylist + IP host 过滤 + 去尾点，正常官网域过。"""
    from app.agents.company_research_agent import _harvest_domains

    for suffix in (
        "baidu.com",
        "google.com",
        "bing.com",
        "sogou.com",
        "so.com",
        "360.cn",
        "sm.cn",
        "wikipedia.org",
    ):
        assert _harvest_domains({"results": [{"url": f"https://www.{suffix}/x"}]}) == []
        assert (
            _harvest_domains({"results": [{"url": f"https://news.{suffix}/x"}]}) == []
        )

    # 全数字点分 host（IPv4）不过
    assert _harvest_domains({"results": [{"url": "http://192.168.1.10/admin"}]}) == []

    # 去尾点 + 去 www：正常官网域过，IP 不占坑
    resp = {
        "results": [
            {"url": "https://www.Official-Corp.com./about"},
            {"url": "https://192.168.0.1/"},
            {"url": "https://sub.official-corp.com/team"},
        ]
    }
    assert _harvest_domains(resp) == ["official-corp.com", "sub.official-corp.com"]


def test_get_or_search_company_fresh_cache_hit_shape(monkeypatch):
    """Minor-3a/c：fresh 命中（非空内容）→ 0 次搜索、不回写，形状与实时路径统一。

    M-2a 口径：命中须内容非空——六维全空 aspects 视同未命中走重搜，
    故本用例改用非空 info（全空分支见 test_fresh_six_dim_empty_cache_triggers_research）。
    """
    from app.agents import company_research_agent as mod

    fake_info = _nonempty_aspects_info()
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: {
            "company": c,
            "info": fake_info,
            "cached_at": "2026-10-01T00:00:00",
            "fresh": True,
        },
    )
    fake = _FakeInternetSearch(lambda _p: {"results": []})
    upserts = []
    monkeypatch.setattr("app.tools.tavily_tool.internet_search", fake)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research",
        lambda c, i: upserts.append(i),
    )

    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert fake.calls == []  # 命中缓存不发任何搜索
    assert upserts == []
    # 形状与实时路径统一：aspects + cached_at + from_cache=True
    assert set(out.keys()) == {"aspects", "cached_at", "from_cache"}
    assert out["cached_at"] == "2026-10-01T00:00:00"
    assert out["from_cache"] is True
    assert out["aspects"] == fake_info["aspects"]


def test_get_or_search_company_fresh_empty_info_triggers_research(monkeypatch):
    """M-2a：空壳缓存（info={}）fresh 命中视同未命中 → 走实时重搜（不再直接 None）。

    （原「返回 None」语义随 M-2 口径调整：空壳与六维全空同样重搜，
    与 FE「调研暂不可用」+重新调研同口径；无缓存行的 None 语义不变。）
    """
    from app.agents import company_research_agent as mod

    fake, upserts, _llm_states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {"results": [{"title": "T", "url": "", "content": "C"}]},
    )
    # helper 默认无缓存，这里覆写成「fresh 但 info 为空壳」的命中行
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: {"info": {}, "cached_at": "2026-10-01T00:00:00", "fresh": True},
    )

    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert len(fake.calls) > 0  # 触发重搜（非短路返回）
    assert out["from_cache"] is False
    assert len(upserts) == 1


def test_get_or_search_company_force_ignores_fresh_cache(monkeypatch):
    """Minor-3b：force=True 忽略 fresh 缓存照常搜索（走实时路径形状）。"""
    from app.agents import company_research_agent as mod

    fake_info = _fake_aspects_info()
    fake, upserts, llm_states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {"results": [{"title": "T", "url": "", "content": "C"}]},
    )
    # helper 默认无缓存，这里覆写成 fresh 命中行
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: {
            "company": c,
            "info": fake_info,
            "cached_at": "2026-10-01T00:00:00",
            "fresh": True,
        },
    )

    out = mod.get_or_search_company("字节跳动", force=True)

    assert out is not None
    assert len(fake.calls) == 7  # url 空 → 无聚焦补检，7 条配方全试
    assert out["from_cache"] is False  # 实时路径，不吃缓存
    assert len(upserts) == 1
    assert llm_states  # LLM 被真调用（force 汇总新结果）


def test_get_or_search_company_recipe5_news_refocus(monkeypatch):
    """Minor-8：配方 5 新闻域名回捞复检——9 次调用链、聚焦 payload 来自
    首轮真实新闻域、首轮结果先入账（聚焦为空也不误伤守卫）。"""
    from datetime import datetime

    from app.agents import company_research_agent as mod

    year = datetime.now().year

    def _responder(payload):
        if payload.get("include_domains"):
            return {"results": []}  # 聚焦返回空：首轮已入账，守卫不触发
        if "官网" in payload["query"]:
            return {
                "results": [
                    {
                        "title": "官网",
                        "url": "https://www.bytedance.com/zh/",
                        "content": "官网",
                    }
                ]
            }
        if "最新新闻" in payload["query"]:
            return {
                "results": [
                    {
                        "title": "新闻A",
                        "url": "https://www.stcn.com/a/1",
                        "content": "A",
                    },
                    {
                        "title": "新闻B",
                        "url": "https://www.yicai.com/b/2",
                        "content": "B",
                    },
                ]
            }
        return {"results": []}

    fake, upserts, llm_states = _patch_company_research_env(monkeypatch, _responder)
    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    # 调用链 r1,f1,r2,r3,r4,r5,f5,r6,r7 = 9 次（8→9：配方 5 新增聚焦）
    assert len(fake.calls) == 9
    news_query = f"字节跳动 最新新闻 {year}"
    assert fake.calls[5]["query"] == news_query
    focused = fake.calls[6]
    assert focused["query"] == news_query
    assert focused["topic"] == "news"
    assert focused["max_results"] == 2
    # 聚焦白名单来自首轮真实回捞域（经 denylist 护栏后）
    assert focused["include_domains"] == ["stcn.com", "yicai.com"]
    assert len(upserts) == 1
    assert llm_states  # 聚焦为空仍出结果：首轮结果先入账，守卫未触发


# ---------- T-P7-3 降级矩阵（stale/None 回退 / LLM 重试 / 半成品不落库 / D4 日期） ----------


def _stale_cache_row(info: dict | None = None, fresh: bool = False) -> dict:
    """构造一条「过期」缓存行（fresh 短路在全失败守卫之前，stale 才会走到回退）。"""
    return {
        "company": "字节跳动",
        "info": _fake_aspects_info() if info is None else info,
        "cached_at": "2026-09-01T00:00:00",
        "fresh": fresh,
    }


def test_slim_search_data_keeps_published_date():
    """D4：投影保留 Tavily 条目级 published_date（缺省不造键，值原样）。"""
    from app.agents.company_research_agent import _slim_search_data

    entry = {
        "query": "字节跳动 最新新闻 2026",
        "result": {
            "results": [
                {
                    "title": "新闻条目",
                    "url": "https://www.stcn.com/a/1",
                    "content": "新闻摘要",
                    "published_date": "2026-09-30",
                    "score": 0.9,
                },
                {
                    "title": "普通条目",
                    "url": "https://www.example.com/about",
                    "content": "官网摘要",
                },
            ]
        },
    }
    data = _slim_search_data([entry])
    dated, plain = data["search_results"]
    assert dated["published_date"] == "2026-09-30"  # 值原样，不改写
    assert set(dated.keys()) == {"title", "url", "content", "published_date"}
    assert "published_date" not in plain  # 缺省不造键


def test_guard_all_queries_fail_falls_back_to_stale_cache(monkeypatch, caplog):
    """矩阵行2 回退①：全 query 失败 + 旧缓存 → stale 返回，不调 LLM、不写库。"""
    import logging

    from app.agents import company_research_agent as mod

    fake = _FakeInternetSearch(lambda _p: (_ for _ in ()).throw(RuntimeError("down")))
    upserts = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research", lambda c: _stale_cache_row()
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr("app.tools.tavily_tool.internet_search", fake)

    def _no_llm(self, state):
        raise AssertionError("全失败守卫不应调用 CompanyResearchAgent")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _no_llm)

    with caplog.at_level(logging.WARNING, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert out["stale"] is True
    assert out["from_cache"] is True
    assert out["cached_at"] == "2026-09-01T00:00:00"
    assert out["aspects"] == _fake_aspects_info()["aspects"]
    assert upserts == []  # 回退零写库（stale 永不落全局缓存行）
    assert "字节跳动" in caplog.text and "全失败守卫触发" in caplog.text


def test_guard_zero_results_falls_back_to_stale_cache(monkeypatch):
    """矩阵行2 回退②：0 结果守卫同样走旧缓存 stale 回退。"""
    from app.agents import company_research_agent as mod

    upserts = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research", lambda c: _stale_cache_row()
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(lambda _p: {"results": []}),
    )

    def _no_llm(self, state):
        raise AssertionError("0 结果守卫不应调用 CompanyResearchAgent")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _no_llm)

    out = mod.get_or_search_company("字节跳动")
    assert out is not None and out["stale"] is True
    assert upserts == []


def test_guard_force_with_stale_cache_falls_back_on_all_fail(monkeypatch):
    """force + 全失败：fresh 缓存在 force 下不短路，守卫触发仍可 stale 回退。"""
    from app.agents import company_research_agent as mod

    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: _stale_cache_row(fresh=True),
    )
    upserts = []
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(lambda _p: (_ for _ in ()).throw(RuntimeError("down"))),
    )
    monkeypatch.setattr(
        mod.CompanyResearchAgent,
        "run",
        lambda self, state: (_ for _ in ()).throw(AssertionError("不应调 LLM")),
    )

    out = mod.get_or_search_company("字节跳动", force=True)
    assert out is not None and out["stale"] is True
    assert upserts == []


def test_llm_fail_then_retry_success_upserts_once(monkeypatch, caplog):
    """矩阵行4①：LLM 首次失败 → 重试 1 次成功（同一 search_data）→ upsert 恰一次。"""
    import logging

    from app.agents import company_research_agent as mod

    fake, upserts, llm_states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {
            "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
        },
    )
    calls = {"n": 0}

    def _flaky_run(self, state):
        llm_states.append(state)
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("schema 校验失败")
        return {"info": _nonempty_aspects_info()}

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _flaky_run)

    with caplog.at_level(logging.ERROR, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert "stale" not in out  # 重试成功走实时路径，无 stale 标记
    assert out["from_cache"] is False
    assert calls["n"] == 2
    # 重试复用同一份 search_data（不重跑搜索）
    assert llm_states[0]["search_data"] == llm_states[1]["search_data"]
    assert len(fake.calls) == 9  # 7 配方 + 官网/新闻聚焦；LLM 重试零新增搜索
    # 半成品不落库：仅最终成功后 upsert 一次，且 info 恒无 stale 键
    assert len(upserts) == 1
    assert "stale" not in upserts[0][1]
    assert "字节跳动" in caplog.text and "重试 1 次" in caplog.text


def test_llm_fail_twice_falls_back_to_stale_cache(monkeypatch, caplog):
    """矩阵行4②：LLM 重试后仍失败 → 旧缓存 stale 回退，失败路径零写库。"""
    import logging

    from app.agents import company_research_agent as mod

    upserts = []
    llm_calls = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research", lambda c: _stale_cache_row()
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(
            lambda _p: {
                "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
            }
        ),
    )

    def _boom(self, state):
        llm_calls.append(state)
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _boom)

    with caplog.at_level(logging.ERROR, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert out["stale"] is True
    assert out["from_cache"] is True
    assert len(llm_calls) == 2  # 重试恰好 1 次
    assert upserts == []  # 半成品不落库
    assert "字节跳动" in caplog.text and "重试次数=1" in caplog.text


def test_llm_fail_twice_without_cache_returns_none(monkeypatch):
    """矩阵行4③：LLM 重试后仍失败且无旧缓存 → None，零写库。"""
    from app.agents import company_research_agent as mod

    upserts = []
    llm_calls = []
    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(
            lambda _p: {
                "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
            }
        ),
    )

    def _boom(self, state):
        llm_calls.append(state)
        raise RuntimeError("LLM 不可用")

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _boom)

    assert mod.get_or_search_company("字节跳动") is None
    assert len(llm_calls) == 2
    assert upserts == []


def test_stale_fallback_then_success_new_snapshot_has_no_stale(monkeypatch):
    """stale 语义注记①：回退后再次成功 → 新快照无 stale 且 upsert 新 info。"""
    from app.agents import company_research_agent as mod

    upserts = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research", lambda c: _stale_cache_row()
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research",
        lambda c, i: upserts.append((c, i)),
    )
    state = {"fail": True}

    def _responder(_p):
        if state["fail"]:
            raise RuntimeError("tavily down")
        return {"results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]}

    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search", _FakeInternetSearch(_responder)
    )
    monkeypatch.setattr(
        mod.CompanyResearchAgent,
        "run",
        lambda self, s: {"info": _nonempty_aspects_info()},
    )

    first = mod.get_or_search_company("字节跳动")
    assert first is not None and first["stale"] is True
    assert upserts == []

    state["fail"] = False
    second = mod.get_or_search_company("字节跳动")
    assert second is not None
    assert "stale" not in second  # force/再次成功后 prep 快照被覆盖为非 stale
    assert second["from_cache"] is False
    assert len(upserts) == 1
    assert "stale" not in upserts[0][1]  # upsert 的 info 恒无 stale 键


def test_success_logs_empty_dims(monkeypatch, caplog):
    """矩阵行3 缺维 observability：成功解析后日志记录空维列表（wire 不加字段）。"""
    import logging

    from app.agents import company_research_agent as mod

    info = _fake_aspects_info()
    info["aspects"]["business"] = [
        {
            "content": "主营 AI 招聘 SaaS",
            "source_type": "官方",
            "source_url": "https://e.com",
        }
    ]
    _fake, upserts, _states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {
            "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
        },
    )
    monkeypatch.setattr(
        mod.CompanyResearchAgent, "run", lambda self, state: {"info": info}
    )

    with caplog.at_level(logging.INFO, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert "缺维（空列表）=overview,ecosystem,team,recent,reputation" in caplog.text
    assert "stale" not in out  # wire 不因缺维加字段


# ---------- T-P7-3 质量收敛（I-1 限流豁免 / M-2 六维空口径 / M-3 派生键 / M-4 回退分支） ----------


def _rate_limit_run(self, state):
    """抛限流特征错误的 agent.run 替身（消息含 429，命中 is_rate_limit_error）。"""
    raise RuntimeError(
        "[company_research] 结构化调用失败（限流退避已耗尽，跳过兜底请求）: HTTP 429"
    )


def test_llm_rate_limit_no_retry_falls_back_to_stale(monkeypatch, caplog):
    """[I-1] 限流不重试：LLM 恰调 1 次 → stale 回退，upserts==[]。"""
    import logging

    from app.agents import company_research_agent as mod

    upserts = []
    llm_calls = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research", lambda c: _stale_cache_row()
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(
            lambda _p: {
                "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
            }
        ),
    )

    def _limited(self, state):
        llm_calls.append(state)
        return _rate_limit_run(self, state)

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _limited)

    with caplog.at_level(logging.ERROR, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert out["stale"] is True
    assert len(llm_calls) == 1  # 限流不重试（穿 llm_json 护栏的重试被豁免）
    assert upserts == []
    assert "限流不重试" in caplog.text


def test_llm_rate_limit_no_cache_returns_none(monkeypatch):
    """[I-1] 限流不重试且无旧缓存 → None，LLM 恰 1 次、零写库。"""
    from app.agents import company_research_agent as mod

    upserts = []
    llm_calls = []
    monkeypatch.setattr("app.tools.db_tools.get_company_research", lambda c: None)
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(
            lambda _p: {
                "results": [{"title": "T", "url": "https://e.com/x", "content": "C"}]
            }
        ),
    )

    def _limited(self, state):
        llm_calls.append(state)
        return _rate_limit_run(self, state)

    monkeypatch.setattr(mod.CompanyResearchAgent, "run", _limited)

    assert mod.get_or_search_company("字节跳动") is None
    assert len(llm_calls) == 1
    assert upserts == []


def test_fresh_six_dim_empty_cache_triggers_research(monkeypatch):
    """[M-2a] 六维全空 aspects 的 fresh 缓存视同未命中 → 实时重搜（与 FE 同口径）。"""
    from app.agents import company_research_agent as mod

    fake, upserts, _llm_states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {"results": [{"title": "T", "url": "", "content": "C"}]},
    )
    # helper 默认无缓存，覆写成 fresh + 六维全空 aspects 的命中行
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: _stale_cache_row(fresh=True),
    )

    out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert len(fake.calls) > 0  # 触发重搜（未被空壳缓存短路）
    assert out["from_cache"] is False
    assert len(upserts) == 1


def test_llm_success_six_dim_empty_no_upsert(monkeypatch, caplog):
    """[M-2b] LLM 成功但六维全空 → warning + 不 upsert，返回无 stale（FE 自然降级）。"""
    import logging

    from app.agents import company_research_agent as mod

    fake, upserts, _llm_states = _patch_company_research_env(
        monkeypatch,
        lambda _p: {"results": [{"title": "T", "url": "", "content": "C"}]},
    )
    monkeypatch.setattr(
        mod.CompanyResearchAgent,
        "run",
        lambda self, state: {"info": _fake_aspects_info()},
    )

    with caplog.at_level(logging.WARNING, logger="jobcraft.agents.company_research"):
        out = mod.get_or_search_company("字节跳动")

    assert out is not None
    assert upserts == []  # 半成品不落库
    assert "stale" not in out  # 非回退路径，无 stale 标记
    assert out["from_cache"] is False
    assert "六维全空" in caplog.text
    assert fake.calls  # 搜索照常发生


def test_guard_all_queries_fail_with_empty_info_cache_returns_none(monkeypatch):
    """[M-4a] 守卫触发 + cached.info={} → None（空壳不值得 stale 回退），零写库。"""
    from app.agents import company_research_agent as mod

    upserts = []
    monkeypatch.setattr(
        "app.tools.db_tools.get_company_research",
        lambda c: _stale_cache_row(info={}),
    )
    monkeypatch.setattr(
        "app.tools.db_tools.upsert_company_research", lambda c, i: upserts.append(i)
    )
    monkeypatch.setattr(
        "app.tools.tavily_tool.internet_search",
        _FakeInternetSearch(lambda _p: (_ for _ in ()).throw(RuntimeError("down"))),
    )
    monkeypatch.setattr(
        mod.CompanyResearchAgent,
        "run",
        lambda self, state: (_ for _ in ()).throw(AssertionError("不应调 LLM")),
    )

    assert mod.get_or_search_company("字节跳动") is None
    assert upserts == []


def test_stale_fallback_unit_none_and_empty_info():
    """[M-4a] _stale_fallback：None 行 / info={} → None；cached_at 直取不伪造时间戳。"""
    from app.agents.company_research_agent import _stale_fallback

    assert _stale_fallback("字节跳动", None) is None
    assert (
        _stale_fallback(
            "字节跳动", {"info": {}, "cached_at": "2026-09-01T00:00:00", "fresh": False}
        )
        is None
    )
    out = _stale_fallback(
        "字节跳动",
        {
            "info": _nonempty_aspects_info(),
            "cached_at": "2026-09-01T00:00:00",
            "fresh": False,
        },
    )
    assert out is not None
    assert out["cached_at"] == "2026-09-01T00:00:00"  # 行内值，非当下伪造


def test_aspect_keys_derived_from_schema():
    """[M-3] _ASPECT_KEYS 从 CompanyResearchAspects.model_fields 派生（第 7 维自动进）。"""
    from app.agents.company_research_agent import _ASPECT_KEYS
    from app.schemas.jobcraft import CompanyResearchAspects

    assert _ASPECT_KEYS == list(CompanyResearchAspects.model_fields)
    assert _ASPECT_KEYS == [
        "overview",
        "business",
        "ecosystem",
        "team",
        "recent",
        "reputation",
    ]
