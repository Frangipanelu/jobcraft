/**
 * 后端 API 响应类型（snake_case，wire 格式）
 *
 * 双层类型架构说明：
 * - 本文件（api/types.ts）：描述后端 HTTP 响应结构（snake_case），
 *   仅用于 api/* 层与 JobCraftContext 映射层内部。
 * - src/types/jobcraft.ts：camelCase 领域模型，被各业务组件消费。
 * - JobCraftContext.tsx 中 3 个 mapper（cardToExperience/analysisToJD/submissionToJob）
 *   负责两层的转换桥接。
 * 由此隔离「后端契约」与「前端领域模型」，避免组件直接耦合后端字段命名。
 */

// ============================================================
// 通用
// ============================================================

export interface APIResponse<T = Record<string, unknown>> {
  code: number
  msg: string
  data: T
}

// ============================================================
// 经历卡
// ============================================================

export interface AchievementAction {
  main: string
  difficulty?: string | null
  resolution?: string | null
}

export interface Achievement {
  title: string
  situation?: string
  action?: AchievementAction
  result?: string
}

export interface CardStructuredCache {
  summary?: string
  achievements?: Achievement[]
}

export interface ExperienceCard {
  id: number
  user_id: number
  title: string
  raw_text: string
  tags: string[]
  ai_structured: CardStructuredCache | null
  summary?: string
  content?: string
  company?: string | null
  role?: string | null
  period?: string | null
  // 统一字段契约（EXPERIENCE_SPEC §30.4）：S / T 槽位 + A / R 槽位
  background?: string | null
  problem?: string | null
  actions?: string[]
  results?: string[]
  source: string
  card_type: string
  version: number
  is_active: boolean
  // EXP-P1-03：False 表示 confirmUpload 入库草稿（未动效）；card 页定稿后转 True
  is_confirmed: boolean
  /** 卡片页可选字段（方向/字数等），后端 JSON 透传，未填为 null */
  fields?: Record<string, unknown> | null
  // T-M1-2（GET /cards 内嵌，首屏 N+1→1）：以下三项为列表摘要字段
  /** 当前版本号（既有 version 列别名，零迁移） */
  current_version?: number | null
  /** 内容版本快照数（排除 jd_alignment 简历对齐快照；摘要查询失败为 null，前端回退本地历史长度） */
  version_count?: number | null
  /** 标准化表达计数 active/total（同上，失败为 null） */
  expression_summary?: { active: number; total: number } | null
  created_at?: string
  updated_at?: string
}

/**
 * 经历卡一条版本快照（card_versions 行，EXP-P1-05 §28）。
 * 表结构固定，仅存 title/raw_text/tags + 来源信息，可据此回滚原文。
 */
export interface ExperienceCardVersion {
  id: number
  card_id: number
  version_type: string
  source_type: string
  source_id: number
  title: string | null
  raw_text: string
  tags: string[]
  note: string | null
  created_at?: string | null
}

/** 经历卡版本历史响应（versions 新→旧） */
export interface ExperienceCardVersionList {
  card_id: number
  current_version: number
  versions: ExperienceCardVersion[]
}

/** GET /cards/search 分页信封（T-M1-3 检索 v1；q / direction_id 至少其一，后端 400） */
export interface CardSearchResponse {
  items: ExperienceCard[]
  total: number
  page: number
  page_size: number
  total_pages: number
  query: string | null
  direction_id: number | null
}

// ============================================================
// 标准化表达（Expression，EXP-P2-02 §8 / DATA_MODEL §6 wire 层）
// ============================================================

/** 来源引用（对齐后端 SourceRef，DATA_MODEL §3.2，EXP-P2-06） */
export interface SourceRef {
  id: string
  source_type:
    | 'user_input'
    | 'resume'
    | 'experience'
    | 'expression'
    | 'job'
    | 'jd'
    | 'jd_analysis'
    | 'interview'
    | 'interview_prep'
    | 'transcript'
    | 'review'
    | 'external_source'
    | 'user_confirmation'
  source_id: string
  locator?: string | null
}

