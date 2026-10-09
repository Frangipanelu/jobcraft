/**
 * API 客户端 —— 全项目唯一的 fetch 出口
 *
 * - 所有 HTTP 请求必须经由本文件的 request()/requestFormData()，禁止在
 *   组件/context 层直接调用 fetch/axios/XHR/WebSocket。
 * - auth token 在此集中注入（Authorization: Bearer），错误处理统一收敛。
 */

const BASE_URL = ''

let authToken: string | null = localStorage.getItem('jobcraft_token')

export function setAuthToken(token: string | null) {
  authToken = token
  if (token) {
    localStorage.setItem('jobcraft_token', token)
  } else {
    localStorage.removeItem('jobcraft_token')
  }
}

export function getAuthToken(): string | null {
  return authToken
}

interface UnifiedErrorBody {
  code?: number
  msg?: string
  data?: unknown
  error?: {
    code?: string
    message?: string
    details?: unknown
    requestId?: string
  }
}

/**
 * 携带 HTTP status 的统一错误对象（T-M10-2 additive）。
 *
 * 消息解析与统一错误契约 `{error:{code,message}}` 完全不变——`ApiError` 仅是
 * `Error` 的子类（message 语义、`instanceof Error` 均与既有消费方兼容），
 * 附加 `status` 供调用方做分级判断（如 runTaskOrSync 4xx/503 不降级）。
 */
export class ApiError extends Error {
  /** HTTP 响应状态码（非 2xx 时由 request 系列注入） */
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function parseUnifiedError(res: Response, fallback: string): Promise<ApiError> {
  const text = await res.text().catch(() => 'Unknown error')
  let body: UnifiedErrorBody | string = text
  try {
    body = JSON.parse(text) as UnifiedErrorBody
  } catch {
    // 保持原始 text
  }
  return new ApiError(parseErrorMessage(body, fallback), res.status)
}

function parseErrorMessage(body: UnifiedErrorBody | string, fallback: string): string {
  if (typeof body === 'string') {
    return body || fallback
  }
  if (body && typeof body === 'object') {
    if (body.error && typeof body.error.message === 'string' && body.error.message) {
      return body.error.message
    }
    if (body.msg) {
      return body.msg
    }
  }
  return fallback
}

export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options,
  })

  if (!res.ok) {
    throw await parseUnifiedError(res, `Request failed: ${res.status}`)
  }

  return res.json() as Promise<T>
}

export async function requestFormData<T>(url: string, formData: FormData, method = 'POST'): Promise<T> {
  const headers: Record<string, string> = {}
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${url}`, {
    method,
    headers,
    body: formData,
  })

  if (!res.ok) {
    throw await parseUnifiedError(res, `Request failed: ${res.status}`)
  }

  return res.json() as Promise<T>
}

/**
 * 二进制下载出口（blob 端点，如全量数据导出）。
 * 与 request() 同规则：token 集中注入、非 2xx 统一抛错；不设 Content-Type。
 */
export async function requestBlob(url: string, options?: RequestInit): Promise<Blob> {
  const headers: Record<string, string> = {}
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const res = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options,
  })

  if (!res.ok) {
    throw await parseUnifiedError(res, `Request failed: ${res.status}`)
  }

  return res.blob()
}
