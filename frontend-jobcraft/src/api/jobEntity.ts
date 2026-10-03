/**
 * 岗位实体（job 表）写路径 API — T-M5-2
 *
 * 拆分说明：既有 job 实体函数（createJobEntity/listJobEntities/JobEntity 类型）
 * 位于 `api/job.ts`；本文件仅承载 `PATCH /api/jobcraft/job/{id}` 更新入口，
 * 独立成文件以隔离岗位实体写路径与投递/分析域。
 */
import { request } from './client'
import type { JobEntity } from './job'

/** 更新岗位字段（company/position/status/is_active；删除 = is_active:false）。 */
export async function updateJobEntity(
  id: number,
  payload: {
    company?: string
    position?: string
    status?: string
    is_active?: boolean
  },
): Promise<JobEntity> {
  return request<JobEntity>(`/api/jobcraft/job/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