/** 一条标准化表达（对齐后端 ExpressionRead，EXP-P2-08） */
export interface Expression {
  id: number
  user_id: number
  experience_id: number
  direction_id?: number | null
  job_id?: number | null
  /** standardized / direction / job_specific（P2 仅 standardized 生效） */
  type: string
  content: string
  version: number
  validation_level: number
  usage_count: number
  source_refs: SourceRef[]
  /** candidate / active / deprecated */
  status: string
  created_at?: string | null
  updated_at?: string | null
}

/** 经历卡表达列表响应（§8.1） */
export interface ExpressionListResponse {
  experience_id: number
  items: Expression[]
}

// ============================================================
// JD / ATS
// ============================================================

export interface DimensionRequirement {
  dimension: string
  level: number
  evidence: string
}

export interface JDRequirements {
  position_title: string
  hard_skills: string[]
  soft_skills: string[]
  keywords: string[]
  nice_to_have: string[]
  responsibilities: string[]
  dimension_requirements: DimensionRequirement[]
  salary_range: string | null
  work_mode: string | null
  location: string | null
}

export interface ATSProfile {
  job_title: string
  department: string | null
  location: string | null
  salary: string | null
  years_of_experience: string | null
  education: string | null
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  key_metrics: string[]
  culture_keywords: string[]
  dimension_requirements: DimensionRequirement[]
  raw_summary: string
}

// ============================================================
// 匹配与建议
// ============================================================

export interface PerCardScore {
  card_id: number
  score: number
  matched: string[]
  missing: string[]
}

export interface SuggestionItem {
  card_id: number | null
  type: 'gap' | 'rewrite' | 'order' | 'supplement' | string
  message: string
  priority: number
  optimization: string | null
}

/** 能力缺口改写任务清单条目（T-M4-2 / Q3 定稿，wire snake_case）。 */
export interface CapabilityGapWire {
  id?: number
  job_analysis_id?: number
  dimension: string
  kind: 'evidence' | 'rewrite'
  status: 'missing' | 'weak'
  severity: 'high' | 'medium' | 'low'
  jd_evidence: string
  current: string
  rewrite_hint: string
  card_id: number | null
  note: string
}

// ============================================================
// 岗位分析结果
// ============================================================

/** 六维方向分类读模型（T-M4-4 additive，wire snake_case，camel 转换在 mapper）。 */
export interface WireJdClassification {
  id: number
  job_analysis_id?: number
  /** 关联方向 id（无方向为 null/0） */
  direction_id: number | null
  /** 关联方向展示名（grouped 查询联 direction 表解析，缺方向为 null） */
  direction_name?: string | null
  direction_code?: string | null
  job_function: string
  primary_role: string
  industry: string
  product: string
  scenario: string
  skills: string
  /** high|medium|low（空串 = manual 直填未评置信） */
  confidence: string
  /** manual|rule|ai */
  source: string
  /** proposed|confirmed */
  status: string
  created_at?: string | null
  updated_at?: string | null
}

export interface JobAnalysisResult {
  job_analysis_id: number
  /** 归属岗位实体 id（job 表，T-M5-5 jd-byte-1：FE 据此对齐 jobId，缺省=旧分析无归属） */
  job_id?: number | null
  user_id: number
  company: string
  position: string
  jd_text: string
  jd_requirements: JDRequirements | null
  ats_profile: ATSProfile | null
  company_context: Record<string, string | number | boolean | null> | null
  match_score: number | null
  match_level: string | null
  customization_needed: boolean | null
  gap_analysis: string | null
  gap_items: string[]
  per_card_scores: PerCardScore[]
  suggestions: SuggestionItem[]
  /** 改写任务清单（T-M4-2 additive 字段；旧分析为 []，报告页回退能力匹配表） */
  capability_gaps?: CapabilityGapWire[]
  dimension_requirements: DimensionRequirement[]
  resume_markdown: string | null
  created_at: string | null
}

