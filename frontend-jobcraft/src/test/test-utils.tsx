import React, { type ReactElement } from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { JobCraftProvider, ToastProvider } from '../context/JobCraftContext';

/** 为测试创建隔离的 QueryClient（关闭重试，避免测试拖沓）。 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

interface RenderWithProvidersOptions {
  route?: string;
  queryClient?: QueryClient;
}

/** 默认包装：QueryClient + ToastProvider + JobCraftProvider + MemoryRouter。 */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', queryClient = createTestQueryClient() }: RenderWithProvidersOptions = {},
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <JobCraftProvider>
          <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
        </JobCraftProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}