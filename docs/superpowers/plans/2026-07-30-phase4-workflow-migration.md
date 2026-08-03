# Phase 4: 其余功能 Workflow 迁移

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将岗位分析、面试准备、经历卡抽取从直接 LLM 调用迁移为 LangGraph Workflow 模式，并将问题表 LLM 调用合并入已有 interview_review_flow。

**Architecture:** 遵循四层架构 Controller → Workflow → Agent → Tool，每个模块新建或复用 workflow，server.py 路由改为调用 workflow 入口，旧 tool 函数中的 LLM 调用移到 Agent 节点，纯规则/DB 操作保留在 tools/ 中。

**Tech Stack:** Python 3.12, LangGraph StateGraph, Pydantic v2, FastAPI

---

### Task 1: 岗位分析 Workflow — `job_analysis_flow.py` + Agent 节点

**Files:**
- Create: `app/workflows/job_analysis_flow.py`
- Create: `app/agents/jd_parser_agent.py` (ATS 解析)
- Create: `app/agents/card_matcher_agent.py` (匹配评分)
- Create: `app/agents/gap_advisor_agent.py` (缺口+润色)
- Modify: `app/api/server.py` (路由改为调用 workflow)
- Keep (no change): `app/tools/jobcraft_analyze.py` (纯函数: compute_match, _card_text_blob, _match_term_to_blob)

- [ ] **Step 1: 创建 `jd_parser_agent.py`**

```python
"""JD 解析 Agent：从 JD 文本提取 ATSProfile"""

from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.llm import model
from app.tools.llm_json import invoke_structured
from app.agents.base_agent import BaseAgent


class JDParseResult(BaseModel):
    ats: dict = Field(..., description="ATSProfile dict")
    jd_text_raw: str = Field("", description="原始 JD 文本")


class JDParserAgent(BaseAgent[JDParseResult]):
    """ATS 解析 Agent"""

    async def run(self, jd_text: str) -> JDParseResult:
        from app.schemas.jobcraft import ATSProfile
        from pydantic import BaseModel

        class _ATSOut(BaseModel):
            job_title: str = ""
            department: str = ""
            location: str = ""
            salary: str = ""
            education: str = ""
            years_of_experience: str = ""
            required_skills: List[str] = Field(default_factory=list)
            preferred_skills: List[str] = Field(default_factory=list)
            responsibilities: List[str] = Field(default_factory=list)
            key_metrics: List[str] = Field(default_factory=list)
            culture_keywords: List[str] = Field(default_factory=list)
            dimension_requirements: List[dict] = Field(default_factory=list)

        prompt = (
            "从以下 JD 中提取结构化岗位画像：\n"
            "- job_title / department / location / salary / education\n"
            "- years_of_experience\n"
            "- required_skills（硬性要求）\n"
            "- preferred_skills（加分项）\n"
            "- responsibilities（核心职责条目）\n"
            "- key_metrics（量化指标）\n"
            "- culture_keywords（文化价值观关键词）\n"
            "- dimension_requirements（D1-D8，level 1-5，evidence 原文证据）\n\n"
            f"JD 文本：\n{jd_text[:5000]}"
        )
        parsed = invoke_structured(model, _ATSOut, prompt, debug_label="jd_parse")
        return JDParseResult(ats=parsed.model_dump(), jd_text_raw=jd_text)
```

- [ ] **Step 2: 创建 `card_matcher_agent.py`**

