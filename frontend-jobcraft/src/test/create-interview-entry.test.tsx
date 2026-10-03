import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { useEffect, useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';
import { renderWithProviders } from './test-utils';
import { useJobCraft } from '../context/JobCraftContext';
import { NewInterviewModal } from '../components/interview/NewInterviewModal';
import { AppRoutes } from '../router/AppRouter';
import type { DashboardItem, JobAnalysisResult } from '../api/types';

/**
 * T-M7-1 页面收敛验收：
 * 1) NewInterviewModal 开→关→开（原实现 isOpen 早退在全部 hooks 之前，打开即崩）；
 * 2) FE-STATE-01 迁移——返回意图由模态向导持位/作废；
 * 3) JD 报告「返回继续」回流改开 Modal（原 go('create_interview') 页面已删）。
 */

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
  listJobAnalyses: vi.fn(),
  getDashboard: vi.fn(),
  getSubmission: vi.fn(),
  listBaseResumes: vi.fn(),
  createSubmission: vi.fn(),
  updateSubmission: vi.fn(),
  deleteSubmission: vi.fn(),
  analyzeJob: vi.fn(),
  analyzeStructuredJd: vi.fn(),
  splitJd: vi.fn(),
  saveResume: vi.fn(),
  createBaseResume: vi.fn(),
  deleteBaseResume: vi.fn(),
  setDefaultBaseResume: vi.fn(),
}));

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));
vi.mock('../api/tasks', () => ({ ...tasks }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

function buildResult(overrides: Partial<JobAnalysisResult> = {}): JobAnalysisResult {
  return {
    job_analysis_id: 13,
    user_id: 1,
    company: '腾讯',
    position: '策略产品经理',
    jd_text: '原始 JD 文本',
    jd_requirements: null,
    ats_profile: null,
    company_context: null,
    match_score: 55,
    match_level: '中匹配',
    customization_needed: false,
    gap_analysis: '整体匹配待补充',
    gap_items: [],
    per_card_scores: [],
    suggestions: [],
    dimension_requirements: [],
    resume_markdown: null,
    created_at: '2026-02-01',
    ...overrides,
  };
}

const DASH_JOB: DashboardItem = {
  id: 1,
  position: 'AI 产品经理',
  company: '字节跳动',
  status: 'APPLIED',
  job_analysis_id: 13,
  has_analysis: true,
  card_count: 1,
  card_version_count: 1,
  has_resume: true,
  is_manual: false,
  delivered: false,
  prep_count: 0,
  review_count: 0,
  created_at: '2026-09-18',
  updated_at: '2026-09-18',
};

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  job.getDashboard.mockResolvedValue({ submissions: [DASH_JOB] });
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue({ analyses: [buildResult()] });
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** 当前 URL pathname 探针（MemoryRouter 不写 window.location）。 */
const PathProbe = () => {
  const location = useLocation();
  return <span data-testid="path">{location.pathname}</span>;
};

/** context 返回意图探针。 */
const TargetProbe = () => {
  const { jdAnalysisReturnTarget } = useJobCraft();
  return <span data-testid="target">{jdAnalysisReturnTarget ?? 'none'}</span>;
};

describe('T-M7-1 NewInterviewModal 开关钩子序（原 isOpen 早退在 hooks 之前）', () => {
  const ToggleHarness = () => {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>打开向导</button>
        <button onClick={() => setOpen(false)}>关闭向导</button>
        <NewInterviewModal isOpen={open} mode="standalone" onClose={() => setOpen(false)} />
      </>
    );
  };

  it('打开 → 关闭 → 再打开，不崩溃且渲染「新建面试准备」', async () => {
    renderWithProviders(<ToggleHarness />);

    fireEvent.click(screen.getByText('打开向导'));
    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();

    fireEvent.click(screen.getByText('关闭向导'));
    expect(screen.queryByText('新建面试准备')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('打开向导'));
    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();
  });
});

describe('T-M7-1 FE-STATE-01 迁移：模态向导持有 jdAnalysisReturnTarget', () => {
  const FlagModalHarness = () => {
    const { setJdAnalysisReturnTarget, jdAnalysisReturnTarget } = useJobCraft();
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setJdAnalysisReturnTarget('create_interview')}>置位返回意图</button>
        <button onClick={() => setOpen(true)}>打开向导</button>
        <NewInterviewModal isOpen={open} mode="standalone" onClose={() => setOpen(false)} />
        <span data-testid="target">{jdAnalysisReturnTarget ?? 'none'}</span>
        <PathProbe />
      </>
    );
  };

  it('重新打开向导即作废残留返回意图（原页面 mount-clear 行为迁移）', async () => {
    renderWithProviders(<FlagModalHarness />);

    fireEvent.click(screen.getByText('置位返回意图'));
    expect(screen.getByTestId('target').textContent).toBe('create_interview');

    fireEvent.click(screen.getByText('打开向导'));
    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('target').textContent).toBe('none'));
  });

  it('向导内「去JD分析页面创建」：置位返回意图 + 关闭向导 + 跳转 /jd-analysis（保留草稿供回流）', async () => {
    renderWithProviders(<FlagModalHarness />);

    fireEvent.click(screen.getByText('打开向导'));
    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();

    fireEvent.click(screen.getByText('去JD分析页面创建'));

    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/jd-analysis'));
    expect(screen.getByTestId('target').textContent).toBe('create_interview');
    expect(screen.queryByText('新建面试准备')).not.toBeInTheDocument();
  });
});

describe('T-M7-1 JD 报告回流改开 Modal（/interview/new 页面已删）', () => {
  const FlagSetter = () => {
    const { setJdAnalysisReturnTarget } = useJobCraft();
    useEffect(() => {
      setJdAnalysisReturnTarget('create_interview');
    }, [setJdAnalysisReturnTarget]);
    return null;
  };

  it('点「返回继续」打开新建面试 Modal，URL 不再跳 /interview/new', async () => {
    renderWithProviders(
      <>
        <FlagSetter />
        <AppRoutes />
        <PathProbe />
        <TargetProbe />
      </>,
      { route: '/jd-report/13' },
    );

    expect(await screen.findByText('策略产品经理')).toBeInTheDocument();
    fireEvent.click(screen.getByText('返回继续'));

    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();
    expect(screen.getByTestId('path').textContent).not.toBe('/interview/new');
    await waitFor(() => expect(screen.getByTestId('target').textContent).toBe('none'));
  });
});
