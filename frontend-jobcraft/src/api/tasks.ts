/**
 * 异步任务系统 API（/api/jobcraft/tasks/*）
 *
 * 为长 AI 调用（简历生成 / 面试准备 / PDF 导出）提供提交、状态轮询、取消能力，
 * 前端据此展示进度反馈，避免同步阻塞。
 */

import { request, ApiError } from './client'
import type {
  SubmitTaskResult,
  TaskInfo,
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

/** 分级降级的触发阶段（打点用） */
type FallbackPhase = 'submit' | 'poll'

/**
 * 读取错误携带的 HTTP status。
 *
 * 优先识别 `ApiError`（client.ts 统一抛出），兼容其他携带数值 `status` 的错误；
 * 无 status（超时自造 Error、网络错误、业务失败等）返回 undefined。
 */
function httpStatusOf(err: unknown): number | undefined {
  if (err instanceof ApiError) return err.status
  if (typeof err === 'object' && err !== null && 'status' in err) {
    const status = (err as { status: unknown }).status
    if (typeof status === 'number') return status
  }
  return undefined
}

/**
 * 分级降级判定（PRD §7 异步任务时序图 / matrix T-M10-2 口径）：
 *
 * - 4xx（400 参数错、404 任务丢失等）与 503（Redis 不可用）→ 不降级，原样上抛，
 *   交调用方既有 error toast 路径接管；
 * - 其余（超时、5xx 非 503、网络错误、无 status 异常）→ 静默降级 fallback()；
 *   3xx（未被 fetch 跟随的最终响应，如重定向异常）同落降级分支，不作上抛。
 */
function shouldRethrow(err: unknown): boolean {
  const status = httpStatusOf(err)
  if (status === undefined) return false
  return (status >= 400 && status < 500) || status === 503
}

/**
 * 静默降级打点（`task_fallback` 占位，T-M10-2）。
 *
 * 打点占位说明：后端 Prometheus 无对应 FE task_fallback 指标（PRD §8.1 记载缺口），
 * 产品侧埋点基建（PRD §8.2）尚未落地——此处仅为前端结构化 console.warn 占位，
 * 待埋点基建落地后迁移；这是本文件唯一的 console 点位，禁止在业务代码散落裸 console。
 *
 * 脱敏禁令：message 可能回显用户派生内容（后端 error 原样透传）——当前仅本地
 * console 输出，可接受；未来接入服务端埋点前必须先做脱敏处理。
 */
function logTaskFallback(
  taskType: string,
  phase: FallbackPhase,
  err: unknown
): void {
  const message = err instanceof Error ? err.message : String(err)
  console.warn('[task_fallback]', {
    task_type: taskType,
    phase,
    status: httpStatusOf(err),
    message,
  })
}

/**
 * 提交异步任务并轮询到完成；超时/网络错误/5xx 非 503/业务失败 → 静默降级为
 * 同步端点调用（fallback）保证功能可用；4xx 与 503（Redis 不可用）→ 原样上抛，
 * 交调用方既有 error toast 路径接管。
 *
 * 分级降级（submit 与 poll 两阶段统一，见 {@link shouldRethrow}）：
 * 4xx/503 原样上抛不降级；其他错误静默降级 fallback() 并打点 task_fallback。
 */
export async function runTaskOrSync<T>(
  taskType: string,
  params: Record<string, unknown>,
  fallback: () => Promise<T>,
  options: PollTaskOptions = {}
): Promise<T> {
  let phase: FallbackPhase = 'submit'
  try {
    const submit = await submitTask({ task_type: taskType, params })
    phase = 'poll'
    const polled = await pollTaskUntilDone(submit.task_id, {
      interval: options.interval ?? 1500,
      timeout: options.timeout ?? 180_000,
      onProgress: options.onProgress,
    })
    return polled.result as unknown as T
  } catch (err) {
    if (shouldRethrow(err)) throw err
    logTaskFallback(taskType, phase, err)
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
 * - failed/cancelled：抛出包含后端 error 信息的 Error（无 status，分级判定按降级处理）；
 * - 超时：抛出 Error（无 status，降级）；
 * - 轮询 HTTP 错误经 client.ts 抛出 ApiError（携带 status，供 runTaskOrSync 分级：
 *   4xx/503 上抛不降级）。
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
