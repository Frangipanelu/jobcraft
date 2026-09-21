/**
 * 岗位/投递 API
 */

import { request, requestFormData } from './client'
import type {
  JobAnalysisResult,
  JDRequirements,
  DimensionRequirement,
  Submission,
  DashboardItem,
  SaveResumeResult,
  ResumePersonalInfo,
  ATSProfile,
  ExperienceCard,
} from './types'

// ============================================================
// 岗位分析
// ============================================================

export interface PreviewItem {
  title: string
  company: string
  role: string
  period: string
  card_type: string
  raw_text: string
  summary: string
  selected: boolean
}

export async function previewResume(file: File): Promise<{ mode: string; items: PreviewItem[]; raw_text: string }> {
  const formData = new FormData()
  formData.append('file', file)
  return requestFormData<{ mode: string; items: PreviewItem[]; raw_text: string }>('/api/jobcraft/experience/upload/preview', formData)
}

export async function confirmUpload(items: PreviewItem[], raw_text?: string): Promise<{ cards: ExperienceCard[] }> {
  return request<{ cards: ExperienceCard[] }>('/api/jobcraft/experience/upload/confirm', {
    method: 'POST',
    body: JSON.stringify({ items, raw_text }),
  })
}

export async function polishExperience(cardId: number, rawText: string, company?: string, role?: string): Promise<{ polished_text: string; original_text: string }> {
  return request<{ polished_text: string; original_text: string }>(`/api/jobcraft/experience/cards/${cardId}/polish`, {
    method: 'POST',
    body: JSON.stringify({ raw_text: rawText, company, role }),
  })
}

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

/** 岗位分析详情（GET /job/analyze/{id} 与 /job/analyses 列表条目的统一契约）。 */
export interface JobAnalysisDetail {
  id: number;
  job_analysis_id: number;
  company: string;
  position: string;
  jd_text: string;
  jd_requirements: JDRequirements | null;
  match_score: number | null;
  gap_analysis: unknown;
  dimension_requirements: DimensionRequirement[];
  created_at: string | null;
}

export async function listJobAnalyses(
  userId?: number
): Promise<{ analyses: JobAnalysisDetail[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request(`/api/jobcraft/job/analyses${qs}`)
}

export async function getJobAnalysis(
  jobId: number
): Promise<JobAnalysisResult> {
  return request<JobAnalysisResult>(`/api/jobcraft/job/analyze/${jobId}`)
}

// ============================================================
// 结构化 JD 分析（前端已分好类）
// ============================================================

export interface StructuredRequirementItem {
  text: string
  tag: 'hard' | 'required' | 'preferred'
}

export async function analyzeStructuredJd(payload: {
  company: string
  position: string
  duties: string[]
  requirements: StructuredRequirementItem[]
}): Promise<{ ats_profile: ATSProfile; raw: Record<string, unknown>; company: string; position: string }> {
  return request('/api/jobcraft/job/analyze-ats-structured', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function splitJd(jdText: string): Promise<{
  duties: string[]
  requirements: { text: string; tag: string }[]
}> {
  return request('/api/jobcraft/job/split-jd', {
    method: 'POST',
    body: JSON.stringify({ jd_text: jdText }),
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
    delivered?: boolean
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

// 底座简历历史版本（持久化）

export interface BaseResumeRecord {
  id: number
  user_id: number
  name: string
  file_size: string
  format: string
  parsed_count: number
  tags: string[]
  is_default: boolean
  created_at: string | null
  updated_at: string | null
}

export async function createBaseResume(payload: {
  name: string
  file_size: string
  format: string
  parsed_count: number
  tags: string[]
}): Promise<BaseResumeRecord> {
  return request<BaseResumeRecord>('/api/jobcraft/experience/base-resumes', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listBaseResumes(): Promise<BaseResumeRecord[]> {
  return request<BaseResumeRecord[]>('/api/jobcraft/experience/base-resumes', {
    method: 'GET',
  })
}

export async function setDefaultBaseResume(resumeId: number): Promise<BaseResumeRecord> {
  return request<BaseResumeRecord>(`/api/jobcraft/experience/base-resumes/${resumeId}/default`, {
    method: 'PATCH',
  })
}

export async function deleteBaseResume(resumeId: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/jobcraft/experience/base-resumes/${resumeId}`, {
    method: 'DELETE',
  })
}

export function getResumeDownloadUrl(path: string): string {
  return `/api/jobcraft/resume/download?path=${encodeURIComponent(path)}`
}
