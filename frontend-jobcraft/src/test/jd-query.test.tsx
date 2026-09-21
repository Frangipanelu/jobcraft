import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { createTestQueryClient, renderWithProviders } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { JDAnalysisCenterView } from '../components/jd/JDAnalysisCenterView';
import { JDReportDetailView } from '../components/jd/JDReportDetailView';
import {
  useCreateJdAnalysisMutation,
  useCreateStructuredJdAnalysisMutation,
  useDeleteJdAnalysisMutation,
  useJdAnalysesQuery,
} from '../features/jd/hooks';
import { useJobsQuery } from '../features/jobs/hooks';
import { structuredResultToJD } from '../features/jd/mappers';
import type { DashboardItem, JobAnalysisResult, ATSProfile } from '../api/types';
import type { JDAnalysis } from '../types/jobcraft';
import type { QueryClient } from '@tanstack/react-query';

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

const DASH_JOB: DashboardItem = {
  id: 1,
  position: 'AI 产品经理',
  company: '字节跳动',
  status: 'APPLIED',
  job_analysis_id: 12,
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

const STRUCTURED_ATS: ATSProfile = {
  job_title: 'AI 产品经理',
  department: null,
  location: null,
  salary: '面议',
  years_of_experience: null,
  education: null,
  required_skills: ['数据分析'],
  preferred_skills: ['英语'],
  responsibilities: ['负责策略制定'],
  key_metrics: ['转化率'],
  culture_keywords: [],
  dimension_requirements: [],
  raw_summary: '',
};

function buildStructuredResult() {
  return {
    ats_profile: {
      ...STRUCTURED_ATS,
      subtext_decoded: [{ surface_requirement: '强自驱', hidden_meaning: '能主动推进', key_ability: '结果导向' }],
    } as unknown as ATSProfile,
    raw: {},
    company: '字节跳动',
    position: 'AI 产品经理',
  };
}

const JdCacheCount = () => {
  const { data: jdAnalyses = [] } = useJdAnalysesQuery();
  return <span data-testid="jd-cache-count">{jdAnalyses.length}</span>;
};

const JobsCacheState = () => {
  const { data: jobs = [] } = useJobsQuery();
  const detail = jobs[0]
    ? `${jobs.length}|${jobs[0].jdAnalysisId}|${jobs[0].matchScore}`
    : '0|';
  return <span data-testid="jobs-cache-state">{detail}</span>;
};

const DeleteHarness = () => {
  const del = useDeleteJdAnalysisMutation();
  return <button onClick={() => del.mutate('sub-55')}>删除 sub</button>;
};

const StructuredCreateHarness = ({ jobId }: { jobId?: string }) => {
  const create = useCreateStructuredJdAnalysisMutation();
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  return (
    <div>
      <button
        onClick={async () => {
          setResult('');
          setError('');
          try {
            const a = await create.mutateAsync({
              company: '字节跳动',
              role: 'AI 产品经理',
              duties: ['负责策略制定'],
              requirements: [{ text: '3年经验', tag: 'required' }],
              jobId,
            });
            setResult(`${a.id}|${a.matchScore}|${a.verdictSummary}|${a.subtextAnalysis.length}`);
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        发起结构化分析
      </button>
      <span data-testid="structured-result">{result}</span>
      <span data-testid="structured-error">{error}</span>
    </div>
  );
};

const UnstructuredCreateHarness = ({ jobId }: { jobId?: string }) => {
  const create = useCreateJdAnalysisMutation();
  const [id, setId] = useState('');
  return (
    <div>
      <button
        onClick={() => {
          create.mutate(
            { company: '字节跳动', role: 'AI 产品经理', rawText: '待补充JD内容', jobId },
            { onSuccess: (a: JDAnalysis) => setId(a.id) },
          );
        }}
      >
        发起原始文本分析
      </button>
      <span data-testid="unstructured-id">{id}</span>
    </div>
  );
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
    analyses: [DETAIL_A, DETAIL_B],
  });
  job.deleteSubmission.mockResolvedValue(undefined);
  job.analyzeStructuredJd.mockResolvedValue(buildStructuredResult());
  job.analyzeJob.mockResolvedValue(buildResult());
  tasks.runTaskOrSync.mockImplementation(async (_t: string, _p: unknown, fallback: () => unknown) => fallback());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useJdAnalysesQuery 迁移视图', () => {
  it('JDAnalysisCenterView 从 query 渲染历史列表并支持搜索过滤', async () => {
    renderWithProviders(
      <>
        <JDAnalysisCenterView />
        <JdCacheCount />
      </>,
    );

    fireEvent.click(screen.getByText(/历史研判报告/));

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText('历史研判报告 (2)')).toBeInTheDocument();
    expect(job.listJobAnalyses).toHaveBeenCalledWith(1);
    expect(job.getJobAnalysis).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '腾讯' },
    });
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '不存在的公司xyz' },
    });
    expect(await screen.findByText('未找到符合条件的研判记录')).toBeInTheDocument();

    await screen.findByTestId('jd-cache-count');
    expect(screen.getByTestId('jd-cache-count').textContent).toBe('2');
  });

  it('delete：cache 过滤，真实分析 id 不发后端删除请求', async () => {
    renderWithProviders(
      <>
        <JDAnalysisCenterView />
        <JdCacheCount />
      </>,
    );

    fireEvent.click(screen.getByText(/历史研判报告/));
    await screen.findByText('字节跳动');
    expect(screen.getByTestId('jd-cache-count').textContent).toBe('2');

    fireEvent.click(screen.getAllByTitle('删除记录')[0]);

    expect(await screen.findByText('历史研判报告 (1)')).toBeInTheDocument();
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(job.deleteSubmission).not.toHaveBeenCalled();
    expect(screen.getByTestId('jd-cache-count').textContent).toBe('1');
  });
});

