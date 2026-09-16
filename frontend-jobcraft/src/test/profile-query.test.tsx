import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { TopHeader } from '../components/layout/TopHeader';
import { UserProfileView } from '../components/user/UserProfileView';

const api = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  getSettings: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...api }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const PROFILE_DATA = {
  display_name: '张三',
  role: 'AI 产品经理',
  target_salary: '30-50K',
  years_of_exp: 3,
  city: '北京',
};

beforeEach(() => {
  vi.resetAllMocks();
  api.autoLogin.mockResolvedValue(1);
  api.getCurrentUser.mockResolvedValue(AUTH_USER);
  api.getProfile.mockResolvedValue(PROFILE_DATA);
  api.updateProfile.mockResolvedValue({});
  api.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
});

describe('TopHeader + useProfileQuery 迁移', () => {
  it('从 react-query 缓存渲染用户姓名与角色（不再读 context user）', async () => {
    renderWithProviders(<TopHeader onOpenNewJob={() => {}} />);

    const avatar = await screen.findByText('张');
    expect(avatar).toBeInTheDocument();

    fireEvent.click(avatar.closest('button') as HTMLElement);
    expect(await screen.findByText('张三')).toBeInTheDocument();
    expect(screen.getByText('AI 产品经理')).toBeInTheDocument();
  });
});

describe('UserProfileView + useProfileQuery/useUpdateProfileMutation 迁移', () => {
  it('表单回填来自资料查询，保存以 snake_case 调用 updateProfile', async () => {
    renderWithProviders(<UserProfileView />);

    expect(await screen.findByText('张三')).toBeInTheDocument();

    fireEvent.click(screen.getByText('个人基本资料'));
    const nameInput = screen.getByDisplayValue('张三');
    fireEvent.change(nameInput, { target: { value: '李四' } });

    fireEvent.click(screen.getByRole('button', { name: '保存个人资料' }));

    await waitFor(() =>
      expect(api.updateProfile).toHaveBeenCalledWith(expect.objectContaining({ display_name: '李四' })),
    );
  });
});