```python
"""卡片匹配 Agent：语义评分每张卡片与 JD 的匹配度"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List
from app.core.llm import model
from app.tools.llm_json import invoke_structured
from app.agents.base_agent import BaseAgent
from app.schemas.jobcraft import CardLLMMatchItem


class CardMatchResult(BaseModel):
    items: Dict[int, CardLLMMatchItem] = Field(default_factory=dict)


class CardMatcherAgent(BaseAgent[CardMatchResult]):
    """卡片匹配评分 Agent"""

    async def run(self, jd_req: Dict[str, Any], cards: List[Dict[str, Any]]) -> CardMatchResult:
        if not cards:
            return CardMatchResult()

        from app.tools.jobcraft_analyze import _card_text_blob

        cards_text = []
        for c in cards:
            cards_text.append(
                f"card_id={c['id']}\ntitle={c.get('title', '')}\nsummary={c.get('summary', '')}\n"
                f"tags={','.join(c.get('tags') or [])}\ncontent={_card_text_blob(c)[:600]}"
            )
        cards_section = "\n---\n".join(cards_text)
        prompt = (
            "你是一名资深 HR，正在评估候选人的经历卡片与岗位要求的匹配度。\n\n"
            f"岗位硬性技能：{', '.join(jd_req.get('hard_skills', []))}\n"
            f"软性技能：{', '.join(jd_req.get('soft_skills', []))}\n"
            f"关键词：{', '.join(jd_req.get('keywords', []))}\n"
            f"职责：{', '.join(jd_req.get('responsibilities', []))}\n\n"
            f"经历卡片：\n{cards_section}\n\n"
            "请为每张卡片输出 match (0-100), covered (已覆盖点), missing (未覆盖点), reason。"
        )

        class _Items(BaseModel):
            items: List[CardLLMMatchItem]

        parsed = invoke_structured(model, _Items, prompt, debug_label="card_match")
        return CardMatchResult(items={it.card_id: it for it in parsed.items})
```

- [ ] **Step 3: 创建 `gap_advisor_agent.py`**

```python
"""缺口+润色建议 Agent"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from app.core.llm import model
from app.tools.llm_json import invoke_structured
from app.agents.base_agent import BaseAgent
from app.schemas.jobcraft import SuggestionsResult


class GapAdviseResult(BaseModel):
    suggestions: SuggestionsResult
    per_card_detail: List[dict] = Field(default_factory=list)


class GapAdvisorAgent(BaseAgent[GapAdviseResult]):
    """缺口分析和润色建议 Agent"""

    async def run(
        self,
        jd_text: str,
        cards: List[Dict[str, Any]],
        per_card_scores: List[Dict[str, Any]],
    ) -> GapAdviseResult:
        cards_text = []
        for c in cards:
            pc = next((p for p in per_card_scores if p.get("card_id") == c["id"]), None)
            cards_text.append(
                f"card_id={c['id']} title={c.get('title', '')} score={pc.get('score', 0) if pc else 0} "
                f"matched={pc.get('matched', []) if pc else []} missing={pc.get('missing', []) if pc else []}"
            )
        cards_lines = "\n".join(cards_text)
        prompt = (
            "你是求职优化专家。请根据岗位要求和卡片匹配情况，给出 3-5 条具体优化建议。\n\n"
            f"JD 文本（摘要）：{jd_text[:2000]}\n"
            f"卡片情况：\n{cards_lines}\n\n"
        )
        parsed = invoke_structured(model, SuggestionsResult, prompt, debug_label="gap_advise")
        return GapAdviseResult(suggestions=parsed, per_card_detail=per_card_scores)
```

- [ ] **Step 4: 创建 `job_analysis_flow.py`**

