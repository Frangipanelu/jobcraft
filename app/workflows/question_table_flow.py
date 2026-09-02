"""
问题表生成 Workflow

流程：
  1. load_record（无 LLM）：读取面试记录、解析对话、构建 QA 对、获取 JD 上下文
  2. generate_intents（LLM）：QuestionTableAgent 为每个问题生成意图/维度/难度
  3. persist（无 LLM）：合并结果并落库 interview_qa_pairs
"""

import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.question_table_agent import QuestionTableAgent
from app.tools import db_tools
from app.tools.interview_review import (
    _build_qa_pairs,
    _parse_dialogue,
)

logger = logging.getLogger(__name__)


class QuestionTableState(TypedDict):
    record_id: int
    user_id: int
    # 加载的数据
    record: Dict[str, Any]
    qa_pairs: List[Dict[str, Any]]
    jd_text: str
    # 生成结果
    intent_by_seq: Dict[int, Dict[str, Any]]
    questions: Optional[List[Dict[str, Any]]]


def _load_record(state: Dict[str, Any]) -> Dict[str, Any]:
    """第 1 步：加载面试记录与 QA 对（无 LLM）"""
    record_id = state["record_id"]
    user_id = state.get("user_id")

    record = db_tools.get_interview_record(record_id, user_id)
    if not record:
        raise ValueError(f"面试记录不存在: {record_id}")

    dialogue = _parse_dialogue(record.get("raw_text", ""))
    qa_pairs = _build_qa_pairs(dialogue)

    jd_text = ""
    if record.get("job_analysis_id"):
        analysis = db_tools.get_job_analysis(record["job_analysis_id"], user_id)
        if analysis:
            jd_text = analysis.get("jd_text", "")

    return {
        "record": record,
        "qa_pairs": qa_pairs,
        "jd_text": jd_text,
    }


def _generate_intents(state: Dict[str, Any]) -> Dict[str, Any]:
    """第 2 步：LLM 生成意图识别"""
    qa_pairs = state.get("qa_pairs", [])
    if not qa_pairs:
        return {"intent_by_seq": {}}
    record = state.get("record", {})
    agent = QuestionTableAgent()
    out = agent.run(
        {
            "company": record.get("company", ""),
            "position": record.get("position", ""),
            "round_type": record.get("round_type", ""),
            "qa_pairs": qa_pairs,
            "jd_text": state.get("jd_text", ""),
        }
    )
    return {"intent_by_seq": out["intent_by_seq"]}


def _persist(state: Dict[str, Any]) -> Dict[str, Any]:
    """第 3 步：合并意图并落库（无 LLM）"""
    record_id = state["record_id"]
    user_id = state.get("user_id", 1)
    qa_pairs = state.get("qa_pairs", [])
    intent_by_seq = state.get("intent_by_seq", {})

    result = []
    for qa in qa_pairs:
        seq = qa["sequence"]
        intent_data = intent_by_seq.get(seq, {})
        result.append(
            {
                "sequence": seq,
                "start_time": qa.get("start_time", ""),
                "speaker": qa.get("speaker", ""),
                "question_text": qa.get("question_text", ""),
                "my_answer": qa.get("my_answer", ""),
                "intent": intent_data.get("intent", ""),
                "dimension": intent_data.get("dimension", "D7 协作沟通"),
                "level": intent_data.get("level", "L3"),
            }
        )

    # 落库：先删除旧的 QA 对，再写入新的问题表（状态为未详细分析）
    db_tools.delete_interview_qa_pairs_by_record(record_id)

    for item in result:
        db_tools.insert_interview_qa_pair(
            {
                "record_id": record_id,
                "user_id": user_id,
                "sequence": item["sequence"],
                "speaker": item["speaker"],
                "start_time": item["start_time"],
                "content": item["question_text"],
                "is_question": True,
                "question_text": item["question_text"],
                "my_answer": item["my_answer"],
                "dimension": item["dimension"],
                "level": item["level"],
                "intent": item["intent"],
                "expected_answer": "",
                "feedback": [],
                "suggestions": [],
                "score": 0,
                "related_card_id": None,
                "related_card_title": "",
            }
        )

    db_tools.update_interview_record_status(record_id, "question_table")
    logger.info("问题表生成完成 record_id=%s questions=%s", record_id, len(result))
    return {"questions": result}


def run_question_table_workflow(
    record_id: int,
    user_id: int = 1,
) -> List[Dict[str, Any]]:
    """执行问题表生成 Workflow，返回问题列表。"""
    workflow = StateGraph(QuestionTableState)
    workflow.add_node("load_record", _load_record)
    workflow.add_node("generate_intents", _generate_intents)
    workflow.add_node("persist", _persist)
    workflow.add_edge(START, "load_record")
    workflow.add_edge("load_record", "generate_intents")
    workflow.add_edge("generate_intents", "persist")
    workflow.add_edge("persist", END)

    app = workflow.compile()
    initial_state: QuestionTableState = {
        "record_id": record_id,
        "user_id": user_id,
        "record": {},
        "qa_pairs": [],
        "jd_text": "",
        "intent_by_seq": {},
        "questions": None,
    }
    result = app.invoke(initial_state)
    return result.get("questions", [])
