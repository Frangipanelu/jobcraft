import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  useProfileQuery,
  useUpdateProfileMutation,
  toApiProfilePatch,
  PROFILE_QUERY_KEY,
  EMPTY_PROFILE,
} from './hooks';
import type { UserProfile } from '../../types/jobcraft';

const api = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock('../../api/auth', () => ({ ...api }));

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { wrapper, client };
}

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: 'a@b.com',
  role: '求职者',
  created_at: '2026-01-01',
};

const PROFILE_DATA = {
  display_name: '张三',
  role: 'AI 产品经理',
  target_salary: '30-50K',
  years_of_exp: 3,
  city: '北京',
  target_roles: ['PM'],
  target_companies: ['字节'],
};

describe('profile hooks', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getCurrentUser.mockResolvedValue(AUTH_USER);
    api.getProfile.mockResolvedValue(PROFILE_DATA);
    api.updateProfile.mockResolvedValue({});
  });

  it('useProfileQuery 合并 getCurrentUser + getProfile 映射为领域 UserProfile', async () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useProfileQuery(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      name: '张三',
      role: 'AI 产品经理',
      targetSalary: '30-50K',
      yearsOfExp: 3,
      city: '北京',
      targetRoles: ['PM'],
      targetCompanies: ['字节'],
      email: 'a@b.com',
    });
  });

  it('getProfile 失败时降级使用 auth 用户信息', async () => {
    api.getProfile.mockRejectedValue(new Error('no profile'));
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useProfileQuery(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      name: 'dev',
      email: 'a@b.com',
      role: '求职者',
      yearsOfExp: 0,
    });
  });

  it('useUpdateProfileMutation 以 snake_case 调用后端并乐观合并缓存', async () => {
    const { wrapper, client } = createWrapper();
    client.setQueryData<UserProfile>(PROFILE_QUERY_KEY, {
      ...EMPTY_PROFILE,
      name: '张三',
      role: 'AI 产品经理',
    });

    const { result } = renderHook(() => useUpdateProfileMutation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ name: '李四', targetSalary: '40-60K' });
    });

    expect(api.updateProfile).toHaveBeenCalledWith({ display_name: '李四', target_salary: '40-60K' });
    expect(client.getQueryData<UserProfile>(PROFILE_QUERY_KEY)).toMatchObject({
      name: '李四',
      targetSalary: '40-60K',
      role: 'AI 产品经理',
    });
  });

  it('toApiProfilePatch 字段映射为后端 snake_case', () => {
    expect(
      toApiProfilePatch({ name: 'n', city: 'c', yearsOfExp: 2, targetRoles: ['r'], targetCompanies: [] }),
    ).toEqual({
      display_name: 'n',
      city: 'c',
      years_of_exp: 2,
      target_roles: ['r'],
      target_companies: [],
    });
  });
});