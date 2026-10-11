"""Surface 评测共享 schema 与 L1 结构合规检查（T-EVAL-2 A4）。

三层评测方法论（evaluation-design-v1.md §方法论）：
- L1 结构合规：确定性、零 LLM 成本，Pydantic 校验 + 规则检查，进 CI。
- L2 LLM-as-judge：GLM-4.7 裁判按 rubric 打分，temperature=0。
- L3 人工校准：每链 5-10 case 人工标注，Cohen's κ ≥ 0.6 才启用裁判结论。

本模块提供：
- ``JudgeScore``：L2 裁判统一输出 schema（所有链共用同一 rubric 打分契约）。
- ``L1Finding``：单条 L1 检查发现（确定性，无 LLM）。
- ``check_review_l1`` / ``check_prep_l1``：逐链 L1 规则检查函数。
- ``summarize_l1``：把 findings 聚合成 L1 报告 dict。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

# ---- L2 裁判统一输出 schema ----


class JudgeScore(BaseModel):
    """L2 LLM-as-judge 统一输出契约（所有链共用）。

    rubric 四维（0-10 整数）：
    - accuracy：与输入材料的一致性（不编造、不超出 JD/逐字稿范围）
    - completeness：关键内容覆盖度（该有的段落/字段是否齐全）
    - actionability：对求职者的真实可用性（建议/逐字稿能否直接用）
    - safety：无幻觉风险、无违规内容（编造事实/歧视/敏感信息为 0 分项）

    :param dimensions: 四维得分
    :param strengths: 本条输出的亮点（≤3 条，中文）
    :param weaknesses: 本条输出的不足（≤3 条，中文）
    :param overall: 总体分（0-10），由四维加权得出
    :param rationale: 总体判断的一句话理由
    """

    accuracy: int = Field(..., ge=0, le=10, description="与输入材料一致性 0-10")
    completeness: int = Field(..., ge=0, le=10, description="关键内容覆盖度 0-10")
    actionability: int = Field(..., ge=0, le=10, description="对求职者可用性 0-10")
    safety: int = Field(..., ge=0, le=10, description="无幻觉/无违规 0-10")
    strengths: list[str] = Field(default_factory=list, max_length=3, description="亮点")
    weaknesses: list[str] = Field(
        default_factory=list, max_length=3, description="不足"
    )
    overall: int = Field(..., ge=0, le=10, description="总体分 0-10")
    rationale: str = Field("", description="总体判断一句话理由")


# ---- L1 检查结果 ----


class L1Finding(BaseModel):
    """单条 L1 结构合规发现（确定性检查，无 LLM）。

    :param case_id: 所属 case
    :param check: 检查项名（如 ``schema_valid`` / ``score_range``）
    :param passed: 是否通过
    :param detail: 说明（失败时必填，成功可空）
    """

    case_id: str
    check: str
    passed: bool
    detail: str = ""


def summarize_l1(findings: list[L1Finding]) -> dict[str, Any]:
    """把 findings 聚合成 L1 报告。

    :param findings: 全部发现
    :return: {"total", "passed", "failed", "pass_rate", "failures"}
    """
    total = len(findings)
    passed = sum(1 for f in findings if f.passed)
    failures = [f.model_dump() for f in findings if not f.passed]
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 1.0,
        "failures": failures,
    }


# ---- L1 检查：复盘链 ----


def check_review_l1(case_id: str, result: Any) -> list[L1Finding]:
    """对单条复盘输出执行 L1 结构合规检查。

    检查项：
    1. ``schema_valid``：result 能通过 InterviewReviewResult 校验
    2. ``overall_score_range``：overall_score ∈ [0, 100]
    3. ``question_coverage``：questions 非空
    4. ``score_range``：每题 score ∈ [0, 100]
    5. ``dimension_format``：每题 dimension 形如 D1-D8
    6. ``feedback_nonempty``：每题 feedback / suggestions 非空（选中题应有诊断）
    7. ``strengths_weaknesses``：strengths / weaknesses / action_items 非空

    :param case_id: case 标识
    :param result: 待检查的复盘结果（dict 或已校验对象）
    :return: findings 列表
    """
    findings: list[L1Finding] = []

    # 1. schema_valid
    try:
        from app.schemas.jobcraft import InterviewReviewResult

        obj = (
            result if hasattr(result, "model_dump") else InterviewReviewResult(**result)
        )
        findings.append(L1Finding(case_id=case_id, check="schema_valid", passed=True))
    except Exception as exc:
        findings.append(
            L1Finding(
                case_id=case_id,
                check="schema_valid",
                passed=False,
                detail=f"InterviewReviewResult 校验失败: {exc}",
            )
        )
        return findings  # 后续检查依赖合法对象，直接返回

    # 2. overall_score_range
    os_ok = 0 <= obj.overall_score <= 100
    findings.append(
        L1Finding(
            case_id=case_id,
            check="overall_score_range",
            passed=os_ok,
            detail="" if os_ok else f"overall_score={obj.overall_score} 越界",
        )
    )

    # 3. question_coverage
    q_ok = len(obj.questions) > 0
    findings.append(
        L1Finding(
            case_id=case_id,
            check="question_coverage",
            passed=q_ok,
            detail="" if q_ok else "questions 为空",
        )
    )

    # 4-6. 逐题检查
    # dimension 实际 wire 格式为 "D7 协作沟通"（码+名，agent 输出原样透传，
    # schema 无格式约束），前缀匹配 D1-D8 即可
    dim_re = re.compile(r"^D[1-8]")
    for q in obj.questions:
        seq = q.sequence
        s_ok = 0 <= q.score <= 100
        findings.append(
            L1Finding(
                case_id=case_id,
                check=f"score_range_q{seq}",
                passed=s_ok,
                detail="" if s_ok else f"Q{seq} score={q.score} 越界",
            )
        )
        d_ok = bool(dim_re.match(q.dimension or ""))
        findings.append(
            L1Finding(
                case_id=case_id,
                check=f"dimension_format_q{seq}",
                passed=d_ok,
                detail="" if d_ok else f"Q{seq} dimension={q.dimension!r} 不符 D1-D8",
            )
        )
        fb_ok = bool(q.feedback) and bool(q.suggestions)
        findings.append(
            L1Finding(
                case_id=case_id,
                check=f"feedback_nonempty_q{seq}",
                passed=fb_ok,
                detail=""
                if fb_ok
                else f"Q{seq} feedback/suggestions 有空（feedback={len(q.feedback)}, suggestions={len(q.suggestions)}）",
            )
        )

    # 7. strengths_weaknesses
    sw_ok = bool(obj.strengths) and bool(obj.weaknesses) and bool(obj.action_items)
    findings.append(
        L1Finding(
            case_id=case_id,
            check="strengths_weaknesses",
            passed=sw_ok,
            detail=""
            if sw_ok
            else f"strengths={len(obj.strengths)}, weaknesses={len(obj.weaknesses)}, action_items={len(obj.action_items)} 有空",
        )
    )

    return findings


# ---- L1 检查：prep 链 ----


def check_prep_l1(case_id: str, result: Any) -> list[L1Finding]:
    """对单条 prep 逐字稿输出执行 L1 结构合规检查。

    检查项：
    1. ``schema_valid``：result 能通过 InterviewPrepLLMOutput 校验（关键字段必填非空）
    2. ``elevator_pitch_nonempty``：elevator_pitch 非空
    3. ``full_version_nonempty``：full_version 非空
    4. ``html_content_nonempty``：html_content 非空
    5. ``dimension_questions_coverage``：dimension_questions 非空
    6. ``dimension_format``：每个 question 的 dimension 形如 D1-D8
    7. ``answer_points_nonempty``：每个 question 的 answer_points 非空

    :param case_id: case 标识
    :param result: 待检查的 prep 结果（dict 或已校验对象）
    :return: findings 列表
    """
    findings: list[L1Finding] = []

    # 1. schema_valid
    try:
        from app.schemas.jobcraft import InterviewPrepLLMOutput

        obj = (
            result
            if hasattr(result, "model_dump")
            else InterviewPrepLLMOutput(**result)
        )
        findings.append(L1Finding(case_id=case_id, check="schema_valid", passed=True))
    except Exception as exc:
        findings.append(
            L1Finding(
                case_id=case_id,
                check="schema_valid",
                passed=False,
                detail=f"InterviewPrepLLMOutput 校验失败: {exc}",
            )
        )
        return findings

    # 2-4. 关键字段非空（schema 已强制，此处再显式检查一层防御未来 schema 放宽）
    ep_ok = bool(obj.elevator_pitch.strip())
    findings.append(
        L1Finding(
            case_id=case_id,
            check="elevator_pitch_nonempty",
            passed=ep_ok,
            detail="" if ep_ok else "elevator_pitch 为空",
        )
    )
    fv_ok = bool(obj.full_version.strip())
    findings.append(
        L1Finding(
            case_id=case_id,
            check="full_version_nonempty",
            passed=fv_ok,
            detail="" if fv_ok else "full_version 为空",
        )
    )
    html_ok = bool(obj.html_content.strip())
    findings.append(
        L1Finding(
            case_id=case_id,
            check="html_content_nonempty",
            passed=html_ok,
            detail="" if html_ok else "html_content 为空",
        )
    )

    # 5. dimension_questions_coverage
    dq_ok = len(obj.dimension_questions) > 0
    findings.append(
        L1Finding(
            case_id=case_id,
            check="dimension_questions_coverage",
            passed=dq_ok,
            detail="" if dq_ok else "dimension_questions 为空",
        )
    )

    # 6-7. 逐题检查（dimension 前缀匹配 D1-D8，允许 "D1 技术深度" 等码+名格式）
    dim_re = re.compile(r"^D[1-8]")
    for i, dq in enumerate(obj.dimension_questions):
        d_ok = bool(dim_re.match(dq.dimension or ""))
        findings.append(
            L1Finding(
                case_id=case_id,
                check=f"dimension_format_q{i}",
                passed=d_ok,
                detail="" if d_ok else f"第{i}题 dimension={dq.dimension!r} 不符 D1-D8",
            )
        )
        ap_ok = bool(dq.answer_points)
        findings.append(
            L1Finding(
                case_id=case_id,
                check=f"answer_points_nonempty_q{i}",
                passed=ap_ok,
                detail="" if ap_ok else f"第{i}题 answer_points 为空",
            )
        )

    return findings
