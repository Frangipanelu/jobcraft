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


class CardStructuredCacheWithTags(CardStructuredCache):
    """STAR 抽取同一次 LLM 调用的输出（含扁平标签，EXPERIENCE_SPEC §26/§55）"""

    tags: List[str] = Field(default_factory=list, description="扁平标签（3-5 个）")


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
    # 统一字段契约（EXPERIENCE_SPEC §30.4）：S / T 槽位 + A / R 槽位
    background: Optional[str] = Field(None, description="STAR 背景槽位 (S)，列存储")
    problem: Optional[str] = Field(None, description="STAR 任务槽位 (T)，列存储")
    actions: List[str] = Field(
        default_factory=list,
        description="STAR 行动槽位 (A)，聚合自 ai_structured.achievements[].action.main",
    )
    results: List[str] = Field(
        default_factory=list,
        description="STAR 结果槽位 (R)，聚合自 ai_structured.achievements[].result",
    )
    solution: Optional[str] = Field(
        None, description="已废弃 (DEPRECATED)，新实现请使用 actions"
    )
    execution: Optional[str] = Field(
        None, description="已废弃 (DEPRECATED)，新实现请使用 results"
    )
    result: Optional[str] = None
    dimensions: Optional[List[str]] = None
    version: int = 1
    is_active: bool = True
    # EXP-P1-03：is_confirmed=False 表示 confirmUpload 入库草稿（定稿见 §34.7）
    is_confirmed: bool = True
    fields: Optional[Dict[str, Any]] = Field(
        None, description="自定义结构字段（方向/表达评估扩展用）"
    )
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExperienceCardCreate(BaseModel):
    """前端创建经历卡请求体"""

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
    actions: Optional[List[str]] = Field(
        default_factory=list,
        description="STAR 行动槽位 (A)，写入 ai_structured.achievements[].action.main",
    )
    results: Optional[List[str]] = Field(
        default_factory=list,
        description="STAR 结果槽位 (R)，写入 ai_structured.achievements[].result",
    )
    solution: Optional[str] = Field(
        None,
        description="已废弃 (DEPRECATED)，保留兼容前端旧写入；新实现请使用 actions",
    )
    execution: Optional[str] = Field(
        None,
        description="已废弃 (DEPRECATED)，保留兼容前端旧写入；新实现请使用 results",
    )
    result: Optional[str] = None
    dimensions: Optional[List[str]] = None
    fields: Optional[Dict[str, Any]] = Field(
        None, description="自定义结构字段（方向/表达评估扩展用）"
    )


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
    card_type: Optional[str] = Field(
        None, description="卡片分类，仅允许 work / intern / project"
    )
    background: Optional[str] = None
    problem: Optional[str] = None
    actions: Optional[List[str]] = Field(
        None,
        description="STAR 行动槽位 (A)，合并写入 ai_structured.achievements[].action.main",
    )
    results: Optional[List[str]] = Field(
        None,
        description="STAR 结果槽位 (R)，合并写入 ai_structured.achievements[].result",
    )
    solution: Optional[str] = Field(
        None,
        description="已废弃 (DEPRECATED)，保留兼容前端旧写入；新实现请使用 actions",
    )
    execution: Optional[str] = Field(
        None,
        description="已废弃 (DEPRECATED)，保留兼容前端旧写入；新实现请使用 results",
    )
    result: Optional[str] = None
    dimensions: Optional[List[str]] = None
    fields: Optional[Dict[str, Any]] = Field(
        None, description="自定义结构字段（方向/表达评估扩展用）"
    )
    is_active: Optional[bool] = None
    # EXP-P1-03：卡片页保存携带 true 触发定稿（用例见 §34.7）
    is_confirmed: Optional[bool] = Field(
        None, description="true 时在同一事务内完成定稿（写 V1 哨兵基线并置位）"
    )


class CardVersionRead(BaseModel):
    """经历卡一条版本快照（card_versions 行，EXP-P1-05 §28）"""

    id: int = Field(..., description="版本记录主键")
    card_id: int = Field(..., description="经历卡 id")
    version_type: str = Field(..., description="original / user_edit / ai_polish / ...")
    source_type: str = Field(..., description="来源域，如 original / card_edit")
    source_id: int = Field(0, description="来源对象 id，哨兵基线为 0")
    title: Optional[str] = None
    raw_text: str = Field("", description="快照原文（可恢复）")
    tags: List[str] = Field(default_factory=list)
    note: Optional[str] = None
    created_at: Optional[str] = None


class CardVersionListResponse(BaseModel):
    """经历卡版本历史响应"""

    card_id: int = Field(..., description="经历卡 id")
    current_version: int = Field(1, description="当前主表 version（V 编号）")
    versions: List[CardVersionRead] = Field(
        default_factory=list, description="版本快照（新→旧）"
    )


# ============================================================
# JD / ATS 相关
# ============================================================


