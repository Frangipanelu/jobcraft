/**
 * API 层类型定义（骨架）。
 *
 * 契约依据：docs/design-decisions/design-v2.0/JOBCRAFT_API_SPEC.md（v0.1）
 * - 成功响应：裸资源 JSON（如 jobs 分页为 { items, nextCursor }）。
 * - 标准错误：HTTP 4xx/5xx + body { error: { code, message, details, requestId } }。
 */

/** 标准错误响应体（见 API SPEC §1.7）。 */
export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    requestId?: string;
  };
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/** ApiClient 构造选项。 */
export interface ApiClientOptions {
  /** 默认空字符串（走 vite /api 代理到 localhost:8001）；迁移 /api/v1 时传入。 */
  baseURL?: string;
  defaultHeaders?: Record<string, string>;
  /** 认证 token 获取函数；缺省从 localStorage 读取（键与遗留代码一致）。 */
  getAuthToken?: () => string | null;
  /** 可注入 fetch 实现以便测试。 */
  fetchImpl?: typeof fetch;
}

export interface ApiRequestOptions extends RequestInit {
  method?: HttpMethod;
  /** 请求超时毫秒数，默认 30s。 */
  timeoutMs?: number;
}