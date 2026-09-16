import type { ApiErrorPayload } from './types';

/** 统一的 API 业务错误。 */
export class ApiError extends Error {
  public readonly status?: number;
  public readonly code?: string;
  public readonly requestId?: string;
  public readonly details?: unknown;
  public readonly body?: unknown;

  constructor(
    message: string,
    options: {
      status?: number;
      code?: string;
      requestId?: string;
      details?: unknown;
      body?: unknown;
    } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
    this.details = options.details;
    this.body = options.body;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/** 从非 2xx 响应构造 ApiError；优先使用后端标准错误体（{ error: {...} }）。 */
export function toApiError(status: number, body: unknown): ApiError {
  const payload = (body ?? {}) as ApiErrorPayload;
  const err = payload.error ?? {};
  const message = err.message || `请求失败（HTTP ${status}）`;
  return new ApiError(message, {
    status,
    code: err.code ?? String(status),
    requestId: err.requestId,
    details: err.details,
    body,
  });
}