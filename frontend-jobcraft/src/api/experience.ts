/**
 * 经历卡 API
 */

import { request } from './client'
import type {
  ExperienceCard,
  ExperienceCardVersionList,
  Expression,
  ExpressionListResponse,
  SourceRef,
} from './types'

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
 * 获取经历卡版本历史（新→旧快照，含 V1 哨兵基线，EXP-P1-05 §28）
 */
export async function listCardVersions(
  cardId: number
): Promise<ExperienceCardVersionList> {
  return request<ExperienceCardVersionList>(
    `/api/jobcraft/experience/cards/${cardId}/versions`
  )
}

/**
 * 重新执行 AI 结构化抽取（T-M1-1 失败重试入口：STAR 为空时卡片页调用）。
 * 后端写 ai_structured 并在 tags 为空时补写 v3 返回的标签。
 */
export async function structureCard(cardId: number): Promise<ExperienceCard> {
  return request<ExperienceCard>(
    `/api/jobcraft/experience/cards/${cardId}/structure`,
    { method: 'POST', body: JSON.stringify({}) }
  )
}

/**
 * 列出经历卡的标准化表达（§8.1，EXP-P2-02）。
 * 同版本链按 version 降序（最新在前）；支持 type/direction/job 过滤。
 */
export async function listExpressions(
  cardId: number,
  params?: { type?: string; directionId?: number; jobId?: number }
): Promise<ExpressionListResponse> {
  const qs = new URLSearchParams()
  if (params?.type) qs.append('type', params.type)
  if (params?.directionId !== undefined) qs.append('direction_id', String(params.directionId))
  if (params?.jobId !== undefined) qs.append('job_id', String(params.jobId))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request<ExpressionListResponse>(
    `/api/jobcraft/experience/cards/${cardId}/expressions${suffix}`
  )
}

/**
 * 手动创建标准化表达（U2b：消费结果「存为表达」入口，P2C-04 双入口之一）。
 * 落 candidate 态，等待用户激活；新版本行 = 组内 version max+1（§31，不覆盖旧行）。
 */
export async function createExpression(payload: {
  experience_id: number
  type?: string
  content: string
  direction_id?: number
  job_id?: number
  source_refs?: SourceRef[]
}): Promise<Expression> {
  return request<Expression>('/api/jobcraft/experience/expressions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/**
 * AI 生成标准化表达并入库（EXP-P2-04：手动触发，返回 candidate 态新表达）。
 */
export async function generateExpression(cardId: number): Promise<Expression> {
  return request<Expression>(
    `/api/jobcraft/experience/cards/${cardId}/expressions`,
    { method: 'POST', body: JSON.stringify({}) }
  )
}

/**
 * 激活标准化表达（EXP-P2-06 状态机：同版本链其它 active 自动降级为 candidate）。
 */
export async function activateExpression(expressionId: number): Promise<Expression> {
  return request<Expression>(
    `/api/jobcraft/experience/expressions/${expressionId}/actions/activate`,
    { method: 'POST', body: JSON.stringify({}) }
  )
}

/**
 * 弃用标准化表达（EXP-P2-06 状态机：active/candidate → deprecated）。
 */
export async function deprecateExpression(expressionId: number): Promise<Expression> {
  return request<Expression>(
    `/api/jobcraft/experience/expressions/${expressionId}/actions/deprecate`,
    { method: 'POST', body: JSON.stringify({}) }
  )
}

/**
 * 基于既有表达新建版本（EXP-P2-03 §8.3：version+1，不覆盖旧行，版本链可回溯）。
 * content 必填；source_refs 缺省留空时后端沿用生成来源（source_type=experience）。
 */
export async function updateExpression(
  expressionId: number,
  payload: { content: string; source_refs?: SourceRef[] }
): Promise<Expression> {
  return request<Expression>(
    `/api/jobcraft/experience/expressions/${expressionId}/versions`,
    { method: 'POST', body: JSON.stringify(payload) }
  )
}
