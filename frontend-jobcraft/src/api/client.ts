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