```python
"""岗位分析 Workflow — 单节点 Workflow（Step1 ATS+推荐 → Step2 缺口+润色）"""

from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

from app.tools import db_tools
from app.tools.jobcraft_analyze import (
    compute_match,
    _ats_to_jdreq,
    _build_gap_text,
    _match_level,
    ATSRecommendResult,
    GapPolishResult,
    RecommendedCard,
)
from app.tools.jobcraft_jd_ats import parse_jd_ats
from app.agents.jd_parser_agent import JDParserAgent
from app.agents.card_matcher_agent import CardMatcherAgent
from app.agents.gap_advisor_agent import GapAdvisorAgent


class JobAnalysisState(TypedDict):
    user_id: int
    company: str
    position: str
    jd_text: str
    card_ids: List[int]
    cards: List[Dict[str, Any]]
    ats: dict
    jd_req: dict
    llm_match_items: dict
    match_result: dict
    suggestions: dict
    result: dict


class JobAnalysisWorkflow:
    """岗位分析 Workflow"""

    def __init__(self):
        self.jd_parser = JDParserAgent()
        self.card_matcher = CardMatcherAgent()
        self.gap_advisor = GapAdvisorAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(JobAnalysisState)

        builder.add_node("load_data", self._load_data)
        builder.add_node("parse_jd", self._parse_jd)
        builder.add_node("score_match", self._score_match)
        builder.add_node("analyze_gap", self._analyze_gap)
        builder.add_node("assemble_result", self._assemble_result)

        builder.set_entry_point("load_data")
        builder.add_edge("load_data", "parse_jd")
        builder.add_edge("parse_jd", "score_match")
        builder.add_edge("score_match", "analyze_gap")
        builder.add_edge("analyze_gap", "assemble_result")
        builder.add_edge("assemble_result", END)

        return builder.compile()

    def _load_data(self, state: JobAnalysisState) -> dict:
        cards = []
        for cid in state["card_ids"]:
            c = db_tools.get_card(cid)
            if c and c.get("is_active"):
                cards.append(c)
        if not cards:
            raise ValueError("所选卡片均不可用")
        return {"cards": cards}

    def _parse_jd(self, state: JobAnalysisState) -> dict:
        result = self.jd_parser.run(state["jd_text"])  # sync
        ats = result.ats
        jd_req = _ats_to_jdreq(type("ATS", (), ats)())  # simple dict wrapper
        return {"ats": ats, "jd_req": jd_req.model_dump()}

    def _score_match(self, state: JobAnalysisState) -> dict:
        from app.schemas.jobcraft import JDRequirements

        jd_req = JDRequirements(**state["jd_req"])
        match = compute_match(state["cards"], jd_req)
        return {"match_result": match}

    def _analyze_gap(self, state: JobAnalysisState) -> dict:
        jd_req = state["jd_req"]
        from app.schemas.jobcraft import JDRequirements

        req = JDRequirements(**jd_req)
        from app.tools.jobcraft_analyze import _suggest_optimizations

        suggestions = _suggest_optimizations(req, state["cards"], state["match_result"]["per_card"])
        return {"suggestions": suggestions.model_dump()}

    def _assemble_result(self, state: JobAnalysisState) -> dict:
        from app.schemas.jobcraft import JobAnalysisResult, PerCardScore
        import copy

        ats = state["ats"]
        match = state["match_result"]
        suggestions = state["suggestions"]

        from pydantic import BaseModel
        class ATSSimple:
            job_title = ats.get("job_title", "")
            dimension_requirements = ats.get("dimension_requirements", [])
            required_skills = ats.get("required_skills", [])
            preferred_skills = ats.get("preferred_skills", [])
            responsibilities = ats.get("responsibilities", [])
            key_metrics = ats.get("key_metrics", [])
            culture_keywords = ats.get("culture_keywords", [])

        from app.tools.jobcraft_analyze import _ats_to_jdreq
        jd_req = _ats_to_jdreq(ATSSimple())

        db_data = {
            "user_id": state["user_id"],
            "company": state.get("company", ""),
            "position": state.get("position", "") or ats.get("job_title", ""),
            "jd_text": state["jd_text"],
            "jd_requirements": jd_req.model_dump(),
            "match_score": match["overall"],
            "gap_analysis": suggestions.get("gap_analysis", "") or match["gap"],
            "dimension_requirements": ats.get("dimension_requirements", []),
        }
        job_id = db_tools.insert_job_analysis(db_data)
        for c in state["cards"]:
            db_tools.upsert_job_mapping(job_id, c["id"])

        per_card_scores = [PerCardScore(**p) for p in match["per_card"]]
        from app.schemas.jobcraft import SuggestionItem
        suggestion_objs = [SuggestionItem(**s) for s in suggestions.get("suggestions", [])]

        result = JobAnalysisResult(
            job_analysis_id=job_id,
            user_id=state["user_id"],
            company=state.get("company", ""),
            position=state.get("position", "") or ats.get("job_title", ""),
            jd_text=state["jd_text"],
            jd_requirements=jd_req,
            ats_profile=ATSSimple(),
            company_context=None,
            match_score=match["overall"],
            match_level=_match_level(match["overall"]),
            customization_needed=match["overall"] < 75,
            gap_analysis=suggestions.get("gap_analysis", "") or match["gap"],
            gap_items=suggestions.get("gap_items", []),
            per_card_scores=per_card_scores,
            suggestions=suggestion_objs,
            dimension_requirements=ats.get("dimension_requirements", []),
        )
        return {"result": result.model_dump()}


# 便捷入口
def run_job_analysis_workflow(
    user_id: int,
    company: str,
    position: str,
    jd_text: str,
    card_ids: List[int],
) -> dict:
    workflow = JobAnalysisWorkflow()
    initial = JobAnalysisState(
        user_id=user_id,
        company=company,
        position=position,
        jd_text=jd_text,
        card_ids=card_ids,
        cards=[],
        ats={},
        jd_req={},
        llm_match_items={},
        match_result={},
        suggestions={},
        result={},
    )
    final = workflow.graph.invoke(initial)
    return final["result"]


def run_step1_workflow(jd_text: str, cards: List[Dict[str, Any]]) -> dict:
    """Step 1: ATS 解析 + 推荐卡片"""
    from app.tools.jobcraft_analyze import ats_and_recommend
    return ats_and_recommend(jd_text, cards)


def run_step2_workflow(
    ats: dict, jd_text: str, selected_cards: List[Dict[str, Any]]
) -> dict:
    """Step 2: 缺口分析 + 润色建议"""
    from app.tools.jobcraft_analyze import gap_and_polish
    return gap_and_polish(type("ATS", (), ats)(), jd_text, selected_cards)
```