class DimensionRequirement(BaseModel):
    """JD 对某一维度的要求"""

    dimension: str = Field(..., description="维度编码 D1-D8")
    level: int = Field(3, ge=1, le=5, description="要求等级 1-5")
    evidence: str = Field("", description="JD 中体现该要求的原文/关键词")


class EvidenceItem(BaseModel):
    """JD 证据条目：每条输出值必须由 JD 原文佐证（evidence-first 模式）"""

    id: int = Field(..., description="证据编号，从 1 开始")
    field: str = Field(
        ...,
        description=(
            "证据支撑的输出字段：required_skills / preferred_skills / "
            "responsibilities / culture_keywords / key_metrics / "
            "dimension_D1..dimension_D8 / salary / location / subtext"
        ),
    )
    span: str = Field(..., description="JD 原文逐字摘录（不加解释）")
    derived: str = Field(
        ...,
        description="从证据提炼出的字段值（列表字段=该条目；dimension_*=level 等级 1-5）",
    )


class SubtextDecode(BaseModel):
    """JD 潜台词解码：表面要求 → 实际期望能力"""

    surface_requirement: str = Field("", description="JD 表面要求，如'熟悉分布式系统'")
    hidden_meaning: str = Field(
        "", description="潜台词/实际期望，如'需要有高并发实践经验'"
    )
    key_ability: str = Field("", description="真正需要证明的关键能力")
    how_to_prove: str = Field("", description="如何用经历/量化成果证明")
    confidence: float = Field(
        0.5, ge=0.0, le=1.0, description="模型自评把握度 0-1，供人工复核按置信度排序"
    )


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


class KeywordSignal(BaseModel):
    """算法抽取的招聘信号关键词（v0.5 §十五/§十六）。"""

    keyword: str
    category: str = Field(description="technical | product | soft")
    importance: str = Field(description="high | medium | low")
    score: int = Field(description="score = section_weight + strength + freq")
    evidence: str = Field(description="首次命中的 JD 原文条目")


class AmbiguousDecision(BaseModel):
    """LLM 对算法不确定条目的歧义裁决（v0.5 §八 UNKNOWN→LLM fallback）。"""

    item_id: str = Field(description="对应传入条目 id")
    label: str = Field(description="required | preferred | responsibility | soft_skill")
    reason: str = Field("", description="裁决理由")


class AtsInference(BaseModel):
    """收窄后 LLM 只负责的推理结果（v0.5 Task06）。

    L1 管道已确定性产出技能/职责/学历/年限/指标等字段；LLM 仅补：
    岗位名、文化关键词、D1-D8 维度、潜台词、以及算法 UNKNOWN/低置信条目的裁决。
    """

    job_title: str = Field("", description="岗位名称")
    culture_keywords: List[str] = Field(default_factory=list)
    dimension_requirements: List[DimensionRequirement] = Field(default_factory=list)
    subtext_decoded: List[SubtextDecode] = Field(default_factory=list)
    ambiguous: List[AmbiguousDecision] = Field(default_factory=list)


class StructuredRequirementItem(BaseModel):
    """前端结构化 JD 的任职要求条目（用户在前端已分好类）"""

    text: str = Field(..., description="要求原文")
    tag: str = Field(
        "required",
        description="hard(硬性门槛/学历年限) | required(必选) | preferred(加分)",
    )


class StructuredJDAnalyzePayload(BaseModel):
    """前端结构化 JD 分析请求（不再需要整段原文让 L1 猜区块）"""

    company: str = Field("", description="公司名称")
    position: str = Field("", description="岗位名称")
    duties: List[str] = Field(
        default_factory=list, description="岗位职责逐条（前端已分好类）"
    )
    requirements: List[StructuredRequirementItem] = Field(
        default_factory=list, description="任职要求逐条（用户已打标签）"
    )


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
    soft_skills: List[str] = Field(
        default_factory=list, description="软能力关键词（算法抽取，可选字段）"
    )
    core_keywords: List[KeywordSignal] = Field(
        default_factory=list, description="招聘信号关键词（算法抽取，v0.5 §十五/十六）"
    )
    dimension_requirements: List[DimensionRequirement] = Field(default_factory=list)
    subtext_decoded: List[SubtextDecode] = Field(default_factory=list)
    evidence_items: List[EvidenceItem] = Field(
        default_factory=list, description="证据列表（evidence-first Prompt C 模式产出）"
    )
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

    id: Optional[int] = Field(
        None, description="后端落库后的真实 record id（生成时填充）"
    )
    job_analysis_id: int
    round_type: str = "技术面"
    duration: str = "10-15 分钟"
    elevator_pitch: str = ""
    dimension_questions: List[DimensionQuestion] = Field(default_factory=list)
    full_version: str = ""
    html_content: str = ""
    created_at: Optional[str] = None
    company_research: Optional[Dict[str, Any]] = Field(default_factory=dict)


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
