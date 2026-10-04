/**
 * 方向 API（T-M3-6：workbench 方向沉淀汇总）
 */

import { request } from './client'

/** 方向汇总行（GET /api/jobcraft/direction/summary 的 directions 元素）。 */
export interface DirectionSummaryItem {
  id: number
  code: string
  name: string
  status: 'active' | 'archived'
  expression_count: number
  jd_classification_count: number
}

/** 高频缺口聚合行（capability_gap 按维度计数，count 降序）。 */
export interface DirectionGapCount {
  dimension: string
  count: number
}

export interface DirectionSummary {
  directions: DirectionSummaryItem[]
  top_gaps: DirectionGapCount[]
}

/** 方向沉淀汇总（/workbench 面板——方向列表+计数+高频缺口）。 */
export async function getDirectionSummary(): Promise<DirectionSummary> {
  return request<DirectionSummary>('/api/jobcraft/direction/summary')
}

/** 方向读模型（direction 表 6 标量列 + code/label，T-M3-1）。 */
export interface DirectionRead {
  id: number
  user_id: number
  code: string
  name: string
  job_function: string
  primary_role: string
  industry: string
  product: string
  scenario: string
  skills: string
  status: 'active' | 'archived'
  created_at: string | null
  updated_at: string | null
}

/** find-or-create 响应（T-M3-3：created 区分命中/新建）。 */
export interface FindDirectionOrCreateResult {
  direction: DirectionRead
  created: boolean
}

/** 按 name 查找或创建方向（命中含归档原样返回不覆盖六维）。 */
export async function findDirectionOrCreate(payload: {
  name: string
  job_function?: string
  primary_role?: string
  industry?: string
  product?: string
  scenario?: string
  skills?: string
}): Promise<FindDirectionOrCreateResult> {
  return request<FindDirectionOrCreateResult>('/api/jobcraft/direction/find-or-create', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 词典建议响应（T-M4-3 零 LLM；词典只产四维 + 建议方向名）。 */
export interface DirectionSuggestResult {
  matched: boolean
  direction_name: string
  industry: string
  product: string
  scenario: string
  skills: string
}

/** 词典规则建议（POST /direction/suggest；未命中 matched=false，非错误）。 */
export async function suggestDirection(text: string): Promise<DirectionSuggestResult> {
  return request<DirectionSuggestResult>('/api/jobcraft/direction/suggest', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

/** 方向列表（表单方向名 datalist 补全）。 */
export async function listDirections(status?: 'active' | 'archived'): Promise<DirectionRead[]> {
  const qs = status ? `?status=${status}` : ''
  return request<DirectionRead[]>(`/api/jobcraft/direction${qs}`)
}
