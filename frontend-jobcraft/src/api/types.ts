/**
 * 后端 API 响应类型定义
 * 从旧前端 types.ts 和 api.ts 提取
 */

// ============================================================
// 通用
// ============================================================

export interface APIResponse<T = any> {
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
  company_context: Record<string, any> | null
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
  parsed_dialogue?: any[]
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
  job_analysis_id: number
  round_type: string
  duration: string
  elevator_pitch: string
  dimension_questions: DimensionQuestion[]
  full_version: string
  html_content: string
  created_at: string | null
}

// ============================================================
// 投递记录
// ============================================================

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
  status: string
  notes: string
  created_at: string | null
  updated_at: string | null
}

export interface DashboardItem {
  id: number
  position: string
  company: string
  status: string
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

export interface BackfillResult {
  checked: number
  splits: {
    from_card_id: number
    from_title: string
    created_ids: number[]
  }[]
}
