import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useEffect, useRef, useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';
import { renderWithProviders } from './test-utils';
import { InterviewReviewCenterView } from '../components/review/InterviewReviewCenterView';
import { useInterviewsQuery } from '../features/interview/hooks';
import { useJobsQuery } from '../features/jobs/hooks';
import { useExperiencesQuery } from '../features/experiences/hooks';
import { INTERVIEWS_QUERY_KEY } from '../features/interview/mappers';
import { JOBS_QUERY_KEY } from '../features/jobs/mappers';
import { EXPERIENCES_QUERY_KEY } from '../features/experiences/mappers';
import { prepRecordToInterview } from '../features/interview/mappers';
import { cardToExperience } from '../features/experiences/mappers';
import {
  useApplyReviewFeedbackMutation,
  useCreateInterviewReviewMutation,
} from '../features/review/hooks';
import type { InterviewPrepRecord, InterviewReviewResult, ExperienceCard } from '../api/types';
import type { Experience, Interview, InterviewReview, Job } from '../types/jobcraft';

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
  createInterviewReview: vi.fn(),
  analyzeInterviewReview: vi.fn(),
}));

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
  updateCard: vi.fn(),
  listCardVersions: vi.fn(),
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

const RECORD_YUAN: InterviewPrepRecord = {
  id: 7,
  job_analysis_id: 12,
  company: '字节跳动',
  position: 'AI 产品经理',
  submission_id: 1,
  round_type: '技术面',
  duration: '45分钟',
  elevator_pitch: '自我介绍',
  dimension_questions: [],
  full_version: '完整方案',
  html_content: '<div>方案</div>',
  created_at: '2026-09-18T08:30:00',
  company_research: null,
};

const RECORD_TX: InterviewPrepRecord = {
  id: 8,
  job_analysis_id: 13,
  company: '腾讯',
  position: 'AI 产品经理',
  submission_id: 1,
  round_type: '业务面',
  duration: '30分钟',
  elevator_pitch: '自我介绍',
  dimension_questions: [],
  full_version: '完整方案',
  html_content: '<div>方案</div>',
  created_at: '2026-09-18T09:00:00',
  company_research: null,
};

const CARD_A: ExperienceCard = {
  id: 7,
  user_id: 1,
  title: '端侧大模型量化评测',
  raw_text: '移动端端侧生成式体验的量产方案。',
  tags: ['端侧大模型'],
  ai_structured: null,
  company: '未来智能实验室',
  role: 'AI 产品经理',
  period: '2025.01 - 2025.08',
  source: 'manual',
  card_type: 'work',
  version: 1,
  is_active: true,
  is_confirmed: true,
};

const REVIEW: InterviewReview = {
  id: 'rev-1',
  interviewId: 'prep-7',
  company: '字节跳动',
  role: 'AI 产品经理',
  roundName: '面试准备 · 技术面',
  reviewDate: '2026-09-19',
  overallScore: 85,
  passProbability: '通过概率较高',
  totalQACount: 1,
  highlights: ['指标拆解清晰'],
  drawbacks: ['商业闭环考虑不足'],
  competencies: [{ name: '岗位匹配度', score: 85, benchmark: 80 }],
  coreProblems: ['商业闭环考虑不足'],
  aiDiagnosis: '整体表现良好',
  qaList: [],
  experienceFeedbacks: [
    {
      experienceId: '7',
      experienceTitle: '端侧大模型量化评测',
      discoveredIssues: ['缺选型对比'],
      suggestions: ['补充量化选型对比'],
      currentVersion: 'V1',
      proposedVersion: 'V2',
      proposedChanges: [
        { field: 'problem', from: '旧职责', to: '新职责（含选型对比）' },
      ],
      applied: false,
    },
  ],
};

const REVIEW_SUGG: InterviewReview = {
  ...REVIEW,
  id: 'rev-2',
  experienceFeedbacks: [
    {
      ...REVIEW.experienceFeedbacks![0],
      proposedChanges: [],
    },
  ],
};

const buildInt = (record: InterviewPrepRecord, review?: InterviewReview): Interview => ({
  ...prepRecordToInterview(record),
  review,
});

const INT_YUAN = buildInt(RECORD_YUAN, REVIEW);
const INT_TX_PREP = buildInt(RECORD_TX);

