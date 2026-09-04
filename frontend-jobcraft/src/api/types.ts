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
  source: string
  card_type: string
  version: number
  is_active: boolean
  created_at?: string
  updated_at?: string
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

// ============================================================
// 岗位分析结果
// ============================================================

export interface JobAnalysisResult {
  job_analysis_id: number
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
  created_at: string | null
}

export interface InterviewReviewRecord {
  id: number
  user_id: number
  title: string
  company: string
  position: string
  round_type: string
  status: string
  created_at: string
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

// ============================================================
// 面试准备稿
// ============================================================

export interface DimensionQuestion {
  dimension: string
  question: string
  answer_points: string[]
  card_ids: number[]
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
  company_research?: Record<string, unknown> | null
}

export interface InterviewPrepRecord extends InterviewPrepResult {
  id: number
  company: string
  position: string
  submission_id: number | null
}

// ============================================================
// 投递记录
// ============================================================

/**
 * 投递记录状态机（后端英文枚举，中文仅前端显示）
 * 合法流转：APPLIED → INVITED → ROUND_1 → ROUND_2 → OFFER / CLOSED，
 * 任一步骤均可提前 CLOSED。
 */
export type SubmissionStatus =
  | 'APPLIED'
  | 'INVITED'
  | 'ROUND_1'
  | 'ROUND_2'
  | 'OFFER'
  | 'CLOSED'

/** 后端状态码 → 中文显示 */
export const SUBMISSION_STATUS_CN: Record<SubmissionStatus, string> = {
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
  position: string
  company: string
  jd_text: string
  resume_markdown: string
  resume_file_path: string | null
  card_version_ids: number[]
  status: SubmissionStatus
  notes: string
  created_at: string | null
  updated_at: string | null
}

export interface DashboardItem {
  id: number
  position: string
  company: string
  status: SubmissionStatus
  job_analysis_id: number | null
  has_analysis: boolean
  card_version_count: number
  card_count: number
  has_resume: boolean
  is_manual: boolean
  prep_count: number
  review_count: number
  created_at: string | null
  updated_at: string | null
}

// ============================================================
// 简历/文件
// ============================================================

export interface SaveResumeResult {
  file_path: string
  file_name: string
  size_bytes: number
  selected_count: number
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

export interface CardDimensionScore {
  dimension: string
  score: number
  note: string
}

// 对齐后端 app/agents/gap_polish_agent.py:CardGapItem + fuse_gap_scores 覆盖字段
export interface CardGapItem {
  card_id: number
  score: number
  local_score: number
  llm_score: number
  matched: string[]
  missing: string[]
  action: string
  rewrite_suggestion?: string | null
  supplement_suggestion?: string | null
  supplement_steps: string[]
  dimension_analysis: CardDimensionScore[]
  transferable_skills: string[]
  domain_overlap: string
  quantified_note: string
}

// 对齐后端 app/agents/gap_polish_agent.py:GlobalSuggestion
export interface GlobalSuggestion {
  missing_ability: string
  priority: 'high' | 'medium' | 'low'
  action: string
  steps: string[]
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
