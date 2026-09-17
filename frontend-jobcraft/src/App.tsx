import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { JobCraftProvider, useJobCraft } from './context/JobCraftContext';
import { AppRouter } from './router/AppRouter';
import { AuthPage } from './pages/AuthPage';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <JobCraftProvider>
        <AppShell />
      </JobCraftProvider>
    </QueryClientProvider>
  );
}

const AppShell: React.FC = () => {
  const { isAuthenticated, isInitialLoaded, isLoading } = useJobCraft();

  // 初次启动：正在确认登录状态
  if (isLoading && !isInitialLoaded) {
    return (
      <div className="flex h-screen bg-page items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sage border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted">正在进入 JobCraft…</p>
        </div>
      </div>
    );
  }

  // 未登录：进入登录/注册页
  if (!isAuthenticated) {
    return <AuthPage />;
  }

  // 已登录：进入路由层（AppRoutes 通过 LegacyPageWrapper 桥接遗留 MainLayout）
  return <AppRouter />;
};