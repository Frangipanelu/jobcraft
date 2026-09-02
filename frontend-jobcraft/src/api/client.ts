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
}

async function parseUnifiedError(res: Response, fallback: string): Promise<Error> {
  const text = await res.text().catch(() => 'Unknown error')
  let body: UnifiedErrorBody | string = text
  try {
    body = JSON.parse(text) as UnifiedErrorBody
  } catch {
    // 保持原始 text
  }
  return new Error(parseErrorMessage(body, fallback))
}

function parseErrorMessage(body: UnifiedErrorBody | string, fallback: string): string {
  if (typeof body === 'string') {
    return body || fallback
  }
  if (body && typeof body === 'object' && body.msg) {
    return body.msg
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
