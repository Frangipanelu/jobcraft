/**
 * T-M10-2 残②：runTaskOrSync 分级降级测试
 *
 * 分级规则（submit 与 poll 两阶段统一）：
 * - 带 HTTP status 的 4xx（参数错/任务丢失）与 503（Redis 不可用）→ 不降级，原样上抛；
 * - 其他错误（超时、5xx 非 503、网络错误、无 status 异常）→ 静默降级 fallback()，
 *   且必须打点 console.warn('[task_fallback]', ...)。
 *
 * 经真实 client.ts（fetch mock 注入响应）端到端验证：ApiError 携带 status 的
 * additive 契约与两阶段分级行为一并覆盖。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import { runTaskOrSync } from '../api/tasks';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const okSubmitResponse = () =>
  jsonResponse(200, { task_id: 't_1', task_type: 'resume_generate', status: 'pending' });

describe('runTaskOrSync 分级降级（T-M10-2）', () => {
  const fetchMock = vi.mocked(globalThis.fetch);
  type FallbackFn = () => Promise<{ from: 'fallback' }>;
  let fallback: Mock<FallbackFn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchMock.mockReset();
    // 兜底：测试未声明的 fetch 调用直接失败，避免 undefined 响应被误判为降级路径
    fetchMock.mockImplementation(async () => {
      throw new TypeError('测试未预期的 fetch 调用');
    });
    fallback = vi.fn<FallbackFn>(async () => ({ from: 'fallback' }));
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  describe('submit 阶段', () => {
    it('400（参数错）→ 上抛不降级、不打点，Error 携带 status', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(400, { error: { code: 'BAD_REQUEST', message: 'params 必须是 JSON 对象' } })
      );

      const err = await runTaskOrSync('resume_generate', { card_ids: [] }, fallback).catch(
        (e: unknown) => e
      );

      expect(err).toBeInstanceOf(Error);
      expect((err as Error).message).toBe('params 必须是 JSON 对象');
      expect((err as { status?: number }).status).toBe(400);
      expect((err as Error).name).toBe('ApiError');
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('404（任务/类型丢失）→ 上抛不降级', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(404, { error: { code: 'NOT_FOUND', message: '任务不存在' } })
      );

      await expect(runTaskOrSync('resume_generate', {}, fallback)).rejects.toThrow('任务不存在');
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('503（Redis 不可用）→ 上抛不降级', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(503, { error: { code: 'UNAVAILABLE', message: '任务服务暂不可用（Redis 未就绪）' } })
      );

      await expect(runTaskOrSync('resume_generate', {}, fallback)).rejects.toThrow(
        '任务服务暂不可用'
      );
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('500 → 静默降级 fallback + 打点（phase=submit, status=500）', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(500, { error: { code: 'INTERNAL', message: '提交任务失败: boom' } })
      );

      const result = await runTaskOrSync('resume_generate', { company: 'X' }, fallback);

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({
          task_type: 'resume_generate',
          phase: 'submit',
          status: 500,
          message: expect.any(String),
        })
      );
    });

    it('网络错误（fetch 拒绝，无 status）→ 静默降级 + 打点（status undefined）', async () => {
      fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

      const result = await runTaskOrSync('resume_generate', {}, fallback);

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'submit', status: undefined })
      );
    });
  });

  describe('poll 阶段', () => {
    it('轮询 GET 404（任务丢失）→ 上抛不降级', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(
          jsonResponse(404, { error: { code: 'NOT_FOUND', message: '任务不存在或已过期' } })
        );

      await expect(
        runTaskOrSync('resume_generate', {}, fallback, { interval: 1 })
      ).rejects.toThrow('任务不存在或已过期');
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('轮询 GET 503 → 上抛不降级', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(
          jsonResponse(503, { error: { code: 'UNAVAILABLE', message: '任务服务暂不可用（Redis 未就绪）' } })
        );

      await expect(
        runTaskOrSync('resume_generate', {}, fallback, { interval: 1 })
      ).rejects.toThrow('任务服务暂不可用');
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('轮询 GET 500 → 静默降级 + 打点（phase=poll, status=500）', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(
          jsonResponse(500, { error: { code: 'INTERNAL', message: '查询任务失败' } })
        );

      const result = await runTaskOrSync('resume_generate', {}, fallback, { interval: 1 });

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'poll', status: 500 })
      );
    });

    it('轮询超时（自造 Error 无 status）→ 静默降级 + 打点（phase=poll）', async () => {
      fetchMock.mockResolvedValueOnce(okSubmitResponse());

      const result = await runTaskOrSync('resume_generate', {}, fallback, { timeout: -1 });

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'poll', status: undefined })
      );
    });

    it('任务执行 failed（业务错误无 status）→ 静默降级 + 打点', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(
          jsonResponse(200, { status: 'failed', error: 'LLM 调用超限' })
        );

      const result = await runTaskOrSync('resume_generate', {}, fallback, { interval: 1 });

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'poll', status: undefined, message: 'LLM 调用超限' })
      );
    });
  });

  describe('duck-type status 分支（httpStatusOf 非 ApiError 路径，评审 Minor-1）', () => {
    // client.ts 统一产出 ApiError；该分支为向前兼容（其他携带数值 status 的抛出物）。
    // 经 onProgress 回调注入闭合分类边界——当前生产链无此形态抛出物，测试即契约锁定。
    it('抛出 {status:404}（数值鸭子类型）→ 上抛不降级', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(jsonResponse(200, { status: 'running' }));

      const duck = { status: 404, message: '鸭子丢失' };
      await expect(
        runTaskOrSync('resume_generate', {}, fallback, {
          interval: 1,
          onProgress: () => {
            throw duck;
          },
        })
      ).rejects.toBe(duck);

      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('抛出 {status:"500"}（字符串 status 不作数）→ 降级 + 打点', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(jsonResponse(200, { status: 'running' }));

      const result = await runTaskOrSync('resume_generate', {}, fallback, {
        interval: 1,
        onProgress: () => {
          throw { status: '500', message: '字符串状态不算 status' };
        },
      });

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'poll', status: undefined })
      );
    });
  });

  describe('边界补全（评审 Minor-5）', () => {
    it('mid-poll 401（token 过期）→ 上抛不降级', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(
          jsonResponse(401, {
            error: { code: 'UNAUTHORIZED', message: '认证已过期，请重新登录' },
          })
        );

      await expect(
        runTaskOrSync('resume_generate', {}, fallback, { interval: 1 })
      ).rejects.toThrow('认证已过期，请重新登录');
      expect(fallback).not.toHaveBeenCalled();
      expect(warnSpy).not.toHaveBeenCalled();
    });

    it('fallback 自身抛错 → 错误上抛不被吞（降级打点仍先发生）', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse(500, { error: { code: 'INTERNAL', message: '提交任务失败' } })
      );
      fallback.mockImplementationOnce(async () => {
        throw new Error('fallback 自身失败');
      });

      await expect(runTaskOrSync('resume_generate', {}, fallback)).rejects.toThrow(
        'fallback 自身失败'
      );
      expect(warnSpy).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ phase: 'submit', status: 500 })
      );
    });

    it('非 Error 抛出物（字符串）→ String(err) 降级不崩', async () => {
      fetchMock
        .mockResolvedValueOnce(okSubmitResponse())
        .mockResolvedValueOnce(jsonResponse(200, { status: 'running' }));

      const result = await runTaskOrSync('resume_generate', {}, fallback, {
        interval: 1,
        onProgress: () => {
          throw '原始字符串错误';
        },
      });

      expect(result).toEqual({ from: 'fallback' });
      expect(fallback).toHaveBeenCalledTimes(1);
      expect(warnSpy).toHaveBeenCalledWith(
        '[task_fallback]',
        expect.objectContaining({ message: '原始字符串错误', status: undefined })
      );
    });
  });

  it('成功路径：submit+poll 完成 → 返回结果，不降级不打点', async () => {
    fetchMock
      .mockResolvedValueOnce(okSubmitResponse())
      .mockResolvedValueOnce(
        jsonResponse(200, { status: 'completed', result: { polished_text: 'x' } })
      );

    const result = await runTaskOrSync('experience_polish', {}, fallback, { interval: 1 });

    expect(result).toEqual({ polished_text: 'x' });
    expect(fallback).not.toHaveBeenCalled();
    expect(warnSpy).not.toHaveBeenCalled();
  });
});