const EXP_V1: Experience = {
  ...cardToExperience(CARD_A),
  problem: '旧职责',
  actions: ['旧动作A', '旧动作B'],
  versionHistory: [],
};

const JOB_12: Job = {
  id: '12',
  company: '字节跳动',
  role: 'AI 产品经理',
  salaryRange: '30-60K',
  status: 'preparing',
  matchScore: 85,
  applyDate: '2026-09-18',
  lastUpdated: '2026-09-18',
  currentStage: '面试准备',
  nextAction: '复盘',
  steps: {
    jdAnalysis: true,
    expMatched: true,
    customResume: true,
    applied: true,
    prepStage: 'in_progress',
    reviewStage: 'pending',
  },
  interviewIds: ['prep-7'],
} as unknown as Job;

const ANALYSIS: InterviewReviewResult = {
  record_id: 101,
  user_id: 1,
  title: '字节跳动 AI 产品经理技术面复盘',
  company: '字节跳动',
  position: 'AI 产品经理',
  round_type: '技术面',
  overall_score: 85,
  summary: '整体表现良好，指标拆解清晰',
  strengths: ['指标拆解清晰'],
  weaknesses: ['商业闭环考虑不足'],
  action_items: ['补充选型对比'],
  questions: [
    {
      sequence: 1,
      start_time: '0.1',
      speaker: '面试官',
      question_text: '如何设计 RAG 评测体系？',
      dimension: '技术深度',
      level: '深挖',
      intent: '考察评测体系设计',
      expected_answer: '拆分维度与指标',
      my_answer: '拆分评测维度，离线指标 + 线上 A/B',
      score: 85,
      feedback: ['缺商业闭环量化'],
      suggestions: ['补充选型对比'],
      related_card_id: null,
      related_card_title: null,
    },
  ],
  created_at: '2026-09-19',
};

interface SeedProps {
  interviews: Interview[];
  experiences: Experience[];
  jobs?: Job[];
}

// 等 provider 初始 load（interviews / experiences / jobs 各自查询 resolve，均为推迟到 macrotask
// 之后的异步写入）完成后 seed 一次 cache，让 review 读/写路径拿到带 review 的数据。
// 只 seed 一次：之后 mutation 对 cache 的写入不会被覆盖。
const Seeder = ({ interviews, experiences, jobs = [] }: SeedProps) => {
  const queryClient = useQueryClient();
  const { data: ivData } = useInterviewsQuery();
  const { data: expData } = useExperiencesQuery();
  const { data: jobData } = useJobsQuery();
  const onceRef = useRef(false);

  const resolved =
    ivData !== undefined && expData !== undefined && jobData !== undefined;

  useEffect(() => {
    if (onceRef.current || !resolved) return;
    const t = setTimeout(() => {
      onceRef.current = true;
      queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], interviews);
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], experiences);
      queryClient.setQueryData([...JOBS_QUERY_KEY], jobs);
    }, 0);
    return () => clearTimeout(t);
  }, [resolved, queryClient, interviews, experiences, jobs]);

  return null;
};

const CacheReader = () => {
  const { data: interviews = [] } = useInterviewsQuery();
  const { data: exp = [] } = useExperiencesQuery();
  const { data: jobData = [] } = useJobsQuery();
  const iv = interviews.find((i) => i.id === 'prep-7');
  const fb = iv?.review?.experienceFeedbacks?.[0];
  const exp0 = exp[0];
  return (
    <>
      <span data-testid="cache-status">{iv?.status ?? ''}</span>
      <span data-testid="cache-score">{iv?.review?.overallScore ?? ''}</span>
      <span data-testid="cache-applied">{String(fb?.applied ?? '')}</span>
      <span data-testid="cache-review-stage">
        {jobData.find((j) => j.id === '12')?.steps?.reviewStage ?? ''}
      </span>
      <span data-testid="cache-exp-version">{exp0?.currentVersion ?? ''}</span>
      <span data-testid="cache-exp-problem">{exp0?.problem ?? ''}</span>
      <span data-testid="cache-exp-action">{exp0?.actions?.[0] ?? ''}</span>
      <span data-testid="cache-exp-hist">{exp0?.versionHistory?.length ?? ''}</span>
    </>
  );
};

