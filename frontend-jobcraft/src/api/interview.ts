/**
 * 面试 API
 */

import { request, requestFormData } from './client'
import type {
  InterviewPrepResult,
  InterviewReviewRecord,
  InterviewReviewDetailRecord,
  InterviewReviewCreateResult,
  InterviewReviewParsePreviewResult,
  InterviewReviewQuestionTableResult,
  InterviewReviewResult,
  ReviewedQuestion,
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

export async function getInterviewPrep(
  jobId: number,
  userId?: number
): Promise<InterviewPrepResult> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request<InterviewPrepResult>(`/api/jobcraft/job/${jobId}/interview-prep${qs}`)
}

export async function getJobSelectedCards(
  jobId: number
): Promise<{ card_ids: number[] }> {
  return request<{ card_ids: number[] }>(`/api/jobcraft/job/${jobId}/selected-cards`)
}

// ============================================================
// 面试复盘
// ============================================================

export async function listInterviewReviews(
  userId?: number
): Promise<{ records: InterviewReviewRecord[] }> {
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
  userId?: number
): Promise<{ record: InterviewReviewDetailRecord; qa_pairs: ReviewedQuestion[] }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request(`/api/jobcraft/interview-review/${recordId}${qs}`)
}

export async function deleteInterviewReview(
  recordId: number,
  userId?: number
): Promise<{ status: string; record_id: number }> {
  const qs = userId !== undefined ? `?user_id=${userId}` : ''
  return request(`/api/jobcraft/interview-review/${recordId}${qs}`, {
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
  return requestFormData<InterviewReviewParsePreviewResult>(
    '/api/jobcraft/interview-review/parse-preview',
    formData
  )
}

export async function generateInterviewReviewQuestionTable(
  recordId: number,
  userId?: number
): Promise<InterviewReviewQuestionTableResult> {
  return request<InterviewReviewQuestionTableResult>(
    `/api/jobcraft/interview-review/${recordId}/question-table`,
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }
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
