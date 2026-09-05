/**
 * 认证模块
 * 自动登录 + JWT Token 管理
 */

import { request, setAuthToken, getAuthToken } from './client'

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
}

export interface UserProfile {
  id: number
  username: string
  display_name: string | null
  role: string
  created_at: string
}

/**
 * 尝试已有 token 自动登录
 * 有效则返回用户 id；无 token 或 token 失效返回 null（由页面引导登录）
 */
export async function autoLogin(): Promise<number | null> {
  const existingToken = getAuthToken()
  if (!existingToken) {
    return null
  }

  // 验证 token 是否有效
  try {
    const profile = await request<UserProfile>('/api/auth/me')
    return profile.id
  } catch {
    // token 无效，清除后引导重新登录
    setAuthToken(null)
    return null
  }
}

/**
 * 账号密码登录
 */
export async function login(username: string, password: string): Promise<number> {
  const result = await request<AuthTokenResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setAuthToken(result.access_token)
  return result.user_id
}

/**
 * 注册新账号
 */
export async function register(
  username: string,
  password: string,
  email?: string
): Promise<number> {
  const result = await request<AuthTokenResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password, email: email || null }),
  })
  setAuthToken(result.access_token)
  return result.user_id
}

/**
 * 获取当前用户信息
 */
export async function getCurrentUser(): Promise<UserProfile> {
  return request<UserProfile>('/api/auth/me')
}

/**
 * 获取用户详细资料（user_profiles 表）
 */
export async function getProfile(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/auth/profile')
}

/**
 * 更新用户详细资料（部分更新）
 */
export async function updateProfile(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/api/auth/profile', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

/**
 * 登出
 */
export function logout() {
  setAuthToken(null)
}