const CreateHarness = ({ interviewId = 'prep-7' }: { interviewId?: string }) => {
  const createReview = useCreateInterviewReviewMutation();
  const [created, setCreated] = useState('');
  const [error, setError] = useState('');
  return (
    <div>
      <button
        onClick={() => {
          setCreated('');
          setError('');
          createReview
            .mutateAsync({ interviewId, transcript: '面试逐字稿...' })
            .then((r) => setCreated(r.interviewId))
            .catch((e: unknown) => setError((e as Error).message));
        }}
      >
        生成复盘
      </button>
      <span data-testid="created-id">{created}</span>
      <span data-testid="create-error">{error}</span>
    </div>
  );
};

const ApplyHarness = ({ interviews }: { interviews: Interview[] }) => {
  const applyFeedback = useApplyReviewFeedbackMutation();
  const [error, setError] = useState('');
  return (
    <div>
      <button
        onClick={() => {
          setError('');
          applyFeedback
            .mutateAsync({ interviewId: 'prep-7', feedbackIndex: 0 })
            .catch((e: unknown) => setError((e as Error).message));
        }}
      >
        应用反馈
      </button>
      <span data-testid="apply-error">{error}</span>
      <CacheReader />
    </div>
  );
};

const seedProps = {
  interviews: [INT_YUAN, INT_TX_PREP],
  experiences: [EXP_V1],
  jobs: [JOB_12],
};

// Seeder 的 seed 是 defer 到 macrotask 的；交互前先等 cache 可见，避免竞态。
const waitForSeed = () =>
  waitFor(() => expect(screen.getByTestId('cache-score').textContent).toBe('85'));

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
  experience.listCards.mockResolvedValue([]);
  // EXP-P1-06b：复盘反哺持久化 + 版本回流（updateCard 后 listCardVersions 返回 V2 + 2 条快照）
  experience.updateCard.mockResolvedValue(CARD_A);
  experience.listCardVersions.mockImplementation(async (cardId: number) => ({
    card_id: cardId,
    current_version: 2,
    versions: [
      {
        id: 2, card_id: cardId, version_type: 'user_edit', source_type: 'card_edit',
        source_id: 0, title: '端侧大模型量化评测', raw_text: '移动端端侧生成式体验的量产方案。',
        tags: ['端侧大模型'], note: '编辑保存 V2', created_at: '2026-09-19T10:00:00',
      },
      {
        id: 1, card_id: cardId, version_type: 'original', source_type: 'original',
        source_id: 0, title: '端侧大模型量化评测', raw_text: '移动端端侧生成式体验的量产方案。',
        tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-18T10:00:00',
      },
    ],
  }));
  interview.listInterviewPreps.mockResolvedValue({ records: [] });
  interview.createInterviewReview.mockResolvedValue({
    record_id: 101,
    status: 'pending',
    qa_pairs: [{ sequence: 1, speaker: '面试官', question: '如何设计 RAG 评测体系？' }],
    qa_pair_count: 1,
    dialogue: '',
    speaker_count: 1,
    role_counts: ['interviewer', 'candidate'],
  });
  interview.analyzeInterviewReview.mockResolvedValue(ANALYSIS);
  tasks.runTaskOrSync.mockImplementation(async (_t: unknown, _p: unknown, fallback: () => unknown) =>
    fallback(),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useCreateInterviewReviewMutation（生成复盘）', () => {
  it('create + analyze 走 fallback：双写 INTERVIEWS/JOBS cache', async () => {
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    await waitForSeed();
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() => expect(screen.getByTestId('created-id').textContent).toBe('prep-7'));

    expect(auth.getCurrentUser).toHaveBeenCalled();
    expect(interview.createInterviewReview).toHaveBeenCalledWith({
      user_id: 1,
      company: '字节跳动',
      position: 'AI 产品经理',
      round_type: 'tech',
      raw_text: '面试逐字稿...',
    });
    expect(tasks.runTaskOrSync).toHaveBeenCalledWith(
      'interview_review_analyze',
      { user_id: 1, record_id: 101, selected_sequences: [1] },
      expect.any(Function),
      expect.objectContaining({ timeout: 180_000 }),
    );
    expect(interview.analyzeInterviewReview).toHaveBeenCalledWith(101, [1], 1);

    // INTERVIEWS cache：status completed + review（真实 score 85）
    expect(screen.getByTestId('cache-status').textContent).toBe('completed');
    expect(screen.getByTestId('cache-score').textContent).toBe('85');
    // 跨域 JOBS cache：steps.reviewStage/prepStage done
    expect(screen.getByTestId('cache-review-stage').textContent).toBe('done');
  });

  it('分析失败时容忍：保留 base patch，仍写入 cache 且不抛错', async () => {
    tasks.runTaskOrSync.mockRejectedValue(new Error('analyze boom'));

    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    await waitForSeed();
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() => expect(screen.getByTestId('created-id').textContent).toBe('prep-7'));
    // 1 道题 → Math.round((qa_pair_count || 4) * 10) = 10
    expect(screen.getByTestId('cache-score').textContent).toBe('10');
    expect(screen.getByTestId('cache-status').textContent).toBe('completed');
    expect(screen.getByTestId('create-error').textContent).toBe('');
  });

  it('INTERVIEWS cache 缺失目标面试时抛错且不触发后端', async () => {
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness interviewId="missing" />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() =>
      expect(screen.getByTestId('create-error').textContent).toContain('未找到对应的面试记录'),
    );
    expect(interview.createInterviewReview).not.toHaveBeenCalled();
    expect(tasks.runTaskOrSync).not.toHaveBeenCalled();
  });
});