// ============================================================
// 面试复盘
// ============================================================

export interface ReviewedQuestion {
  sequence: number
  start_time: string
  speaker: string
  question_text: string
  dimension: string
  level: string
  intent: string
  expected_answer: string
  my_answer: string
  score: number
  feedback: string[]
  suggestions: string[]
  related_card_id: number | null
  related_card_title: string | null
}

export interface InterviewReviewResult {
  record_id: number
  user_id: number
  title: string
  company: string
  position: string
  round_type: string
  overall_score: number
  summary: string
  strengths: string[]
  weaknesses: string[]
  action_items: string[]
  questions: ReviewedQuestion[]
  /** W12：候选正文随 analysis_json 落库（camelCase，与 GET detail 契约一致）；FE 直读进 review
   * ；仅 record.analysis(=analysis_json) 含此键，POST analyze 响应不含 */
  experienceFeedbacks?: ReviewExperienceFeedback[]
  created_at: string | null
}

/**
 * 复盘候选正文（camelCase，随 analysis_json 落库；与 jobcraft 领域模型同构）。
 * 定义放 api 层以保持本文件零依赖（原在 types/jobcraft.ts，jobcraft 侧重导出，
 * 全部既有消费者导入路径不变）。
 */
export interface ReviewExperienceFeedback {
  experienceId: string
  experienceTitle: string
  discoveredIssues: string[]
  suggestions: string[]
  currentVersion: string
  proposedVersion: string
  /** wire 形状 = {field, from, to}（与 ExperienceProposedChange 结构等价） */
  proposedChanges: Array<{ field: string; from: string; to: string }>
  applied: boolean
}

export interface InterviewReviewRecord {
  id: number
  user_id: number
  title: string
  company: string
  position: string
  round_type: string
  /** T-M8-7 起 FE 透传后非空；存量行可能为 null（匹配 interview 时兜底 company/position/round） */
  job_analysis_id?: number | null
  status: string
  created_at: string | null
}

export interface InterviewReviewDetailRecord extends InterviewReviewRecord {
  raw_text?: string
  parsed_dialogue?: InterviewReviewParsePreviewItem[]
  analysis?: InterviewReviewResult
}

export interface InterviewReviewParsePreviewItem {
  sequence: number
  speaker: string
  role: 'interviewer' | 'candidate' | string
  time: string
  content: string
}

export interface InterviewReviewParsePreviewQAPair {
  sequence: number
  start_time: string
  speaker: string
  question_text: string
  my_answer: string
  intent?: string
  dimension?: string
  level?: string
}

export interface InterviewReviewParsePreviewResult {
  dialogue: InterviewReviewParsePreviewItem[]
  qa_pairs: InterviewReviewParsePreviewQAPair[]
  qa_pair_count: number
  speaker_count: number
  role_counts: {
    interviewer: number
    candidate: number
    unknown: number
  }
}

export interface InterviewReviewCreateResult {
  record_id: number
  status: string
  qa_pairs: InterviewReviewParsePreviewQAPair[]
  qa_pair_count: number
  dialogue: InterviewReviewParsePreviewItem[]
  speaker_count: number
  role_counts: {
    interviewer: number
    candidate: number
    unknown: number
  }
}

export interface InterviewReviewQuestionTableResult {
  record_id: number
  status: string
  questions: InterviewReviewParsePreviewQAPair[]
}

/** T-M7-4：预建面试场次行（interview_records，status=planned）结果 */
export interface InterviewSessionCreateResult {
  record_id: number
  status: string
}

