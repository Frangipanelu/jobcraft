import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useExpressionsQuery,
  useGenerateExpressionMutation,
  useActivateExpressionMutation,
  useDeprecateExpressionMutation,
} from './expressionHooks';
import type { Expression } from '../../api/types';

const api = vi.hoisted(() => ({
  listExpressions: vi.fn(),
  generateExpression: vi.fn(),
  activateExpression: vi.fn(),
  deprecateExpression: vi.fn(),
}));

vi.mock('../../api/experience', () => ({ ...api }));

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { wrapper, client };
}

const EXPRESSION_CANDIDATE: Expression = {
  id: 11,
  user_id: 1,
  experience_id: 7,
  type: 'standardized',
  content: '负责端侧大模型量化评测，建立量产评估体系。',
  version: 2,
  validation_level: 0,
  usage_count: 0,
  source_refs: [],
  status: 'candidate',
};

const EXPRESSION_ACTIVE: Expression = {
  ...EXPRESSION_CANDIDATE,
  id: 9,
  version: 1,
  status: 'active',
};

const EXPRESSION_DEPRECATED: Expression = {
  ...EXPRESSION_CANDIDATE,
  id: 8,
  version: 0,
  status: 'deprecated',
};

describe('expression hooks（EXP-P2-08）', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('useExpressionsQuery 拉取并返回该卡表达列表', async () => {
    api.listExpressions.mockResolvedValue({
      experience_id: 7,
      items: [EXPRESSION_CANDIDATE, EXPRESSION_ACTIVE, EXPRESSION_DEPRECATED],
    });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useExpressionsQuery(7), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.listExpressions).toHaveBeenCalledWith(7);
    expect(result.current.data).toHaveLength(3);
    expect(result.current.data![0]!.status).toBe('candidate');
  });

  it('listExpressions 返回空时兜底为空数组', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [] });
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useExpressionsQuery(7), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it('useGenerateExpressionMutation 调后端生成并返回新表达', async () => {
    api.generateExpression.mockResolvedValue(EXPRESSION_CANDIDATE);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useGenerateExpressionMutation(7), { wrapper });

    let out!: Expression;
    await act(async () => {
      out = await result.current.mutateAsync(undefined);
    });
    expect(api.generateExpression).toHaveBeenCalledWith(7);
    expect(out.id).toBe(EXPRESSION_CANDIDATE.id);
    expect(out.status).toBe('candidate');
  });

  it('useActivateExpressionMutation 调激活端点', async () => {
    api.activateExpression.mockResolvedValue(EXPRESSION_ACTIVE);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useActivateExpressionMutation(7), { wrapper });

    let out!: Expression;
    await act(async () => {
      out = await result.current.mutateAsync(11);
    });
    expect(api.activateExpression).toHaveBeenCalledWith(11);
    expect(out.status).toBe('active');
  });

  it('useDeprecateExpressionMutation 调弃用端点', async () => {
    api.deprecateExpression.mockResolvedValue(EXPRESSION_DEPRECATED);
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useDeprecateExpressionMutation(7), { wrapper });

    let out!: Expression;
    await act(async () => {
      out = await result.current.mutateAsync(8);
    });
    expect(api.deprecateExpression).toHaveBeenCalledWith(8);
    expect(out.status).toBe('deprecated');
  });

  it('激活成功后使表达列表失活（触发回流）', async () => {
    api.listExpressions.mockResolvedValue({
      experience_id: 7,
      items: [EXPRESSION_CANDIDATE],
    });
    api.activateExpression.mockResolvedValue(EXPRESSION_ACTIVE);
    const { wrapper } = createWrapper();

    const { result } = renderHook(
      () => ({
        query: useExpressionsQuery(7),
        activate: useActivateExpressionMutation(7),
      }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.query.isSuccess).toBe(true));
    const callsBefore = api.listExpressions.mock.calls.length;

    await act(async () => {
      await result.current.activate.mutateAsync(11);
    });

    await waitFor(() => {
      expect(api.listExpressions.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});