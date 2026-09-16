import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { QueryProvider } from '../app/providers/QueryProvider';
import { apiClient } from '../services/api/client';

describe('QueryProvider 基础设施', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('跨重渲染保持同一个 QueryClient 实例', () => {
    const seen: Array<QueryClient | null> = [];
    const Probe = () => {
      seen.push(useQueryClient());
      return null;
    };
    const { rerender } = render(
      <QueryProvider>
        <Probe />
      </QueryProvider>,
    );
    rerender(
      <QueryProvider>
        <Probe />
      </QueryProvider>,
    );
    expect(seen[0]).not.toBeNull();
    expect(seen[1]).not.toBeNull();
    expect(seen[0]).toBe(seen[1]);
  });

  it('查询可穿透到 apiClient 并渲染结果', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ value: 'pong' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const Probe = () => {
      const { data, status } = useQuery({
        queryKey: ['echo'],
        queryFn: async () => (await apiClient.request<{ value: string }>('/api/echo')).value,
      });
      return <span>{status === 'success' ? data : status}</span>;
    };

    render(
      <QueryProvider>
        <Probe />
      </QueryProvider>,
    );

    await waitFor(() => expect(screen.getByText('pong')).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});