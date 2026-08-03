const BASE_URL = ''

// 从 types.ts 重新导出后端权威类型，供新代码或逐步迁移使用
export * from './types'
import type {
  ExperienceCard,
  InterviewReviewCreateResult,
  InterviewReviewDetailRecord,
  InterviewReviewParsePreviewResult,
  InterviewReviewQuestionTableResult,
  InterviewReviewRecord,
  InterviewReviewResult,
  ReviewedQuestion,
} from './types'

export interface AtsProfile {
  role_summary: string | null
  experience_years: string | null
  education: string | null
  industry: string | null
  hard_skills: string[]
  soft_skills: string[]
  hidden_requirements: HiddenRequirement[]
  keywords: Keyword[]
  priority_tags: string[]
}

export interface HiddenRequirement {
  category: string
  source: string
  phrase: string
  decoded: string
}

export interface Keyword {
  keyword: string
  weight: number
  category: string
}

export interface CompanyContext {
  name?: string
  industry?: string
  scale?: string
  business?: string
  products?: string[]
  industry_position?: string
  culture?: string
  business_domains?: string[]
}

export interface GapItem {
  term: string
  why: string
  how: string
  priority: 'high' | 'medium' | 'low'
  category: string
  example_rewrite?: string
  target_card_id?: number
}

export interface PerCardScore {
  card_id: number
  score: number
  algo_score?: number
  llm_score?: number
  jargon_hits?: string[]
}

export interface DimensionRequirement {
  dimension: string
  level: string
  requirement: string
}

export interface DimensionQuestion {
  dimension: string
  question: string
  answer_points: string[]
  card_ids: number[]
}

export interface AnalyzeJobResult {
  job_analysis_id: number
  match_score: number
  match_level: string
  customization_needed: boolean
  gap_analysis: string[]
  gap_items: GapItem[]
  per_card_scores: PerCardScore[]
  suggestions: any[]
  ats_profile: AtsProfile
  company_context: CompanyContext
  dimension_requirements: DimensionRequirement[]
  resume_markdown: string
}

export interface SaveResumeResult {
  job_analysis_id: number
  resume_path: string
  resume_markdown: string
}

export interface InterviewPrepResult {
  job_analysis_id: number
  round_type: string
  elevator_pitch: string
  dimension_questions: DimensionQuestion[]
  full_version: string
  html_content: string
  created_at?: string
}

interface UnifiedErrorBody {
  code?: number
  msg?: string
  data?: any
}

async function parseUnifiedError(res: Response, fallback: string): Promise<Error> {
  const text = await res.text().catch(() => 'Unknown error')
  let body: UnifiedErrorBody | string = text
  try {
    body = JSON.parse(text) as UnifiedErrorBody
  } catch {
    // 保持原始 text
  }
  return new Error(parseErrorMessage(res, body, fallback))
}

