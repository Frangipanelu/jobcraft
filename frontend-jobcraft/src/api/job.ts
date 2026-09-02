/**
 * 岗位/投递 API
 */

import { request, requestFormData } from './client'
import type {
  JobAnalysisResult,
  Submission,
  DashboardItem,
  SaveResumeResult,
  ResumePersonalInfo,
  ATSProfile,
  ExperienceCard,
  CardGapItem,
  GlobalSuggestion,
} from './types'

// ============================================================
// 岗位分析
// ============================================================

export async function analyzeJob(payload: {
  position: string
  company: string
  jd_text: string
  card_ids?: number[]
}): Promise<JobAnalysisResult> {
  return request<JobAnalysisResult>('/api/jobcraft/job/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listJobAnalyses(
  userId?: number
): Promise<{ analyses: { id: number; company: string; position: string; match_score: number | null; created_at: string | null }[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request(`/api/jobcraft/job/analyses${qs}`)
}

export async function step1AtsRecommend(payload: {
  position: string
  company: string
  jd_text: string
}): Promise<{
  job_analysis_id: number
  ats: ATSProfile
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
  per_card: CardGapItem[]
  global_suggestions: GlobalSuggestion[]
  overall_score: number
  match_level: string
  score_weights: { local: number; llm: number }
}> {
  return request('/api/jobcraft/job/step2-gap-polish', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ============================================================
// 投递记录
// ============================================================

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

export async function updateSubmission(
  id: number,
  payload: {
    position?: string
    company?: string
    status?: string
    notes?: string
    resume_markdown?: string
    job_analysis_id?: number
    card_version_ids?: number[]
  }
): Promise<Submission> {
  return request<Submission>(`/api/jobcraft/submission/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteSubmission(id: number): Promise<void> {
  await request(`/api/jobcraft/submission/${id}`, { method: 'DELETE' })
}

export async function getDashboard(
  userId?: number
): Promise<{ submissions: DashboardItem[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request(`/api/jobcraft/dashboard${qs}`)
}

export async function createManualSubmission(
  file: File,
  payload: { position: string; company?: string; jd_text?: string }
): Promise<Submission> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('position', payload.position)
  formData.append('company', payload.company || '')
  formData.append('jd_text', payload.jd_text || '')
  return requestFormData<Submission>('/api/jobcraft/submission/manual', formData)
}

// ============================================================
// 简历
// ============================================================

export async function saveResume(payload: {
  job_analysis_id: number
  selected_card_ids: number[]
  card_versions?: Record<number, string>
  personal_info?: Partial<ResumePersonalInfo>
}): Promise<SaveResumeResult & { resume_markdown?: string; resume_html?: string }> {
  return request('/api/jobcraft/job/save-resume', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getResumeDownloadUrl(path: string): string {
  return `/api/jobcraft/resume/download?path=${encodeURIComponent(path)}`
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
