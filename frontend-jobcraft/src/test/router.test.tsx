import { describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import { AppRoutes } from '../router/AppRouter';
import { renderWithProviders } from './test-utils';

describe('AppRoutes 路由匹配（基础设施冒烟测试）', () => {
  it('/workbench 匹配工作台视图', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/workbench' });
    await waitFor(() => expect(ui.getByText('正在推进')).toBeInTheDocument());
  });

  it('/jobs/:jobId 匹配岗位空间视图', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/jobs/job-test-1' });
    await waitFor(() => expect(ui.getByText('未找到岗位信息')).toBeInTheDocument());
  });

  it('/profile 直接渲染个人中心路由页（AppShell 壳 + ProfilePage，不经 LegacyPageWrapper）', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/profile' });
    await waitFor(() => expect(ui.getByText('账号设置')).toBeInTheDocument());
    expect(ui.getByText('职业资产')).toBeInTheDocument();
    expect(ui.getByText('求职中 · 积极沟通')).toBeInTheDocument();
  });

  it('/profile?tab=preferences 传递子 tab 打开求职偏好', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/profile?tab=preferences' });
    await waitFor(() => expect(ui.getByText('意向职位方向')).toBeInTheDocument());
  });
});