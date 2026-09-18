import type { Page } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8000';

/** 后端注册接口。返回 user_id。 */
export async function registerUser(username: string, password: string): Promise<number> {
  const resp = await fetch(`${BACKEND_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, display_name: username }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`注册失败 ${resp.status}: ${text.slice(0, 200)}`);
  }
  const data = await resp.json();
  return data.user_id;
}

/** 后端登录接口。返回 access_token。 */
export async function loginUser(username: string, password: string): Promise<string> {
  const resp = await fetch(`${BACKEND_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`登录失败 ${resp.status}: ${text.slice(0, 200)}`);
  }
  const data = await resp.json();
  return data.access_token;
}

/**
 * 在 Playwright 页面中注入 auth token 到 localStorage，
 * 使 autoLogin 可用（跳过 UI 登录流程）。
 */
export async function injectAuthToken(page: Page, token: string): Promise<void> {
  await page.evaluate((t) => {
    localStorage.setItem('jobcraft_token', t);
  }, token);
}

/** 生成唯一测试用户名。 */
export function uniqueUser(prefix = 'e2e') {
  const ts = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 6);
  return `${prefix}_${ts}${rand}`;
}