- [ ] **Step 5: 更新 server.py — 岗位分析路由改为调用 workflow**

Find the `jobcraft_job_analyze` route (line ~726) and change it:

```python
# 替换:
from app.tools import jobcraft_analyze
result = jobcraft_analyze.analyze_job(...)
# 为:
from app.workflows.job_analysis_flow import run_job_analysis_workflow
result = run_job_analysis_workflow(...)
```

- [ ] **Step 6: ruff check + ruff format**
- [ ] **Step 7: pytest tests/test_qa_pairs_unit.py -q 验证**

---

### Task 2: 问题表 LLM 合并入 `interview_review_flow.py`

**Files:**
- Modify: `app/workflows/interview_review_flow.py` (新增 `generate_question_table` 节点)
- Modify: `app/api/server.py` (路由改为调用 workflow)
- Keep: `app/tools/interview_review.py` 中的 `generate_question_table()` / `preview_question_intents()`

- [ ] **Step 1: 在 `interview_review_flow.py` 新增 `generate_question_table` 节点**

Add a new Agent `QuestionTableAgent` in the agents dir or inline. The flow already has `load_data` which parses dialogue and builds QA pairs. Add a new branching path for question-table generation.

- [ ] **Step 2: 更新 server.py 中 `/question-table` 和 `/interview-review` 路由**
- [ ] **Step 3: ruff check + ruff format**

---

### Task 3: 面试准备 Workflow — `interview_prep_flow.py`

**Files:**
- Create: `app/workflows/interview_prep_flow.py`
- Keep: `app/tools/interview_pre.py` 中的 `_build_interview_prompt`, `generate_interview_prep`, `get_or_search_company`
- Modify: `app/api/server.py` (面试准备路由改为调用 workflow)

- [ ] **Step 1: 创建单节点 workflow**
- [ ] **Step 2: 更新 server.py**
- [ ] **Step 3: ruff check + ruff format**

---

### Task 4: 经历卡抽取 Workflow — `extract_flow.py`

**Files:**
- Create: `app/workflows/extract_flow.py`
- Keep: `app/tools/jobcraft_extract.py`
- Modify: `app/api/server.py`

- [ ] **Step 1: 创建单节点 workflow**
- [ ] **Step 2: 更新 server.py**
- [ ] **Step 3: ruff check + ruff format**

---

### Task 5: 清理旧导入 + 全量验证

- [ ] **Step 1: 检查所有未使用的 LLM 导入**
- [ ] **Step 2: ruff check --fix . && ruff format .**
- [ ] **Step 3: pytest tests/ -q**
