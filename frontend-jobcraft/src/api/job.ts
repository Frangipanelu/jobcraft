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
  ResumeSuggestionWire,
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
    resume_suggestions?: ResumeSuggestionWire[]
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

/**
 * FE-RESUME-02：同步生成简历 AI 优化建议（只算不写，落库走 PATCH resume_suggestions）。
 * 任务系统不可用时由 runTaskOrSync 降级直接调用本端点。
 * @param id 投递记录 id
 * @param bullets 结构化要点 [{item_index, bullet_index, text}]
 */
export async function suggestResume(
  id: number,
  bullets: { item_index: number; bullet_index: number; text: string }[]
): Promise<{ suggestions: ResumeSuggestionWire[] }> {
  return request(`/api/jobcraft/submission/${id}/resume-suggest`, {
    method: 'POST',
    body: JSON.stringify({ bullets }),
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
