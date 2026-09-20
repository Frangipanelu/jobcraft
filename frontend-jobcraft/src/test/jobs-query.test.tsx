import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { useJobsQuery } from '../features/jobs/hooks';
import { JobsListView } from '../components/jobs/JobsListView';
import { NewJobModal } from '../components/jobs/NewJobModal';
import { WorkbenchView } from '../components/workbench/WorkbenchView';

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
    id: 1,
    position: 'AI 产品经理',
    company: '字节跳动',
    status: 'APPLIED',
    job_analysis_id: null,
    has_analysis: false,
    card_version_count: 0,
    card_count: 0,
    has_resume: false,
    is_manual: false,
    delivered: false,
    prep_count: 0,
    review_count: 0,
    created_at: '2026-09-01T00:00:00',
    updated_at: '2026-09-02T00:00:00',
  },
  {
    id: 2,
    position: '搜索策略产品',
    company: '腾讯',
    status: 'ROUND_1',
    job_analysis_id: 5,
    has_analysis: true,
    card_version_count: 0,
    card_count: 0,
    has_resume: false,
    is_manual: false,
    delivered: true,
    prep_count: 1,
    review_count: 0,
    created_at: '2026-09-05T00:00:00',
    updated_at: '2026-09-06T00:00:00',
  },
];

const MIRROR_JOB = {
  id: 99,
  user_id: 1,
  job_analysis_id: null,
  position: 'AI 策略产品',
  company: '快手',
  jd_text: '',
  resume_markdown: '',
  resume_file_path: null,
  card_version_ids: [],
  status: 'APPLIED',
  notes: '',
  delivered: false,
  created_at: null,
  updated_at: null,
};

const CacheSpy = () => {
  const { data: jobs = [] } = useJobsQuery();
  return <span data-testid="cache-count">{jobs.length}</span>;
};

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
  job.createSubmission.mockResolvedValue(MIRROR_JOB);
});

describe('useJobsQuery 迁移视图', () => {
  it('JobsListView 从 query 渲染岗位、筛选计数与状态徽标', async () => {
    renderWithProviders(<JobsListView onOpenNewJob={() => {}} />);

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText('全部 (2)')).toBeInTheDocument();
    expect(screen.getByText('待处理 (1)')).toBeInTheDocument();
    expect(screen.getByText('待面试 (1)')).toBeInTheDocument();
    expect(job.getDashboard).toHaveBeenCalledWith(1);
  });

  it('create：cache 前置写入（未迁移视图可读）', async () => {
    renderWithProviders(
      <>
        <JobsListView onOpenNewJob={() => {}} />
        <NewJobModal isOpen onClose={() => {}} />
        <CacheSpy />
      </>,
    );

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('例如：字节跳动、腾讯、微软'), {
      target: { value: '快手' },
    });
    fireEvent.change(screen.getByPlaceholderText('例如：AI 产品经理、搜索策略专家'), {
      target: { value: 'AI 策略产品' },
    });
    fireEvent.click(screen.getByRole('button', { name: /创建并进入岗位空间/ }));

    expect(await screen.findByText('快手')).toBeInTheDocument();
    expect(screen.getByText('全部 (3)')).toBeInTheDocument();
    expect(screen.getByText('待处理 (2)')).toBeInTheDocument();
    expect(job.createSubmission).toHaveBeenCalledWith({
      position: 'AI 策略产品',
      company: '快手',
    });
    await screen.findByTestId('cache-count');
    expect(screen.getByTestId('cache-count').textContent).toBe('3');
  });

  it('terminate/resume：乐观更新 cache', async () => {
    renderWithProviders(
      <>
        <JobsListView onOpenNewJob={() => {}} />
        <CacheSpy />
      </>,
    );

    await screen.findByText('字节跳动');
    expect(screen.getByTestId('cache-count').textContent).toBe('2');

    fireEvent.click(screen.getAllByText('标记已结束')[0]);
    expect(await screen.findByText('恢复处理')).toBeInTheDocument();
    expect(screen.getByText('已结束 (1)')).toBeInTheDocument();
    expect(screen.getByText('待处理 (0)')).toBeInTheDocument();
    expect(screen.getByTestId('cache-count').textContent).toBe('2');

    fireEvent.click(screen.getByText('恢复处理'));
    expect(await screen.findByText('待处理 (1)')).toBeInTheDocument();
    expect(screen.getByText('已结束 (0)')).toBeInTheDocument();
  });
});

describe('WorkbenchView 迁移', () => {
  it('统计来自 query（activeCount=2），不读 context jobs', async () => {
    renderWithProviders(<WorkbenchView onOpenNewJob={() => {}} />);

    expect(await screen.findByText('正在推进')).toBeInTheDocument();
    expect(screen.getByText('2 个岗位')).toBeInTheDocument();
  });
});