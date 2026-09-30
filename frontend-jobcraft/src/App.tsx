import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { JobCraftProvider, ToastProvider, useJobCraft } from './context/JobCraftContext';
import { AppRouter } from './router/AppRouter';
import { AuthPage } from './pages/AuthPage';

/**
 * BrowserRouter 提升至 Provider 之上（FE-NAV-01）：
 * JobCraftProvider 内的 `navigateTo` 需要 `useNavigate` 做真实路由跳转，
 * 故路由上下文必须包住 Provider（测试侧 test-utils 的 MemoryRouter 同步外提）。
 */
export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <JobCraftProvider>
          <AppShell />
        </JobCraftProvider>
      </ToastProvider>
    </BrowserRouter>
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

  // 已登录：进入路由层（AppRoutes 全部为 AppShell 真实路由页）
  return <AppRouter />;
};