/** T-M8-2：interview_qa_pairs 表直读行（含深度研判字段，详情页直读数据源） */
export interface InterviewReviewQaPair {
  id: number
  record_id: number
  sequence: number
  speaker: string
  start_time: string
  content: string
  is_question: boolean
  question_text: string
  dimension: string
  level: string
  intent: string
  expected_answer: string
  my_answer: string
  feedback: string[]
  suggestions: string[]
  score: number
  related_card_id: number | null
  related_card_title: string | null
}

/** T-M8-3：聚合题库行——QA 对 + 所属场次上下文（跨 record 聚合，只读） */
export interface QuestionBankQaPair extends InterviewReviewQaPair {
  record_title: string
  record_company: string
  record_position: string
  record_round_type: string
  record_job_analysis_id: number | null
}

/** T-M8-3：GET /api/jobcraft/interview-review/qa-pairs 响应 */
export interface QuestionBankResponse {
  qa_pairs: QuestionBankQaPair[]
  qa_pair_count: number
  job_analysis_id: number | null
}

/** T-M8-2：GET /api/jobcraft/interview-review/{record_id} 响应（record + 直读题库） */
export interface InterviewReviewDetailResponse {
  record: InterviewReviewDetailRecord
  qa_pairs: InterviewReviewQaPair[]
}

/** T-M8-1：反馈候选决策状态（后端 feedback_candidates 台账，刷新不丢）
 *
 * T-M8-9：新增 `edited`（用户手工改过槽位再确认，SPEC §23 枚举），
 * 语义上等同 `accepted`（已沉淀到卡片），仅台账标签不同。
 */
export type FeedbackDecisionStatus =
  | 'pending'
  | 'accepted'
  | 'edited'
  | 'rejected'

/** T-M8-1：闸门状态由台账推导；T-M8-9 起 DB 侧阶段序也落 awaiting_confirmation/done */
export type FeedbackGateStatus = 'none' | 'awaiting_confirmation' | 'done'

/**
 * T-M8-1：GET /{record_id}/feedback-candidates 响应。
 * 候选正文来自 analysis_json（唯一来源），decision 来自决策台账。
 */
export interface FeedbackCandidateItem {
  target_type: string
  target_ref: string
  experience_id: string
  experience_title: string
  discovered_issues: string[]
  suggestions: string[]
  current_version: string
  proposed_version: string
  /** 收窄为 {field,from,to}（= ExperienceProposedChange 结构等价），消费方 applyProposedChanges 只读三字段 */
  proposed_changes: Array<{ field: string; from: string; to: string }>
  decision: FeedbackDecisionStatus
  card_version: number | null
  decided_at: string | null
}

export interface FeedbackCandidatesResponse {
  record_id: number
  candidates: FeedbackCandidateItem[]
  candidate_count: number
  pending_count: number
  gate_status: FeedbackGateStatus
}

/** T-M8-1：accept 请求体（四槽位内容由前端本地合成后提交，服务端只管幂等落卡） */
export interface FeedbackDecisionPayload {
  target_ref: string
  target_type?: string
  background?: string
  problem?: string
  actions?: string[]
  results?: string[]
  analysis_run_id?: string
  /** T-M8-9：用户手工改过槽位再确认 → 台账记 `edited` 而非 `accepted`。
   *
   * 当前详情页确认弹层只做预览、无编辑输入，故前端暂不传该字段（恒为 accepted）；
   * 服务端已支持该语义，供后续「编辑后确认」UI 直接启用。
   */
  edited?: boolean
}

export interface FeedbackDecisionResult {
  record_id: number
  target_ref: string
  decision: FeedbackDecisionStatus
  card_version: number | null
  decided_at: string | null
  idempotent: boolean
  gate_status: FeedbackGateStatus
}

/** T-M8-9 遗留 C：§24.2 汇总一次确认——批次内单条决策（服务端先整批校验后单事务写入） */
export interface FeedbackBatchDecisionItem {
  target_ref: string
  target_type?: string
  /** accepted/edited 走写卡，rejected 仅记台账 */
  decision: 'accepted' | 'edited' | 'rejected'
  background?: string
  problem?: string
  actions?: string[]
  results?: string[]
  analysis_run_id?: string
}

