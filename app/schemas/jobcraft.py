"""
JobCraft 求职助手 Pydantic 数据模型

所有 LLM 结构化输出、API 请求/响应共用此模块，确保字段一致。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 经历卡 — 新架构: raw_text + tags + ai_structured 缓存
# ============================================================


class AchievementAction(BaseModel):
    """单条成就中的 Action 子结构"""

    main: str = Field(..., description="主要行为")
    difficulty: Optional[str] = Field(None, description="遇到的困难")
    resolution: Optional[str] = Field(None, description="如何解决")


class Achievement(BaseModel):
    """AI 从 raw_text 中抽取的单条成就"""

    title: str = Field(..., description="成就标题")
    situation: str = Field(default="", description="背景/情境 (S)")
    action: AchievementAction = Field(
        default_factory=lambda: AchievementAction(main=""),
        description="行动 (A)",
    )
    result: str = Field(default="", description="结果/收益 (R)")


class CardStructuredCache(BaseModel):
    """经历卡 AI 结构化缓存（调用时生成，可刷新）"""

    summary: str = Field(default="", description="一句话总结")
    achievements: List[Achievement] = Field(default_factory=list)


class ResumeExperience(BaseModel):
    """从简历中解析出的一段经历（对应一张经历卡）"""

    company: str = Field(default="", description="公司名")
    role: str = Field(default="", description="职位/角色")
    period: str = Field(default="", description="任职时间，如 '2020.03 - 2022.06'")
    title: str = Field(default="", description="经历标题")
    summary: str = Field(default="", description="一句话总概括，含背景+行动+量化成果")
    card_type: str = Field(
        default="work",
        description="经历类型: work(工作) / intern(实习) / project(项目)",
    )
    achievements: List[Achievement] = Field(
        default_factory=list, description="工作项 bullet 列表"
    )


class ResumeParseResult(BaseModel):
    """简历解析结果：仅提取项目/实习/工作经历，跳过个人信息/技能/评价"""

    entries: List[ResumeExperience] = Field(default_factory=list)


class ResumePersonalInfo(BaseModel):
    """简历头部个人信息（用户补充）"""

    name: str = Field("", description="姓名")
    phone: str = Field("", description="电话")
    email: str = Field("", description="邮箱")
    city: str = Field("", description="城市")
    github: str = Field("", description="GitHub/作品链接")
    education: str = Field("", description="学历，如'本科·计算机'")
    years: str = Field("", description="工作年限，如'5 年'")


class ExperienceCardSchema(BaseModel):
    """服务端经历卡完整结构（响应用）"""

    id: int
    user_id: int = 1
    title: str = Field(..., description="经历标题")
    raw_text: str = Field(..., description="用户原始文本")
    tags: List[str] = Field(default_factory=list, description="扁平标签")
    ai_structured: Optional[CardStructuredCache] = Field(
        None, description="AI 结构化缓存（可空，调用时按需生成）"
    )
    # 旧字段保留向后兼容
    summary: str = Field(
        default="", description="摘要（从 ai_structured 或 raw_text 派生）"
    )
    content: str = Field(default="", description="完整内容（向后兼容用）")
    company: Optional[str] = None
    role: Optional[str] = None
    period: Optional[str] = None
    source: str = "manual"
    card_type: str = Field(
        "work", description="卡片分类: work(工作) / intern(实习) / project(项目)"
    )
    version: int = 1
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExperienceCardCreate(BaseModel):
    """前端创建经历卡请求体"""

    user_id: int = 1
    title: str = Field(..., description="经历标题")
    raw_text: str = Field(..., description="原始文本")
    tags: List[str] = Field(default_factory=list, description="扁平标签")
    summary: Optional[str] = None
    content: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    period: Optional[str] = None
    card_type: str = Field(
        "work", description="卡片分类: work(工作) / intern(实习) / project(项目)"
    )
    background: Optional[str] = None
    problem: Optional[str] = None
    solution: Optional[str] = None
    execution: Optional[str] = None
    result: Optional[str] = None
    dimensions: Optional[List[str]] = None


class ExperienceCardUpdate(BaseModel):
    """前端更新经历卡请求体（全部可选）"""

    title: Optional[str] = None
    raw_text: Optional[str] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    period: Optional[str] = None
    card_type: Optional[str] = None
    background: Optional[str] = None
    problem: Optional[str] = None
    solution: Optional[str] = None
    execution: Optional[str] = None
    result: Optional[str] = None
    dimensions: Optional[List[str]] = None
    is_active: Optional[bool] = None


# ============================================================
# JD / ATS 相关
# ============================================================


class DimensionRequirement(BaseModel):
    """JD 对某一维度的要求"""

    dimension: str = Field(..., description="维度编码 D1-D8")
    level: int = Field(3, ge=1, le=5, description="要求等级 1-5")
    evidence: str = Field("", description="JD 中体现该要求的原文/关键词")


class SubtextDecode(BaseModel):
    """JD 潜台词解码：表面要求 → 实际期望能力"""

    surface_requirement: str = Field("", description="JD 表面要求，如'熟悉分布式系统'")
    hidden_meaning: str = Field(
        "", description="潜台词/实际期望，如'需要有高并发实践经验'"
    )
    key_ability: str = Field("", description="真正需要证明的关键能力")
    how_to_prove: str = Field("", description="如何用经历/量化成果证明")


class JDRequirements(BaseModel):
    """JD 需求提取结果"""

    position_title: str = Field("", description="岗位名称")
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    nice_to_have: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    dimension_requirements: List[DimensionRequirement] = Field(default_factory=list)
    salary_range: Optional[str] = Field(None)
    work_mode: Optional[str] = Field(None)
    location: Optional[str] = Field(None)


class ATSProfile(BaseModel):
    """JD ATS 解析结果"""

    job_title: str = Field("")
    department: Optional[str] = Field(None)
    location: Optional[str] = Field(None)
    salary: Optional[str] = Field(None)
    years_of_experience: Optional[str] = Field(None)
    education: Optional[str] = Field(None)
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    key_metrics: List[str] = Field(default_factory=list)
    culture_keywords: List[str] = Field(default_factory=list)
    dimension_requirements: List[DimensionRequirement] = Field(default_factory=list)
    subtext_decoded: List[SubtextDecode] = Field(default_factory=list)
    raw_summary: str = Field("", description="JD 原文摘要")


# ============================================================
# 匹配与建议
# ============================================================


class PerCardScore(BaseModel):
    """单张经历卡的匹配评分"""

    card_id: int
    score: float = Field(0.0, ge=0, le=100, description="融合后最终分数")
    local_score: float = Field(0.0, ge=0, le=100, description="本地关键词匹配分数")
    llm_score: float = Field(0.0, ge=0, le=100, description="LLM 语义匹配分数")
    matched: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)


class SuggestionItem(BaseModel):
    """单条优化建议"""

    card_id: Optional[int] = None
    type: str = Field("", description="gap / rewrite / order / supplement")
    message: str = Field("")
    priority: int = Field(3, ge=1, le=5)
    optimization: Optional[str] = Field(None, description="改写建议或补充文案")


class SuggestionsResult(BaseModel):
    """优化建议集合"""

    gap_analysis: str = ""
    gap_items: List[str] = Field(default_factory=list)
    suggestions: List[SuggestionItem] = Field(default_factory=list)


class CardLLMMatchItem(BaseModel):
    """单张卡片的 LLM 语义匹配结果"""

    card_id: int
    match: float = Field(0.0, ge=0, le=100)
    covered: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    reason: str = ""


# ============================================================
# 岗位分析结果
# ============================================================


class JobAnalysisResult(BaseModel):
    """岗位分析落库及返回结果"""

    job_analysis_id: int
    user_id: int = 1
    company: str = ""
    position: str = ""
    jd_text: str = ""
    jd_requirements: Optional[JDRequirements] = None
    ats_profile: Optional[ATSProfile] = None
    company_context: Optional[Dict[str, Any]] = None
    match_score: Optional[float] = None
    match_level: Optional[str] = None
    customization_needed: Optional[bool] = None
    gap_analysis: Optional[str] = None
    gap_items: List[str] = Field(default_factory=list)
    per_card_scores: List[PerCardScore] = Field(default_factory=list)
    suggestions: List[SuggestionItem] = Field(default_factory=list)
    dimension_requirements: List[DimensionRequirement] = Field(default_factory=list)
    resume_markdown: Optional[str] = None
    created_at: Optional[str] = None


# ============================================================
# 面试复盘
# ============================================================


class ReviewedQuestion(BaseModel):
    """面试复盘中拆解出的单个问题"""

    sequence: int = Field(0, description="对话顺序")
    start_time: str = Field("", description="问题出现时间，如 2:12")
    speaker: str = Field("", description="发言人")
    question_text: str = Field(..., description="面试官问题原文")
    dimension: str = Field("", description="归属维度 D1-D8")
    level: str = Field("L3", description="难度等级 L1-L5")
    intent: str = Field("", description="面试官意图")
    expected_answer: str = Field("", description="标准答案")
    my_answer: str = Field("", description="我的回答")
    score: int = Field(60, ge=0, le=100, description="回答评分")
    feedback: List[str] = Field(default_factory=list, description="诊断反馈")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    related_card_id: Optional[int] = Field(None, description="推荐关联的经历卡 ID")
    related_card_title: Optional[str] = Field(None, description="推荐关联的经历卡标题")


class InterviewReviewResult(BaseModel):
    """面试复盘分析结果"""

    record_id: int
    user_id: int = 1
    title: str = ""
    company: str = ""
    position: str = ""
    round_type: str = ""
    overall_score: int = Field(60, ge=0, le=100)
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    questions: List[ReviewedQuestion] = Field(default_factory=list)
    created_at: Optional[str] = None


# ============================================================
# 面试准备稿
# ============================================================


class DimensionQuestion(BaseModel):
    """某一维度的面试题"""

    dimension: str
    question: str
    answer_points: List[str] = Field(default_factory=list)
    card_ids: List[int] = Field(default_factory=list)


class InterviewPrepResult(BaseModel):
    """面试准备稿结果"""

    job_analysis_id: int
    round_type: str = "技术面"
    duration: str = "10-15 分钟"
    elevator_pitch: str = ""
    dimension_questions: List[DimensionQuestion] = Field(default_factory=list)
    full_version: str = ""
    html_content: str = ""
    created_at: Optional[str] = None


# ============================================================
# 公司背调
# ============================================================


class CompanyResearchInfo(BaseModel):
    """公司背调信息结构"""

    basic: Dict[str, Any] = Field(default_factory=dict)
    business: Dict[str, Any] = Field(default_factory=dict)
    funding: Dict[str, Any] = Field(default_factory=dict)
    team: Dict[str, Any] = Field(default_factory=dict)
    industry: Dict[str, Any] = Field(default_factory=dict)
    news: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class CompanyResearchResult(BaseModel):
    """公司背调返回结果"""

    company: str
    info: CompanyResearchInfo = Field(default_factory=CompanyResearchInfo)
    cached_at: Optional[str] = None
    from_cache: bool = False
    fresh: bool = False
