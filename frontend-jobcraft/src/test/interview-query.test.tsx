import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { InterviewPrepCenterView } from '../components/interview/InterviewPrepCenterView';
import { useCreateInterviewMutation } from '../features/interview/hooks';
import { useJobCraft } from '../context/JobCraftContext';
import type { DashboardItem, InterviewPrepRecord, InterviewPrepResult } from '../api/types';
import type { Interview } from '../types/jobcraft';

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
  listBaseResumes: vi.fn(),
  listJobAnalyses: vi.fn(),
  getJobAnalysis: vi.fn(),
}));

const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
  generateInterviewPrep: vi.fn(),
}));

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));
vi.mock('../api/interview', () => ({ ...interview }));
vi.mock('../api/tasks', () => ({ ...tasks }));
vi.mock('../api/experience', () => ({ ...experience }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const PREP_RECORD: InterviewPrepRecord = {
  id: 7,
  job_analysis_id: 12,
  company: '字节跳动',
  position: 'AI 产品经理',
  submission_id: 1,
  round_type: '技术面',
  duration: '45分钟',
  elevator_pitch: '自我介绍',
  dimension_questions: [
    {
      dimension: '技术深度',
      question: '如何设计 RAG 评测体系？',
      answer_points: ['拆分评测维度', '离线指标 + 线上 A/B'],
      card_ids: [3],
    },
  ],
  full_version: '完整方案',
  html_content: '<div>方案</div>',
  created_at: '2026-09-18T08:30:00',
  company_research: null,
};

function buildPrepResult(overrides: Partial<InterviewPrepResult> = {}): InterviewPrepResult {
  return {
    id: 55,
    job_analysis_id: 12,
    round_type: '技术面',
    duration: '45分钟',
    elevator_pitch: '自我介绍',
    dimension_questions: [
      { dimension: '技术深度', question: '如何设计 RAG 评测体系？', answer_points: ['拆分评测维度'], card_ids: [] },
    ],
    full_version: '完整方案',
    html_content: '<div>方案</div>',
    created_at: '2026-09-18T09:00:00',
    company_research: null,
    ...overrides,
  };
}

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
  prep_count: 0,
  review_count: 0,
  created_at: '2026-09-18',
  updated_at: '2026-09-18',
};

const MirrorCount = () => {
  const { interviews } = useJobCraft();
  return <span data-testid="iv-mirror-count">{interviews.length}</span>;
};

const JobMirror = () => {
  const { jobs } = useJobCraft();
  return <span data-testid="job-interview-ids">{jobs.map((j) => j.interviewIds.join(',')).join(';')}</span>;
};

const CreateHarness = ({ jobId = '1' }: { jobId?: string }) => {
  const { syncInterviews, syncJobs } = useJobCraft();
  const createInterview = useCreateInterviewMutation({ onSync: syncInterviews, onSyncJobs: syncJobs });
  const [created, setCreated] = useState<Interview | null>(null);
  const [error, setError] = useState('');
  return (
    <div>
      <button
        onClick={() => {
          setCreated(null);
          setError('');
          createInterview
            .mutateAsync({
              jobId,
              company: '字节跳动',
              role: 'AI 产品经理',
              roundNumber: 1,
              roundName: '技术面',
              roundType: 'tech',
              time: '2026-09-20 10:00',
              format: 'video',
              supplementNotes: '',
            })
            .then(setCreated)
            .catch((e: unknown) => setError((e as Error).message));
        }}
      >
        创建面试
      </button>
      <span data-testid="created-id">{created?.id || ''}</span>
      <span data-testid="create-error">{error}</span>
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
  job.listJobAnalyses.mockResolvedValue({ analyses: [] });
  job.getJobAnalysis.mockResolvedValue(null);
  experience.listCards.mockResolvedValue({ cards: [] });
  interview.listInterviewPreps.mockResolvedValue({ records: [] });
  interview.generateInterviewPrep.mockResolvedValue(buildPrepResult());
  tasks.runTaskOrSync.mockImplementation(async (_t, _p, fallback) => fallback());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useInterviewsQuery 迁移视图', () => {
  it('InterviewPrepCenterView 从 query 渲染面试准备记录并支持搜索过滤', async () => {
    interview.listInterviewPreps.mockResolvedValue({ records: [PREP_RECORD] });

    renderWithProviders(
      <>
        <InterviewPrepCenterView onOpenMockInterview={vi.fn()} onOpenNewInterview={vi.fn()} />
        <MirrorCount />
      </>,
    );

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    expect(screen.getByText('AI 产品经理')).toBeInTheDocument();
    expect(screen.getByText('全部面试 (1)')).toBeInTheDocument();
    expect(interview.listInterviewPreps).toHaveBeenCalledWith(1);

    fireEvent.change(screen.getByPlaceholderText('搜索公司、岗位或面试轮次...'), {
      target: { value: '腾讯' },
    });
    expect(await screen.findByText('未找到符合条件的面试记录')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索公司、岗位或面试轮次...'), {
      target: { value: '字节' },
    });
    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('iv-mirror-count').textContent).toBe('1'));
  });
});

describe('useCreateInterviewMutation', () => {
  it('从 JOBS cache 解析 job_analysis_id，runTaskOrSync 降级 generateInterviewPrep，双写 interviews + jobs 镜像', async () => {
    job.getDashboard.mockResolvedValue({ submissions: [DASH_JOB] });

    renderWithProviders(
      <>
        <CreateHarness />
        <MirrorCount />
        <JobMirror />
      </>,
    );

    await screen.findByText('创建面试');
    fireEvent.click(screen.getByText('创建面试'));

    await waitFor(() => expect(screen.getByTestId('created-id').textContent).toBe('prep-55'));

    expect(tasks.runTaskOrSync).toHaveBeenCalledWith(
      'interview_prep',
      { user_id: 1, job_analysis_id: 12, round_type: '技术面', card_ids: [] },
      expect.any(Function),
      expect.objectContaining({ timeout: 180_000 }),
    );
    expect(interview.generateInterviewPrep).toHaveBeenCalledWith(12, { round_type: '技术面', card_ids: [] });

    expect(screen.getByTestId('iv-mirror-count').textContent).toBe('1');
    expect(screen.getByTestId('job-interview-ids').textContent).toBe('prep-55');
  });

  it('JOBS cache 缺失 jdAnalysisId 时抛错且不触发任务服务', async () => {
    renderWithProviders(
      <>
        <CreateHarness jobId="99" />
        <JobMirror />
      </>,
    );

    await screen.findByText('创建面试');
    fireEvent.click(screen.getByText('创建面试'));

    await waitFor(() =>
      expect(screen.getByTestId('create-error').textContent).toContain('尚未完成 AI 岗位分析'),
    );
    expect(tasks.runTaskOrSync).not.toHaveBeenCalled();
    expect(interview.generateInterviewPrep).not.toHaveBeenCalled();
    expect(screen.getByTestId('job-interview-ids').textContent).toBe('');
  });
});