export interface FeedbackBatchConfirmPayload {
  decisions: FeedbackBatchDecisionItem[]
}

export interface FeedbackBatchItemResult {
  target_ref: string
  decision: FeedbackDecisionStatus
  card_version: number | null
  decided_at: string | null
  idempotent: boolean
}

export interface FeedbackBatchConfirmResult {
  record_id: number
  results: FeedbackBatchItemResult[]
  decision_count: number
  gate_status: FeedbackGateStatus
}

// ============================================================
// 面试准备稿
// ============================================================

export interface DimensionQuestion {
  dimension: string
  question: string
  answer_points: string[]
  card_ids: number[]
}

/**
 * 公司调研单条条目（T-P7-1：6 维 aspect 内层结构化，与后端 ResearchItem 对齐）。
 * 旧缓存（无 aspects）仍可能是旧自由结构，字段因此全可选。
 */
export interface ResearchItemShape {
  content?: string
  source_url?: string
  date?: string
  source_type?: '官方' | '新闻' | '社交' | 'AI推断'
  sufficiency?: 'full' | 'partial' | 'insufficient'
}

/** 公司调研 6 维 aspect（键名与后端 CompanyResearchInfo 裁定一致，不得改）。 */
export interface CompanyResearchAspects {
  overview?: ResearchItemShape[]
  business?: ResearchItemShape[]
  ecosystem?: ResearchItemShape[]
  team?: ResearchItemShape[]
  recent?: ResearchItemShape[]
  reputation?: ResearchItemShape[]
}

/**
 * 公司背调结构（后端 company_research JSON 的消费子集）。
 * 双形：旧缓存自由结构（basic/business/…）+ 新结构 aspects
 * （对齐 `app/schemas/jobcraft.py` `CompanyResearchInfo.aspects`）。
 * 消费方（mappers.buildInterviewFromPrep）新结构优先、旧字段兜底；
 * 字段均可选（AI 生成结果可能缺项）。
 */
export interface CompanyResearchShape {
  aspects?: CompanyResearchAspects
  /**
   * T-P7-3 降级矩阵：后端回退旧缓存时顶层标记——仅回退返回值带；
   * 永不进全局 company_research 缓存行，但会随 prep 快照
   * company_research_json 持久化。
   */
  stale?: boolean
  basic?: {
    name?: string
    full_name?: string
    description?: string
    industry?: string
    founded?: string
    headquarters?: string
    size?: string
    stage?: string
    website?: string
  }
  business?: {
    main_business?: string
    product_names?: string[]
    main_products?: string | string[]
    business_model?: string
    target_customers?: string
    competitors?: string
  }
  funding?: {
    latest_round?: string
    investors?: string
    valuation?: string
  }
  team?: {
    founders?: string
    key_executives?: string
  }
  industry?: {
    sector?: string
    trends?: string
    opportunities?: string
    risks?: string
  }
  news?: (string | { title?: string; date?: string; summary?: string })[]
  ai_hiring?: string
  sources?: string[]
}

export interface InterviewPrepResult {
  id?: number
  job_analysis_id: number
  round_type: string
  duration: string
  elevator_pitch: string
  dimension_questions: DimensionQuestion[]
  full_version: string
  html_content: string
  created_at: string | null
  company_research?: CompanyResearchShape | null
}

export interface InterviewPrepRecord extends InterviewPrepResult {
  id: number
  company: string
  position: string
  submission_id?: number | null
  /** 备战应答草稿（题号 -> 文本），FE-PREP-01 落库于 interview_preps.drafts */
  drafts?: Record<string, string>
}

// ============================================================
// 投递记录
// ============================================================