function parseErrorMessage(_res: Response, body: UnifiedErrorBody | string, fallback: string): string {
  if (typeof body === 'string') {
    return body || fallback
  }
  if (body && typeof body === 'object' && body.msg) {
    return body.msg
  }
  return fallback
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw await parseUnifiedError(res, `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function listCards(userId?: number, includeInactive?: boolean): Promise<ExperienceCard[]> {
  const params = new URLSearchParams()
  if (userId !== undefined) params.append('user_id', String(userId))
  if (includeInactive !== undefined) params.append('include_inactive', String(includeInactive))
  const qs = params.toString() ? `?${params.toString()}` : ''
  const data = await request<{ cards: ExperienceCard[] }>(`/api/jobcraft/experience/cards${qs}`)
  return data.cards || []
}

export async function createCard(payload: Partial<ExperienceCard>): Promise<ExperienceCard> {
  return request<ExperienceCard>('/api/jobcraft/experience/cards', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateCard(id: number, payload: Partial<ExperienceCard>): Promise<ExperienceCard> {
  return request<ExperienceCard>(`/api/jobcraft/experience/cards/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteCard(id: number): Promise<void> {
  await request<void>(`/api/jobcraft/experience/cards/${id}`, { method: 'DELETE' })
}

export async function uploadResume(
  file: File,
): Promise<ExperienceCard[]> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/jobcraft/experience/upload`, { method: 'POST', body: formData })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    let body: UnifiedErrorBody | string = text
    try {
      body = JSON.parse(text) as UnifiedErrorBody
    } catch {
      // 保持原始 text
    }
    const message = parseErrorMessage(res, body, `Upload failed: ${res.status}`)
    throw new Error(message)
  }
  const data = await res.json()
  return (data.cards || []) as ExperienceCard[]
}

export interface SubtextDecode {
  surface_requirement: string
  hidden_meaning: string
  key_ability: string
  how_to_prove: string
}

export async function step1AtsRecommend(payload: {
  position: string
  company: string
  jd_text: string
}): Promise<{
  job_analysis_id: number
  ats: {
    job_title: string
    required_skills: string[]
    preferred_skills: string[]
    responsibilities: string[]
    key_metrics: string[]
    culture_keywords: string[]
    education?: string
    years_of_experience?: string
    subtext_decoded?: SubtextDecode[]
  }
  recommended_cards: { card_id: number; score: number; reason: string }[]
  all_cards: ExperienceCard[]
}> {
  return request('/api/jobcraft/job/step1-ats-recommend', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function step2GapPolish(payload: {
  job_analysis_id: number
  card_ids: number[]
}): Promise<{
  per_card: {
    card_id: number
    score: number
    local_score: number
    llm_score: number
    matched: string[]
    missing: string[]
    action: 'polish' | 'supplement' | 'good'
    rewrite_suggestion?: string
    supplement_suggestion?: string
    supplement_steps?: string[]
    dimension_analysis?: { dimension: string; score: number; note: string }[]
    transferable_skills?: string[]
    domain_overlap?: string
    quantified_note?: string
  }[]
  global_suggestions: {
    missing_ability: string
    priority: string
    action: string
    steps: string[]
  }[]
  overall_score: number
  match_level: string
}> {
  return request('/api/jobcraft/job/step2-gap-polish', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface BackfillResult {
  checked: number
  splits: {
    from_card_id: number
    from_title: string
    created_ids: number[]
  }[]
}

export async function backfillCards(payload?: {
  user_id?: number
  min_chars?: number
}): Promise<BackfillResult> {
  return request<BackfillResult>('/api/jobcraft/experience/cards/backfill', {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  })
}

export async function saveCardVersion(payload: {
  card_id: number
  source_type: string
  source_id: number
  raw_text: string
  title?: string
  tags?: string[]
}): Promise<{ version_id: number; status: string }> {
  return request('/api/jobcraft/job/save-card-version', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function analyzeJob(payload: any): Promise<AnalyzeJobResult> {
  return request<AnalyzeJobResult>('/api/jobcraft/job/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getResumeDownloadUrl(path: string): string {
  return `${BASE_URL}/api/jobcraft/resume/download?path=${encodeURIComponent(path)}`
}

export async function generateInterviewPrep(
  jobId: number,
  payload: { user_id?: number; round_type: string; card_ids: number[]; submission_id?: number },
): Promise<InterviewPrepResult> {
  return request<InterviewPrepResult>(`/api/jobcraft/job/${jobId}/interview-prep`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getJobSelectedCards(jobId: number): Promise<{ card_ids: number[] }> {
  return request<{ card_ids: number[] }>(`/api/jobcraft/job/${jobId}/selected-cards`)
}

export async function getInterviewPrep(jobId: number, userId?: number): Promise<InterviewPrepResult> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<InterviewPrepResult>(`/api/jobcraft/job/${jobId}/interview-prep${qs}`)
}

export async function listInterviewReviews(userId?: number): Promise<{ records: InterviewReviewRecord[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ records: InterviewReviewRecord[] }>(`/api/jobcraft/interview-review${qs}`)
}

export async function createInterviewReview(payload: {
  user_id?: number
  title?: string
  company?: string
  position?: string
  round_type?: string
  job_analysis_id?: number | null
  submission_id?: number | null
  raw_text: string
}): Promise<InterviewReviewCreateResult> {
  return request<InterviewReviewCreateResult>('/api/jobcraft/interview-review', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getInterviewReviewDetail(
  recordId: number,
  userId?: number,
): Promise<{ record: InterviewReviewDetailRecord; qa_pairs: ReviewedQuestion[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ record: InterviewReviewDetailRecord; qa_pairs: ReviewedQuestion[] }>(
    `/api/jobcraft/interview-review/${recordId}${qs}`,
  )
}

export async function deleteInterviewReview(recordId: number, userId?: number): Promise<{ status: string; record_id: number }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ status: string; record_id: number }>(`/api/jobcraft/interview-review/${recordId}${qs}`, {
    method: 'DELETE',
  })
}

export async function uploadInterviewReview(
  file: File,
  payload: {
    user_id?: number
    title?: string
    company?: string
    position: string
    round_type?: string
    job_analysis_id?: number | null
  submission_id?: number | null
  },
): Promise<InterviewReviewCreateResult> {
  const formData = new FormData()
  formData.append('file', file)
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      formData.append(key, String(value))
    }
  })
  const res = await fetch(`${BASE_URL}/api/jobcraft/interview-review/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    let body: UnifiedErrorBody | string = text
    try {
      body = JSON.parse(text) as UnifiedErrorBody
    } catch {
      // 保持原始 text
    }
    const message = parseErrorMessage(res, body, `Upload failed: ${res.status}`)
    throw new Error(message)
  }
  return res.json() as Promise<InterviewReviewCreateResult>
}

