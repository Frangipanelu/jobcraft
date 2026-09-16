import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../services/api/client';
import { ApiError, isApiError } from '../services/api/errors';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiClient 基础设施', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('2xx：返回解析后的 JSON，并注入 Authorization 头', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      return jsonResponse({ authorization: headers.get('Authorization') });
    });
    const client = new ApiClient({ fetchImpl: fetchMock, getAuthToken: () => 'tok-abc' });

    const data = await client.request<{ authorization: string | null }>('/api/ping');

    expect(data).toEqual({ authorization: 'Bearer tok-abc' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('非 2xx：按标准错误体 { error } 抛 ApiError', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: 'NOT_FOUND',
            message: '资源不存在',
            details: { id: 42 },
            requestId: 'req_0001',
          },
        },
        404,
      ),
    );
    const client = new ApiClient({ fetchImpl: fetchMock });

    const error = await client.request('/api/missing').catch((e) => e);

    expect(isApiError(error)).toBe(true);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).code).toBe('NOT_FOUND');
    expect((error as ApiError).requestId).toBe('req_0001');
    expect((error as ApiError).message).toContain('资源不存在');
  });

  it('超时：超过 timeoutMs 抛 code=TIMEOUT 的 ApiError', async () => {
    // 模拟实现：只有 AbortSignal 触发才会结束的 fetch（真实 fetch 行为）
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          const err = new Error('The operation was aborted.');
          err.name = 'AbortError';
          reject(err);
        });
      });
    });
    const client = new ApiClient({ fetchImpl: fetchMock });

    const error = await client
      .request('/api/slow', { timeoutMs: 50 })
      .then(() => null)
      .catch((e) => e);

    expect(isApiError(error)).toBe(true);
    expect((error as ApiError).code).toBe('TIMEOUT');
  });
});