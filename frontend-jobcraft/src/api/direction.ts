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