export async function parseInterviewReviewPreview(params: {
  raw_text?: string
  file?: File
  company?: string
  position?: string
  round_type?: string
  job_analysis_id?: number | null
  submission_id?: number | null
  with_intent?: boolean
}): Promise<InterviewReviewParsePreviewResult> {
  const formData = new FormData()
  if (params.raw_text !== undefined) {
    formData.append('raw_text', params.raw_text)
  }
  if (params.file) {
    formData.append('file', params.file)
  }
  if (params.company !== undefined) {
    formData.append('company', params.company)
  }
  if (params.position !== undefined) {
    formData.append('position', params.position)
  }
  if (params.round_type !== undefined) {
    formData.append('round_type', params.round_type)
  }
  if (params.job_analysis_id !== undefined && params.job_analysis_id !== null) {
    formData.append('job_analysis_id', String(params.job_analysis_id))
  }
  if (params.submission_id !== undefined && params.submission_id !== null) {
    formData.append('submission_id', String(params.submission_id))
  }
  if (params.with_intent) {
    formData.append('with_intent', 'true')
  }
  const res = await fetch(`${BASE_URL}/api/jobcraft/interview-review/parse-preview`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    let body: UnifiedErrorBody | string = text
    try {
      body = JSON.parse(text) as UnifiedErrorBody
    } catch {
      // 保持原始 text
    }
    const message = parseErrorMessage(res, body, `Preview failed: ${res.status}`)
    throw new Error(message)
  }
  return res.json() as Promise<InterviewReviewParsePreviewResult>
}

export async function generateInterviewReviewQuestionTable(
  recordId: number,
  userId?: number,
): Promise<InterviewReviewQuestionTableResult> {
  return request<InterviewReviewQuestionTableResult>(
    `/api/jobcraft/interview-review/${recordId}/question-table`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    },
  )
}

export async function analyzeInterviewReview(
  recordId: number,
  selectedSequences: number[],
  userId?: number,
): Promise<InterviewReviewResult> {
  return request<InterviewReviewResult>(`/api/jobcraft/interview-review/${recordId}/analyze`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, selected_sequences: selectedSequences }),
  })
}

export async function listJobAnalyses(userId?: number): Promise<{ analyses: any[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ analyses: any[] }>(`/api/jobcraft/job/analyses${qs}`)
}

// ============================================================
// 投递记录 (resume_submission)
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

export async function createSubmission(payload: {
  position: string
  company?: string
  jd_text?: string
  job_analysis_id?: number | null
  status?: string
}): Promise<Submission> {
  return request<Submission>('/api/jobcraft/submission', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getSubmission(id: number): Promise<Submission> {
  return request<Submission>(`/api/jobcraft/submission/${id}`)
}

export async function updateSubmission(id: number, payload: {
  position?: string
  company?: string
  status?: string
  notes?: string
  resume_markdown?: string
  job_analysis_id?: number
  card_version_ids?: number[]
}): Promise<Submission> {
  return request<Submission>(`/api/jobcraft/submission/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteSubmission(id: number): Promise<void> {
  await request(`/api/jobcraft/submission/${id}`, { method: 'DELETE' })
}

export async function getDashboard(userId?: number): Promise<{ submissions: DashboardItem[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ submissions: DashboardItem[] }>(`/api/jobcraft/dashboard${qs}`)
}

export async function createManualSubmission(
  file: File,
  payload: { position: string; company?: string; jd_text?: string },
): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('position', payload.position)
  formData.append('company', payload.company || '')
  formData.append('jd_text', payload.jd_text || '')
  const res = await fetch('/api/jobcraft/submission/manual', {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Upload failed')
    throw new Error(text)
  }
  return res.json()
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

export async function saveResume(payload: {
  job_analysis_id: number
  selected_card_ids: number[]
  card_versions?: Record<number, string>
  personal_info?: Partial<ResumePersonalInfo>
}): Promise<SaveResumeResult & { resume_markdown?: string; resume_html?: string }> {
  return request<SaveResumeResult & { resume_markdown?: string; resume_html?: string }>('/api/jobcraft/job/save-resume', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