describe('useApplyReviewFeedbackMutation（反哺经历资产）', () => {
  it('proposedChanges 路径：updateCard 持久化 + EXPERIENCES/INTERVIEWS cache 反哺', async () => {
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <ApplyHarness interviews={[INT_YUAN]} />
      </>,
    );

    await screen.findByText('应用反馈');
    await waitForSeed();
    fireEvent.click(screen.getByText('应用反馈'));

    // EXPERIENCES cache：字段变更 + 后端版本回流（versionHistory 来自 card_versions）
    await waitFor(() => expect(screen.getByTestId('cache-exp-version').textContent).toBe('V2'));
    // 内容已持久化到后端 + 定稿（EXP-P1-06b §34.6）
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        problem: '新职责（含选型对比）',
        actions: ['旧动作A', '旧动作B'],
        is_confirmed: true,
      }),
    );
    expect(screen.getByTestId('cache-exp-problem').textContent).toBe('新职责（含选型对比）');
    expect(screen.getByTestId('cache-exp-hist').textContent).toBe('2');
    // INTERVIEWS cache：feedback applied
    expect(screen.getByTestId('cache-applied').textContent).toBe('true');
    expect(screen.getByTestId('apply-error').textContent).toBe('');
  });

  it('proposedChanges 为空时走 suggestions 前置持久化，版本历史来自后端', async () => {
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_SUGG)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <ApplyHarness interviews={[buildInt(RECORD_YUAN, REVIEW_SUGG)]} />
      </>,
    );

    await screen.findByText('应用反馈');
    await waitForSeed();
    fireEvent.click(screen.getByText('应用反馈'));

    await waitFor(() => expect(screen.getByTestId('cache-exp-version').textContent).toBe('V2'));
    // suggestions 前置动作已持久化到后端
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        actions: ['[面试复盘升级] 补充量化选型对比', '旧动作A', '旧动作B'],
        is_confirmed: true,
      }),
    );
    expect(screen.getByTestId('cache-exp-action').textContent).toBe('[面试复盘升级] 补充量化选型对比');
    expect(screen.getByTestId('cache-exp-hist').textContent).toBe('2');
    expect(screen.getByTestId('apply-error').textContent).toBe('');
  });
});

describe('InterviewReviewCenterView 读路径', () => {
  it('从 query 渲染已复盘面试（含 review 过滤）并支持搜索', async () => {
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <InterviewReviewCenterView />
      </>,
    );

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    // 1 条带 review（INT_YUAN），1 条无（INT_TX_PREP 待复盘）：已完成 1 场 + 待复盘 1 场
    expect(screen.getAllByText('1 场')).toHaveLength(2);
    // 已复盘台账含真实得分
    expect(screen.getByText('85')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索公司、岗位或面试轮次...'), {
      target: { value: '腾讯' },
    });
    expect(screen.getByText('未找到复盘记录')).toBeInTheDocument();
  });
});