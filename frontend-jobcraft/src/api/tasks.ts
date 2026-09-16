/**
 * 异步任务系统 API（/api/jobcraft/tasks/*）
 *
 * 为长 AI 调用（简历生成 / 面试准备 / PDF 导出）提供提交、状态轮询、取消能力，
 * 前端据此展示进度反馈，避免同步阻塞。
 */

import { request } from './client'
import type {
  SubmitTaskResult,
  TaskInfo,
  TaskStatusName,
} from './types'

export interface SubmitTaskPayload {
  task_type: string
  params?: Record<string, unknown>
}

export async function submitTask(
  payload: SubmitTaskPayload
): Promise<SubmitTaskResult> {
  return request<SubmitTaskResult>('/api/jobcraft/tasks/submit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getTask(taskId: string): Promise<TaskInfo> {
  return request<TaskInfo>(`/api/jobcraft/tasks/${taskId}`)
}

export async function cancelTask(taskId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/jobcraft/tasks/${taskId}/cancel`, {
    method: 'POST',
  })
}

export async function listTasks(
  status?: TaskStatusName,
  limit = 50
): Promise<{ items: TaskInfo[]; total: number }> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  params.set('limit', String(limit))
  const qs = params.toString()
  return request<{ items: TaskInfo[]; total: number }>(
    `/api/jobcraft/tasks?${qs}`
  )
}

/**
 * 提交异步任务并轮询到完成；任务系统不可用（Redis/worker 未就绪）时
 * 降级为同步端点调用，保证功能可用。
 */
export async function runTaskOrSync<T>(
  taskType: string,
  params: Record<string, unknown>,
  fallback: () => Promise<T>,
  options: PollTaskOptions = {}
): Promise<T> {
  try {
    const submit = await submitTask({ task_type: taskType, params })
    const polled = await pollTaskUntilDone(submit.task_id, {
      interval: options.interval ?? 1500,
      timeout: options.timeout ?? 180_000,
      onProgress: options.onProgress,
    })
    return polled.result as unknown as T
  } catch (err) {
    return fallback()
  }
}

export interface PollTaskOptions {
  interval?: number
  timeout?: number
  onProgress?: (task: TaskInfo) => void
}

export interface PollTaskResult {
  task: TaskInfo
  result: Record<string, unknown>
}

/**
 * 轮询任务直至完成/失败/取消/超时。
 *
 * - completed：返回 `{ task, result }`；
 * - failed/cancelled：抛出包含后端 error 信息的 Error；
 * - 超时：抛出 Error。
 */
export async function pollTaskUntilDone(
  taskId: string,
  options: PollTaskOptions = {}
): Promise<PollTaskResult> {
  const interval = options.interval ?? 1500
  const timeout = options.timeout ?? 120_000
  const deadline = Date.now() + timeout

  for (;;) {
    if (Date.now() > deadline) {
      throw new Error('任务处理超时，请稍后重试')
    }
    // eslint-disable-next-line no-await-in-loop
    const task = await getTask(taskId)
    options.onProgress?.(task)

    if (task.status === 'completed') {
      return { task, result: task.result ?? {} }
    }
    if (task.status === 'failed') {
      throw new Error(task.error || '任务执行失败')
    }
    if (task.status === 'cancelled') {
      throw new Error('任务已取消')
    }

    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, interval))
  }
}
