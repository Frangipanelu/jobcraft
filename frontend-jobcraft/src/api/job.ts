/**
 * 岗位/投递 API
 */

import { request, requestFormData } from './client'
import type {
  JobAnalysisResult,
  JDRequirements,
  DimensionRequirement,
  CapabilityGapWire,
  WireJdClassification,
  Submission,
  DashboardItem,
  SaveResumeResult,
  ResumeVersionWire,
  ResumePersonalInfo,
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
  /** 归属岗位实体 id（job 表，T-M5-5：列表路径按此关联岗位，消灭错误回落） */
  job_id?: number | null;
  company: string;
  position: string;
  jd_text: string;
  jd_requirements: JDRequirements | null;
  match_score: number | null;
  gap_analysis: unknown;
  dimension_requirements: DimensionRequirement[];
  /** 改写任务清单（T-M4-2 additive；旧分析缺省 → 报告页回退能力匹配表） */
  capability_gaps?: CapabilityGapWire[];
  /** 六维方向分类（T-M4-4 additive；无分类/缺表 → null，历史表格显示诚实空态） */
  jd_classification?: WireJdClassification | null;
  created_at: string | null;
}

/**
 * 拉取历史分析列表。
 *
 * @param userId 归属用户（缺省不带 user_id，交后端取当前登录用户）
 * @param limit 返回条数上限（后端 GET /analyses 默认 20；历史表格客户端分页需传更大值）
 */
export async function listJobAnalyses(
  userId?: number,
  limit?: number
): Promise<{ analyses: JobAnalysisDetail[] }> {
  const params = new URLSearchParams();
  if (userId !== undefined) params.set('user_id', String(userId));
  if (limit !== undefined) params.set('limit', String(limit));
  const qs = params.toString();
  return request(`/api/jobcraft/job/analyses${qs ? `?${qs}` : ''}`)
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
  card_ids: number[]
}): Promise<JobAnalysisResult> {
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
// 六维方向分类（T-M3-2 后端 / T-M4-3 表单接线，Q4 零 LLM）
// ============================================================

/** 六维分类载荷（与后端 JdClassificationPayload 同构；六维至少一项非空 → 否则 422）。 */
export interface JdClassificationPayload {
  direction_id?: number | null
  job_function?: string
  primary_role?: string
  industry?: string
  product?: string
  scenario?: string
  skills?: string
  confidence?: '' | 'high' | 'medium' | 'low'
  source?: 'manual' | 'rule' | 'ai'
  status?: 'proposed' | 'confirmed'
}

/** 提交/更新该分析的六维分类（全量 upsert，一行一分析）。 */
export async function upsertJdClassification(
  jobAnalysisId: number,
  payload: JdClassificationPayload,
): Promise<unknown> {
  return request(`/api/jobcraft/job/${jobAnalysisId}/jd-classification`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ============================================================
// 岗位实体（T-M5-1 / M5-Q2 Job 先行：创建岗位 ≠ 投递）
// ============================================================

export interface JobEntity {
  id: number
  user_id: number
  company: string
  position: string
  raw_jd_id: number | null
  job_analysis_id: number | null
  submission_id: number | null
  status: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

/** 创建岗位实体（find-or-create 幂等：同用户同公司同岗位名返回既有行）。 */
export async function createJobEntity(payload: {
  company?: string
  position: string
  job_analysis_id?: number | null
  raw_jd_id?: number | null
}): Promise<JobEntity> {
  return request<JobEntity>('/api/jobcraft/job', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listJobEntities(): Promise<JobEntity[]> {
  return request<JobEntity[]>('/api/jobcraft/job')
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
  delivered?: boolean
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

// ============================================================
// 简历版本（T-M6-2：FE 简历域读写源，替代 submission 的简历正文）
// ============================================================

export async function listResumeVersions(jobId?: number): Promise<ResumeVersionWire[]> {
  const qs = jobId != null ? `?job_id=${jobId}` : ''
  return request<ResumeVersionWire[]>(`/api/jobcraft/resume-version${qs}`)
}

export async function updateResumeVersion(
  id: number,
  payload: {
    version_name?: string
    sections?: unknown
    resume_markdown?: string
    source_expression_refs?: unknown
  },
): Promise<ResumeVersionWire> {
  return request<ResumeVersionWire>(`/api/jobcraft/resume-version/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/** T-M6-7：设为当前投递版本（同岗单选 selected_for_application，返回更新后的版本 wire）。 */
export async function setCurrentResumeVersion(id: number): Promise<ResumeVersionWire> {
  return request<ResumeVersionWire>(`/api/jobcraft/resume-version/${id}/current`, { method: 'POST' })
}

/** T-M6-3：按能力缺口 AI 改写选中要点（1 次 LLM；只算不写，落库走 PATCH）。 */
export interface RewriteResumeBulletPayload {
  original_text: string
  dimension?: string
  gap_current?: string
  jd_evidence?: string
  rewrite_hint?: string
}

export async function rewriteResumeBullet(
  id: number,
  payload: RewriteResumeBulletPayload,
): Promise<{ rewritten_text: string }> {
  return request<{ rewritten_text: string }>(`/api/jobcraft/resume-version/${id}/rewrite`, {
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
