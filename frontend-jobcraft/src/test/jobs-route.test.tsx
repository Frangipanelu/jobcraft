import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { AppRoutes } from '../router/AppRouter';
import { renderWithProviders } from './test-utils';

const auth = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  getSettings: vi.fn(),
}));

const job = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getSubmission: vi.fn(),
  createSubmission: vi.fn(),
  updateSubmission: vi.fn(),
  deleteSubmission: vi.fn(),
  listBaseResumes: vi.fn(),
  listJobAnalyses: vi.fn(),
  getJobAnalysis: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const SUBMISSIONS = [
  {
    id: 3,
    position: 'AI 策略产品',
    company: '快手',
    status: 'APPLIED',
    job_analysis_id: null,
    has_analysis: false,
    card_version_count: 0,
    card_count: 0,
    has_resume: false,
    is_manual: false,
    prep_count: 0,
    review_count: 0,
    created_at: '2026-09-10T00:00:00',
    updated_at: '2026-09-10T00:00:00',
  },
];

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  job.getDashboard.mockResolvedValue({ submissions: SUBMISSIONS });
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue([]);
});

const assertWorkspaceReached = async () => {
  expect(await screen.findByText('返回我的岗位列表')).toBeInTheDocument();
  // 面包屑 + 岗位空间头部会各出现一次岗位标题
  expect(screen.getAllByText('快手 · AI 策略产品').length).toBeGreaterThan(0);
};

describe('FE-ROUTE-02 真实路由间跳转', () => {
  it('工作台「进入岗位」→ /jobs/:jobId 岗位空间直达', async () => {
    renderWithProviders(<AppRoutes />, { route: '/workbench' });

    expect(await screen.findByText('快手')).toBeInTheDocument();

    fireEvent.click(screen.getAllByText('进入岗位')[0]);

    await assertWorkspaceReached();
  });

  it('岗位列表点击岗位卡 → /jobs/:jobId 岗位空间直达', async () => {
    renderWithProviders(<AppRoutes />, { route: '/jobs' });

    expect(await screen.findByText('快手')).toBeInTheDocument();

    fireEvent.click(screen.getByText('进入岗位空间'));

    await assertWorkspaceReached();
  });
});