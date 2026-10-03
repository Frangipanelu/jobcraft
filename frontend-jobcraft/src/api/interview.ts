/**
 * 面试 API
 */

import { request, requestFormData } from './client'
import type {
  InterviewPrepResult,
  InterviewPrepRecord,
  InterviewReviewCreateResult,
  InterviewReviewDetailResponse,
  InterviewReviewRecord,
  InterviewReviewResult,
  InterviewSessionCreateResult,
} from './types'

// ============================================================
// 面试准备
// ============================================================

export async function generateInterviewPrep(
  jobId: number,
  payload: {
    user_id?: number
    round_type: string
    card_ids: number[]
    submission_id?: number
  }
): Promise<InterviewPrepResult> {
  return request<InterviewPrepResult>(`/api/jobcraft/job/${jobId}/interview-prep`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function listInterviewPreps(
  userId?: number
): Promise<{ records: InterviewPrepRecord[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<{ records: InterviewPrepRecord[] }>(`/api/jobcraft/interview-prep${qs}`)
}

export async function saveInterviewPrepDrafts(
  prepId: number,
  drafts: Record<string, string>
): Promise<{ id: number; drafts: Record<string, string> }> {
  return request<{ id: number; drafts: Record<string, string> }>(
    `/api/jobcraft/interview-prep/${prepId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ drafts }),
    }
  )
}

export async function refreshInterviewPrepResearch(
  prepId: number
): Promise<{ id: number; company_research: unknown }> {
  return request<{ id: number; company_research: unknown }>(
    `/api/jobcraft/interview-prep/${prepId}/company-research`,
    { method: 'POST' }
  )
}

/**
 * T-M7-4：预建面试场次行（record+1，status=planned）——向导字段全透传落列。
 * 复盘时经 T-M8-7 的 record_id → update 分支填充内容。
 */
export async function createInterviewSession(payload: {
  job_analysis_id?: number | null
  submission_id?: number | null
  company: string
  position: string
  round_type?: string
  round_seq?: number
  occurred_at?: string
  interviewer?: string
  format?: string
  resume_version_id?: number | null
}): Promise<InterviewSessionCreateResult> {
  return request<InterviewSessionCreateResult>(
    '/api/jobcraft/interview-review/session',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  )
}

// ============================================================
// 面试复盘
// ============================================================

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
  }
): Promise<InterviewReviewCreateResult> {
  const formData = new FormData()
  formData.append('file', file)
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      formData.append(key, String(value))
    }
  })
  return requestFormData<InterviewReviewCreateResult>(
    '/api/jobcraft/interview-review/upload',
    formData
  )
}

export async function analyzeInterviewReview(
  recordId: number,
  selectedSequences: number[],
  userId?: number
): Promise<InterviewReviewResult> {
  return request<InterviewReviewResult>(
    `/api/jobcraft/interview-review/${recordId}/analyze`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, selected_sequences: selectedSequences }),
    }
  )
}

/** T-M8-2：复盘记录列表（含 job_analysis_id，用于详情页定位 record） */
export async function listInterviewReviewRecords(): Promise<{
  records: InterviewReviewRecord[]
}> {
  return request<{ records: InterviewReviewRecord[] }>('/api/jobcraft/interview-review')
}

/** T-M8-2：详情页直读——record（含 analysis）+ interview_qa_pairs 题库行 */
export async function getInterviewReviewDetail(
  recordId: number
): Promise<InterviewReviewDetailResponse> {
  return request<InterviewReviewDetailResponse>(
    `/api/jobcraft/interview-review/${recordId}`
  )
}

export interface MockChatReply {
  reply: string;
  role: 'interviewer';
}

export async function mockChat(payload: {
  messages: { role: string; content: string }[];
  company?: string;
  position?: string;
  round_type?: string;
  experience_context?: string;
}): Promise<MockChatReply> {
  return request<MockChatReply>('/api/jobcraft/interview-review/mock-chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
