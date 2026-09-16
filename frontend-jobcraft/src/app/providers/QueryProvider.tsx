import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

interface QueryProviderProps {
  children: React.ReactNode;
}

const DEFAULT_OPTIONS = {
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
} as const;

export const QueryProvider: React.FC<QueryProviderProps> = ({ children }) => {
  // 每个挂载实例只创建一次 QueryClient，保证数据缓存与 GC 生命周期一致
  const [queryClient] = useState(() => new QueryClient(DEFAULT_OPTIONS));
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};