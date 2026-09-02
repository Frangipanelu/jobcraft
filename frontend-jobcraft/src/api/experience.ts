/**
 * 经历卡 API
 */

import { request, requestFormData } from './client'
import type { ExperienceCard } from './types'

/**
 * 获取经历卡列表
 */
export async function listCards(
  userId?: number,
  includeInactive?: boolean
): Promise<ExperienceCard[]> {
  const params = new URLSearchParams()
  if (userId !== undefined) params.append('user_id', String(userId))
  if (includeInactive !== undefined) params.append('include_inactive', String(includeInactive))
  const qs = params.toString() ? `?${params.toString()}` : ''
  const data = await request<{ items: ExperienceCard[]; cards?: ExperienceCard[] }>(
    `/api/jobcraft/experience/cards${qs}`
  )
  return data.items || data.cards || []
}

/**
 * 创建经历卡
 */
export async function createCard(payload: Partial<ExperienceCard>): Promise<ExperienceCard> {
  return request<ExperienceCard>('/api/jobcraft/experience/cards', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * 更新经历卡
 */
export async function updateCard(
  id: number,
  payload: Partial<ExperienceCard>
): Promise<ExperienceCard> {
  return request<ExperienceCard>(`/api/jobcraft/experience/cards/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

/**
 * 删除经历卡
 */
export async function deleteCard(id: number): Promise<void> {
  await request<void>(`/api/jobcraft/experience/cards/${id}`, { method: 'DELETE' })
}

/**
 * 上传简历解析经历卡
 */
export async function uploadResume(file: File): Promise<ExperienceCard[]> {
  const formData = new FormData()
  formData.append('file', file)
  const data = await requestFormData<{ cards?: ExperienceCard[] }>(
    '/api/jobcraft/experience/upload',
    formData
  )
  return data.cards || []
}

/**
 * 结构化经历卡
 */
export async function structureCard(cardId: number): Promise<void> {
  await request(`/api/jobcraft/experience/cards/${cardId}/structure`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

/**
 * 推荐标签
 */
export async function recommendTags(cardId: number): Promise<string[]> {
  const data = await request<{ tags?: string[] }>(
    `/api/jobcraft/experience/cards/${cardId}/recommend-tags`,
    {
      method: 'POST',
    }
  )
  return data.tags || []
}

/**
 * 回填经历卡
 */
export async function backfillCards(payload?: {
  user_id?: number
  min_chars?: number
}): Promise<{
  checked: number
  splits: { from_card_id: number; from_title: string; created_ids: number[] }[]
}> {
  return request('/api/jobcraft/experience/cards/backfill', {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  })
}