describe('useDeleteJdAnalysisMutation', () => {
  it('sub-{number} id 触发后端 deleteSubmission 并更新 cache', async () => {
    renderWithProviders(
      <>
        <DeleteHarness />
        <JdCacheCount />
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

describe('JDReportDetailView 结构化分析降级展示', () => {
  const STRUCT_ANALYSIS = structuredResultToJD(
    buildStructuredResult(),
    {
      id: 'jd-1700000000000',
      company: '字节跳动',
      role: 'AI 产品经理',
      rawText: '1. 负责策略制定\n1. （硬性门槛）3年经验',
    },
  );

  /** 预置结构化分析（合成 id + matchScore 0）到查询缓存，避免 useJdAnalysesQuery 重新拉取覆盖。 */
  function seedStructuredClient(): QueryClient {
    const client = createTestQueryClient();
    client.setQueryDefaults(['jdAnalyses'], { staleTime: Infinity });
    client.setQueryData(['jdAnalyses'], [STRUCT_ANALYSIS]);
    return client;
  }

  it('matchScore 空 → 结论卡片降级：待分析 label、— 分、无 MATCH、无金色满星', async () => {
    renderWithProviders(
      <JDReportDetailView analysisId="jd-1700000000000" />,
      { queryClient: seedStructuredClient() },
    );

    expect(await screen.findByText('AI 岗位匹配结论')).toBeInTheDocument();
    expect(screen.getAllByText('待分析').length).toBeGreaterThan(0);
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    expect(screen.queryByText('MATCH')).not.toBeInTheDocument();
    expect(screen.getByTestId('verdict-stars').dataset.filled).toBe('false');
  });

  it('结构化分析匹配区块降级占位、非匹配区块（暗话）正常展示', async () => {
    renderWithProviders(
      <JDReportDetailView analysisId="jd-1700000000000" />,
      { queryClient: seedStructuredClient() },
    );

    expect(await screen.findByText(/暂无能力匹配数据/)).toBeInTheDocument();
    expect(screen.getByText(/暂无推荐经历数据/)).toBeInTheDocument();
    expect(screen.getByText('强自驱')).toBeInTheDocument();
  });

  it('点击「立即去定制简历」不发 saveResume（合成 id 无真实 job_analysis_id），提示先完整分析', async () => {
    renderWithProviders(
      <>
        <JDReportDetailView analysisId="jd-1700000000000" />
        <ToastContainer />
      </>,
      { queryClient: seedStructuredClient() },
    );

    fireEvent.click(await screen.findByText('立即去定制简历'));

    expect(await screen.findByText('暂无法生成简历')).toBeInTheDocument();
    expect(job.saveResume).not.toHaveBeenCalled();
  });

  it('有真实 matchScore 的分析仍显示 MATCH 标签与金色满星', async () => {
    renderWithProviders(<JDReportDetailView analysisId="13" />);

    expect(await screen.findByText('策略产品经理')).toBeInTheDocument();
    expect(screen.getByText('MATCH')).toBeInTheDocument();
    expect(screen.getByTestId('verdict-stars').dataset.filled).toBe('true');
  });
});

describe('JD create 迁移（features/jd/hooks）', () => {
  it('结构化分析：无 jobId 时自动创建岗位，runTaskOrSync 降级 analyzeStructuredJd，双写 jd + jobs cache', async () => {
    renderWithProviders(
      <>
        <StructuredCreateHarness />
        <JdCacheCount />
        <JobsCacheState />
      </>,
    );

    fireEvent.click(await screen.findByText('发起结构化分析'));

    await waitFor(() => expect(screen.getByTestId('structured-result').textContent).toMatch(/^jd-\d+\|0\|结构化分析完成\|1$/));

    expect(tasks.runTaskOrSync).toHaveBeenCalledWith(
      'jd_analyze_structured',
      expect.objectContaining({ user_id: 1, duties: ['负责策略制定'] }),
      expect.any(Function),
      expect.objectContaining({ timeout: 120_000 }),
    );
    expect(job.analyzeStructuredJd).toHaveBeenCalledWith({
      company: '字节跳动',
      position: 'AI 产品经理',
      duties: ['负责策略制定'],
      requirements: [{ text: '3年经验', tag: 'required' }],
    });

    expect(screen.getByTestId('jd-cache-count').textContent).toBe('3');
    expect(screen.getByTestId('jobs-cache-state').textContent).toMatch(/^1\|jd-\d+\|0$/);
  });

  it('结构化分析：提供 jobId 时复用已有岗位并回填 jdAnalysisId（合成 id）', async () => {
    job.getDashboard.mockResolvedValue({ submissions: [DASH_JOB] });

    renderWithProviders(
      <>
        <StructuredCreateHarness jobId="1" />
        <JdCacheCount />
        <JobsCacheState />
      </>,
    );

    await waitFor(() => expect(screen.getByTestId('jobs-cache-state').textContent).toBe('1|12|0'));
    fireEvent.click(screen.getByText('发起结构化分析'));

    await waitFor(() => expect(screen.getByTestId('structured-result').textContent).toMatch(/^jd-\d+\|0\|结构化分析完成\|1$/));
    expect(screen.getByTestId('jobs-cache-state').textContent).toMatch(/^1\|jd-\d+\|0$/);
    expect(screen.getByTestId('jd-cache-count').textContent).toBe('3');
  });

  it('原始文本分析（NewInterviewModal 路径）：复用已有岗位，回填真实 job_analysis_id 与 matchScore', async () => {
    job.getDashboard.mockResolvedValue({ submissions: [DASH_JOB] });

    renderWithProviders(
      <>
        <UnstructuredCreateHarness jobId="1" />
        <JdCacheCount />
        <JobsCacheState />
      </>,
    );

    await waitFor(() => expect(screen.getByTestId('jobs-cache-state').textContent).toBe('1|12|0'));
    fireEvent.click(screen.getByText('发起原始文本分析'));

    await waitFor(() => expect(screen.getByTestId('unstructured-id').textContent).toBe('12'));

    expect(tasks.runTaskOrSync).toHaveBeenCalledWith(
      'resume_generate',
      expect.objectContaining({ user_id: 1, jd_text: '待补充JD内容', card_ids: [] }),
      expect.any(Function),
      expect.objectContaining({ timeout: 180_000 }),
    );
    expect(job.analyzeJob).toHaveBeenCalledWith({
      position: 'AI 产品经理',
      company: '字节跳动',
      jd_text: '待补充JD内容',
      card_ids: [],
    });

    expect(screen.getByTestId('jobs-cache-state').textContent).toBe('1|12|60');
    expect(screen.getByTestId('jd-cache-count').textContent).toBe('3');
  });

  it('结构化分析失败时 mutateAsync reject（不再 fire-and-forget）', async () => {
    job.analyzeStructuredJd.mockRejectedValue(new Error('任务超时'));

    renderWithProviders(<StructuredCreateHarness />);

    fireEvent.click(await screen.findByText('发起结构化分析'));

    await waitFor(() => expect(screen.getByTestId('structured-error').textContent).toBe('任务超时'));
  });
});
