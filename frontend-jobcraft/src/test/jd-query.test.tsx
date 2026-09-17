import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { useJobCraft } from '../context/JobCraftContext';
import { JDAnalysisCenterView } from '../components/jd/JDAnalysisCenterView';
import { JDReportDetailView } from '../components/jd/JDReportDetailView';
import { useDeleteJdAnalysisMutation } from '../features/jd/hooks';
import type { JobAnalysisResult } from '../api/types';

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
  getJobAnalysis: vi.fn(),
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

function buildResult(overrides: Partial<JobAnalysisResult> = {}): JobAnalysisResult {
  return {
    job_analysis_id: 12,
    user_id: 1,
    company: '字节跳动',
    position: 'AI 产品经理',
    jd_text: '原始 JD 文本',
    jd_requirements: null,
    ats_profile: null,
    company_context: null,
    match_score: 60,
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

const DETAIL_A = buildResult({
  job_analysis_id: 12,
  company: '字节跳动',
  position: 'AI 产品经理',
  match_score: 82,
});

const DETAIL_B = buildResult({
  job_analysis_id: 13,
  company: '腾讯',
  position: '策略产品经理',
  match_score: 55,
});

const MirrorCount = () => {
  const { jdAnalyses } = useJobCraft();
  return <span data-testid="jd-mirror-count">{jdAnalyses.length}</span>;
};

const DeleteHarness = () => {
  const { syncJdAnalyses } = useJobCraft();
  const del = useDeleteJdAnalysisMutation({ onSync: syncJdAnalyses });
  return <button onClick={() => del.mutate('sub-55')}>删除 sub</button>;
};

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  job.getDashboard.mockResolvedValue({ submissions: [] });
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue({
    analyses: [
      { id: 12, company: '字节跳动', position: 'AI 产品经理', match_score: 82, created_at: '2026-02-01' },
      { id: 13, company: '腾讯', position: '策略产品经理', match_score: 55, created_at: '2026-02-02' },
    ],
  });
  job.getJobAnalysis.mockImplementation(async (id: number) => (id === 13 ? DETAIL_B : DETAIL_A));
  job.deleteSubmission.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useJdAnalysesQuery 迁移视图', () => {
  it('JDAnalysisCenterView 从 query 渲染历史列表并支持搜索过滤', async () => {
    renderWithProviders(
      <>
        <JDAnalysisCenterView />
        <MirrorCount />
      </>,
    );

    fireEvent.click(screen.getByText(/历史研判报告/));

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText('历史研判报告 (2)')).toBeInTheDocument();
    expect(job.listJobAnalyses).toHaveBeenCalledWith(1);
    expect(job.getJobAnalysis).toHaveBeenCalledWith(12);
    expect(job.getJobAnalysis).toHaveBeenCalledWith(13);

    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '腾讯' },
    });
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '不存在的公司xyz' },
    });
    expect(await screen.findByText('未找到符合条件的研判记录')).toBeInTheDocument();

    await screen.findByTestId('jd-mirror-count');
    expect(screen.getByTestId('jd-mirror-count').textContent).toBe('2');
  });

  it('delete：cache 过滤 + 镜像同步，真实分析 id 不发后端删除请求', async () => {
    renderWithProviders(
      <>
        <JDAnalysisCenterView />
        <MirrorCount />
      </>,
    );

    fireEvent.click(screen.getByText(/历史研判报告/));
    await screen.findByText('字节跳动');
    expect(screen.getByTestId('jd-mirror-count').textContent).toBe('2');

    fireEvent.click(screen.getAllByTitle('删除记录')[0]);

    expect(await screen.findByText('历史研判报告 (1)')).toBeInTheDocument();
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(job.deleteSubmission).not.toHaveBeenCalled();
    expect(screen.getByTestId('jd-mirror-count').textContent).toBe('1');
  });
});

describe('useDeleteJdAnalysisMutation', () => {
  it('sub-{number} id 触发后端 deleteSubmission 并同步镜像', async () => {
    renderWithProviders(
      <>
        <DeleteHarness />
        <MirrorCount />
      </>,
    );

    await screen.findByText('删除 sub');
    fireEvent.click(screen.getByText('删除 sub'));

    await vi.waitFor(() => {
      expect(job.deleteSubmission).toHaveBeenCalledWith(55);
    });
  });
});

describe('JDReportDetailView 迁移读路径', () => {
  it('按 analysisId 从 query 命中对应分析', async () => {
    renderWithProviders(<JDReportDetailView analysisId="13" />);

    expect(await screen.findByText('策略产品经理')).toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
  });
});
