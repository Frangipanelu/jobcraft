import { ApiError, toApiError } from './errors';
import type { ApiClientOptions, ApiRequestOptions } from './types';

/** 遗留代码使用的本地 token 键（与 src/api/client.ts 保持一致）。 */
export const TOKEN_STORAGE_KEY = 'jobcraft_token';

/** 从 localStorage 读取认证 token（惰性读取，避免模块加载时快照）。 */
export function getAuthToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

const DEFAULT_TIMEOUT_MS = 30_000;

/**
 * 通用请求客户端骨架。
 *
 * 只提供传输能力（token 注入 / 超时 / 错误归一化），不包含任何业务 endpoint。
 * 业务 API 在迁移到 src/features/* 时基于该客户端实现。
 */
export class ApiClient {
  private readonly baseURL: string;
  private readonly defaultHeaders: Record<string, string>;
  private readonly getToken: () => string | null;
  // 允许测试注入 fetch；未注入时每次请求动态读取 globalThis.fetch，便于运行时替换
  private readonly fetchImpl?: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseURL = options.baseURL ?? '';
    this.defaultHeaders = options.defaultHeaders ?? {};
    this.getToken = options.getAuthToken ?? getAuthToken;
    this.fetchImpl = options.fetchImpl;
  }

  /**
   * 发起请求并以 JSON 返回响应体。
   * 2xx：返回解析后的资源 JSON；非 2xx：抛出 ApiError。
   */
  async request<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
    const { timeoutMs = DEFAULT_TIMEOUT_MS, headers, ...init } = options;

    const requestHeaders = new Headers(this.defaultHeaders);
    if (headers) {
      new Headers(headers).forEach((value, key) => requestHeaders.set(key, value));
    }
    const token = this.getToken();
    if (token) {
      requestHeaders.set('Authorization', `Bearer ${token}`);
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await this.doFetch(`${this.baseURL}${url}`, {
        ...init,
        headers: requestHeaders,
        signal: controller.signal,
      });
      return await this.parse<T>(response);
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (error instanceof Error && error.name === 'AbortError') {
        throw new ApiError(`请求超时（${timeoutMs}ms）`, { code: 'TIMEOUT' });
      }
      throw new ApiError('网络请求失败', { code: 'NETWORK_ERROR', body: error });
    } finally {
      clearTimeout(timer);
    }
  }

  private async doFetch(url: string, init: RequestInit): Promise<Response> {
    const impl = this.fetchImpl ?? globalThis.fetch;
    return impl(url, init);
  }

  /** 解析响应体；非 2xx 归一化为 ApiError。 */
  private async parse<T>(response: Response): Promise<T> {
    const text = await response.text();
    let body: unknown = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }
    if (!response.ok) {
      throw toApiError(response.status, body);
    }
    return body as T;
  }
}

/** 默认客户端实例：走 vite /api 代理，token 来自 localStorage。 */
export const apiClient = new ApiClient();

export { ApiError };