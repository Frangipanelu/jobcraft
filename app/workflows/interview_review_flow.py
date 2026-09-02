"""
面试复盘 Multi-Agent Workflow

将 analyze_selected_questions 从单次 LLM 调用拆分为：
  1. load_data（无 LLM）→ 2. route（分类）
  → 3. tech_analyze + soft_analyze（并行）→ 4. gate（质检）
  → 5. assemble（无 LLM）

API 层调用 run_interview_review_workflow() 即可。
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.router_agent import RouterAgent
from app.agents.tech_analyzer import TechAnalyzer
from app.agents.soft_analyzer import SoftAnalyzer
from app.agents.gate_agent import GateAgent
from app.schemas.jobcraft import InterviewReviewResult, ReviewedQuestion
from app.tools import db_tools
from app.tools.interview_review import (
    _parse_dialogue,
    _build_qa_pairs,
    _get_job_context,
    _format_cards_for_prompt,
    _find_my_answer,
    MAX_QUESTION_TABLE_QA_PAIRS,
)

logger = logging.getLogger(__name__)


class InterviewReviewState(TypedDict):
    # 输入
    record_id: int
    user_id: int
    selected_sequences: List[int]

    # 加载的数据
    record: Dict[str, Any]
    dialogue: List[Dict[str, Any]]
    all_qa_pairs: List[Dict[str, Any]]
    selected_qa_pairs: List[Dict[str, Any]]
    job_context: Dict[str, Any]
    jd_text: str
    cards_text: str
    company: str
    position: str
    round_type: str

    # Router 输出
    classified: Dict[str, List[int]]

    # Tech/Soft 分析结果
    tech_results: List[Dict[str, Any]]
    soft_results: List[Dict[str, Any]]

    # Gate 输出
    gate_report: Dict[str, Any]

    # 最终结果
    result: Optional[Dict[str, Any]]


def _load_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """第1步：从 DB 加载数据，规则引擎解析，无 LLM"""
    record_id = state["record_id"]
    user_id = state.get("user_id", 1)

    record = db_tools.get_interview_record(record_id, user_id)
    if not record:
        raise ValueError(f"面试记录不存在: {record_id}")

    dialogue = _parse_dialogue(record.get("raw_text", ""))
    all_qa_pairs = _build_qa_pairs(dialogue)
    if not all_qa_pairs:
        raise ValueError("未识别到任何面试官问题")

    selected_set = set(state["selected_sequences"])
    selected_qa_pairs = [qa for qa in all_qa_pairs if qa["sequence"] in selected_set]
    if not selected_qa_pairs:
        raise ValueError("未选中任何有效问题")

    job_context = _get_job_context(record, user_id=user_id)
    cards_text = _format_cards_for_prompt(job_context.get("cards", []), max_cards=5)

    return {
        "record": record,
        "dialogue": dialogue,
        "all_qa_pairs": all_qa_pairs,
        "selected_qa_pairs": selected_qa_pairs,
        "job_context": job_context,
        "jd_text": job_context.get("jd_text", ""),
        "cards_text": cards_text,
        "company": record.get("company", ""),
        "position": record.get("position", ""),
        "round_type": record.get("round_type", ""),
    }


def _route_questions(state: Dict[str, Any]) -> Dict[str, Any]:
    """第2步：Router Agent 分类问题"""
    agent = RouterAgent()
    return agent.run(state)


def _tech_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """第3a步：Tech Agent 分析技术类问题"""
    agent = TechAnalyzer()
    return agent.run(state)


def _soft_analyze(state: Dict[str, Any]) -> Dict[str, Any]:
    """第3b步：Soft Agent 分析行为/业务类问题"""
    agent = SoftAnalyzer()
    return agent.run(state)


def _gate_check(state: Dict[str, Any]) -> Dict[str, Any]:
    """第4步：Gate Agent 质检"""
    agent = GateAgent()
    return agent.run(state)


def _assemble_result(state: Dict[str, Any]) -> Dict[str, Any]:
    """第5步：组装最终结果，写入 DB，无 LLM"""
    record = state["record"]
    user_id = state.get("user_id", 1)
    record_id = state["record_id"]
    selected_sequences = state["selected_sequences"]
    selected_set = set(selected_sequences)
    all_qa_pairs = state["all_qa_pairs"]
    dialogue = state["dialogue"]
    selected_qa_pairs = state["selected_qa_pairs"]
    job_context = state["job_context"]

    # 合并 Tech + Soft 分析结果
    analysis_by_seq: Dict[int, Dict[str, Any]] = {}
    for item in state.get("tech_results", []) or []:
        analysis_by_seq[item["sequence"]] = item
    for item in state.get("soft_results", []) or []:
        analysis_by_seq[item["sequence"]] = item

    valid_card_ids = {c["id"] for c in job_context.get("cards", [])}
    card_title_map = {c["id"]: c.get("title", "") for c in job_context.get("cards", [])}

    # 计算总体评分
    scores = [a["score"] for a in analysis_by_seq.values() if a.get("score")]
    overall_score = round(sum(scores) / len(scores)) if scores else 0

    questions = []
    for qa in all_qa_pairs:
        seq = qa["sequence"]
        is_selected = seq in selected_set
        analysis = analysis_by_seq.get(seq, {}) if is_selected else {}

        expected = analysis.get("expected_answer", "")
        if isinstance(expected, list):
            expected = "；".join(str(e) for e in expected)

        rid = analysis.get("related_card_id")
        related_card_title = ""
        if rid in valid_card_ids:
            related_card_title = card_title_map.get(rid, "")
        else:
            rid = None

        q_data = {
            "sequence": seq,
            "start_time": qa.get("start_time", ""),
            "speaker": qa.get("speaker", ""),
            "question_text": qa.get("question_text", ""),
            "dimension": analysis.get("dimension", "D7 协作沟通"),
            "level": analysis.get("level", "L3"),
            "intent": analysis.get("intent", ""),
            "expected_answer": expected,
            "my_answer": qa.get("my_answer", ""),
            "score": analysis.get("score", 0) if is_selected else 0,
            "feedback": analysis.get("feedback", []) if is_selected else [],
            "suggestions": analysis.get("suggestions", []) if is_selected else [],
            "related_card_id": rid,
            "related_card_title": related_card_title,
        }
        if is_selected and not q_data.get("my_answer"):
            q_data["my_answer"] = _find_my_answer(dialogue, seq)
        questions.append(ReviewedQuestion(**q_data))

    summary = ""
    unselected_count = len(all_qa_pairs) - len(selected_qa_pairs)
    if unselected_count > 0:
        summary = (
            f"本次面试共识别出 {len(all_qa_pairs)} 个问题，"
            f"已对勾选的 {len(selected_qa_pairs)} 个问题进行了详细拆解；"
            f"另有 {unselected_count} 个问题可在问题表汇总中查看。"
        )
    if len(all_qa_pairs) > MAX_QUESTION_TABLE_QA_PAIRS:
        summary += f"\n问题表最多展示前 {MAX_QUESTION_TABLE_QA_PAIRS} 个问题。"

    # 提取 strengths/weaknesses/action_items 从分析结果中
    strengths = []
    weaknesses = []
    action_items = []
    for a in analysis_by_seq.values():
        if a.get("feedback"):
            weaknesses.extend(a["feedback"][:1])
        if a.get("suggestions"):
            action_items.extend(a["suggestions"][:1])
    if not strengths:
        strengths = ["等待评估"]
    if not weaknesses:
        weaknesses = ["等待评估"]
    if not action_items:
        action_items = ["等待评估"]

    result = InterviewReviewResult(
        record_id=record_id,
        user_id=user_id,
        title=record.get("title", ""),
        company=record.get("company", ""),
        position=record.get("position", ""),
        round_type=record.get("round_type", ""),
        overall_score=overall_score,
        summary=summary,
        strengths=strengths[:3],
        weaknesses=weaknesses[:3],
        action_items=action_items[:3],
        questions=questions,
    )

    # 落库
    analysis_dict = result.model_dump(exclude={"record_id", "user_id", "created_at"})
    db_tools.update_interview_record_analysis(record_id, analysis_dict)
    db_tools.delete_interview_qa_pairs_by_record(record_id)
    for q in questions:
        db_tools.insert_interview_qa_pair(
            {
                "record_id": record_id,
                "user_id": user_id,
                "sequence": q.sequence,
                "speaker": q.speaker,
                "start_time": q.start_time,
                "content": q.question_text,
                "is_question": True,
                "question_text": q.question_text,
                "my_answer": q.my_answer,
                "dimension": q.dimension,
                "level": q.level,
                "intent": q.intent,
                "expected_answer": q.expected_answer,
                "feedback": q.feedback,
                "suggestions": q.suggestions,
                "score": q.score,
                "related_card_id": q.related_card_id,
                "related_card_title": q.related_card_title,
            }
        )

    return {"result": result.model_dump()}


def _has_tech(state: Dict[str, Any]) -> str:
    """条件边：判断是否有技术类问题"""
    classified = state.get("classified", {})
    tech = classified.get("tech", [])
    return "tech" if tech else "no_tech"


def _has_soft(state: Dict[str, Any]) -> str:
    """条件边：判断是否有行为/业务类问题"""
    classified = state.get("classified", {})
    soft = classified.get("soft", [])
    return "soft" if soft else "no_soft"


def run_interview_review_workflow(
    record_id: int,
    selected_sequences: List[int],
    user_id: int = 1,
) -> Dict[str, Any]:
    """执行面试复盘详细分析 Workflow"""
    workflow = StateGraph(InterviewReviewState)

    # 注册节点
    workflow.add_node("load_data", _load_data)
    workflow.add_node("route", _route_questions)
    workflow.add_node("tech_analyze", _tech_analyze)
    workflow.add_node("soft_analyze", _soft_analyze)
    workflow.add_node("gate", _gate_check)
    workflow.add_node("assemble", _assemble_result)

    # 边
    workflow.add_edge(START, "load_data")
    workflow.add_edge("load_data", "route")

    # Router → Tech/Soft（条件边）
    workflow.add_conditional_edges(
        "route",
        _has_tech,
        {"tech": "tech_analyze", "no_tech": "gate"},
    )
    workflow.add_conditional_edges(
        "route",
        _has_soft,
        {"soft": "soft_analyze", "no_soft": "gate"},
    )

    # Tech/Soft → Gate
    workflow.add_edge("tech_analyze", "gate")
    workflow.add_edge("soft_analyze", "gate")

    # Gate → Assemble → End
    workflow.add_edge("gate", "assemble")
    workflow.add_edge("assemble", END)

    # 编译并执行
    app = workflow.compile()
    initial_state: InterviewReviewState = {
        "record_id": record_id,
        "user_id": user_id,
        "selected_sequences": selected_sequences,
        "record": {},
        "dialogue": [],
        "all_qa_pairs": [],
        "selected_qa_pairs": [],
        "job_context": {},
        "jd_text": "",
        "cards_text": "",
        "company": "",
        "position": "",
        "round_type": "",
        "classified": {},
        "tech_results": [],
        "soft_results": [],
        "gate_report": {},
        "result": None,
    }
    result = app.invoke(initial_state)
    return result.get("result", {})