/**
 * 投递记录状态机（后端英文枚举，中文仅前端显示）
 * 合法流转：PREPARED → APPLIED → INVITED → ROUND_1 → ROUND_2 → OFFER / CLOSED，
 * 任一步骤均可提前 CLOSED。
 *
 * P11-a：创建投递记录 ≠ 提交投递，故区分两态：
 * - PREPARED（待投递）：已创建记录 / 已保存简历，用户尚未确认投递；
 * - APPLIED（已投递）：必须由用户主动确认投递（delivered=1）才成立。
 */
export type SubmissionStatus =
  | 'PREPARED'
  | 'APPLIED'
  | 'INVITED'
  | 'ROUND_1'
  | 'ROUND_2'
  | 'OFFER'
  | 'CLOSED'

/** 后端状态码 → 中文显示 */
export const SUBMISSION_STATUS_CN: Record<SubmissionStatus, string> = {
  PREPARED: '待投递',
  APPLIED: '已投递',
  INVITED: '面试邀约',
  ROUND_1: '一面',
  ROUND_2: '二面',
  OFFER: 'Offer',
  CLOSED: '已关闭',
}

export interface Submission {
  id: number
  user_id: number
  job_analysis_id: number | null
  /** P4-4a：岗位实体 id（Job 聚合根），创建岗位后用于缓存与后续归属 */
  job_id?: number | null
  position: string
  company: string
  jd_text: string
  resume_markdown: string
  resume_file_path: string | null
  card_version_ids: number[]
  status: SubmissionStatus
  notes: string
  delivered: boolean
  created_at: string | null
  updated_at: string | null
}

export interface DashboardItem {
  id: number
  position: string
  company: string
  status: SubmissionStatus
  job_analysis_id: number | null
  /** P4-4a：岗位实体 id */
  job_id?: number | null
  has_analysis: boolean
  card_version_count: number
  card_count: number
  has_resume: boolean
  is_manual: boolean
  delivered: boolean
  prep_count: number
  review_count: number
  created_at: string | null
  updated_at: string | null
}

// ============================================================
// 简历/文件
// ============================================================

export interface SaveResumeResult {
  submission_id?: number | null
  /** T-M6-2：save-resume 产物写入 resume_version 的版本 id（submission_id 已废为 null） */
  resume_version_id?: number | null
  file_path: string
  file_name: string
  size_bytes: number
  selected_count: number
}

/** T-M6-2：简历版本（/api/jobcraft/resume-version），FE 简历域读写源 */
export interface ResumeVersionWire {
  id: number
  user_id: number
  job_id: number | null
  job_analysis_id: number | null
  direction_id: number | null
  version_no: number
  version_name: string | null
  sections: unknown
  resume_markdown: string | null
  selected_for_application: boolean
  source_expression_refs: unknown
  company: string | null
  position: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ResumePersonalInfo {
  name: string
  phone: string
  email: string
  city: string
  github: string
  education: string
  years: string
}

// ============================================================
// Step1/Step2 结果
// ============================================================

export interface SubtextDecode {
  surface_requirement: string
  hidden_meaning: string
  key_ability: string
  how_to_prove: string
}

export interface Step1AtsProfile {
  job_title: string
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  key_metrics: string[]
  culture_keywords: string[]
  education?: string
  years_of_experience?: string
  salary?: string
  location?: string
  subtext_decoded?: SubtextDecode[]
}

export interface BackfillResult {
  checked: number
  splits: {
    from_card_id: number
    from_title: string
    created_ids: number[]
  }[]
}

// ============================================================
// 异步任务系统（/api/jobcraft/tasks/*）
// ============================================================

export type TaskStatusName =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface TaskInfo {
  task_id: string
  task_type: string
  status: TaskStatusName
  params: Record<string, unknown>
  result?: Record<string, unknown> | null
  error?: string | null
  created_at?: number
  started_at?: number | null
  completed_at?: number | null
}

export interface SubmitTaskResult {
  task_id: string
  task_type: string
  status: TaskStatusName
}
