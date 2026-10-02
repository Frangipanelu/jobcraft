import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useEffect, useRef, useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { QueryClient, useQueryClient } from '@tanstack/react-query';
import { renderWithProviders } from './test-utils';
import { InterviewReviewCenterView } from '../components/review/InterviewReviewCenterView';
import { InterviewReviewDetailView } from '../components/review/InterviewReviewDetailView';
import { ToastContainer } from '../components/common/Toast';
import { CreateReview } from '../pages/CreateReview';
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
}));

const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
  generateInterviewPrep: vi.fn(),
  createInterviewReview: vi.fn(),
  uploadInterviewReview: vi.fn(),
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

const CreateHarness = ({
  interviewId = 'prep-7',
  args,
}: {
  interviewId?: string;
  args?: { transcript?: string; file?: File };
}) => {
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
            .mutateAsync({ interviewId, ...(args ?? { transcript: '面试逐字稿...' }) })
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

// FE-CACHE-01：mock 服务端需有状态——invalidate 触发 refetch 时必须返回反映
// 本次写入的服务端真相（dashboard review_count / cards 内容），否则乐观补丁被静态 fixture 回滚。
interface DashRow {
  id: number;
  position: string;
  company: string;
  status: string;
  job_analysis_id: number | null;
  job_id: number | null;
  has_analysis: boolean;
  card_version_count: number;
  card_count: number;
  has_resume: boolean;
  is_manual: boolean;
  delivered: boolean;
  prep_count: number;
  review_count: number;
  created_at: string | null;
  updated_at: string | null;
}
let serverSubs: DashRow[] = [];
let serverCards: ExperienceCard[] = [];

/** 复盘落库后的服务端 submission 行（id=12 → mapper 后 job.id='12'，review_count=1 → reviewStage done）。 */
const REVIEWED_ROW: DashRow = {
  id: 12,
  position: 'AI 产品经理',
  company: '字节跳动',
  status: 'ROUND_1',
  job_analysis_id: 12,
  job_id: null,
  has_analysis: true,
  card_version_count: 0,
  card_count: 1,
  has_resume: true,
  is_manual: false,
  delivered: true,
  prep_count: 1,
  review_count: 1,
  created_at: '2026-09-18T00:00:00',
  updated_at: '2026-09-19T00:00:00',
};

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  serverSubs = [];
  serverCards = [];
  job.getDashboard.mockImplementation(async () => ({ submissions: serverSubs }));
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue({ analyses: [] });
  experience.listCards.mockImplementation(async () => serverCards);
  // EXP-P1-06b：复盘反哺持久化 + 版本回流（updateCard 后 listCardVersions 返回 V2 + 2 条快照）
  // T-M1-2：currentVersion 只来自 GET /cards 的 version 列 → mock 需模拟后端
  // updateCard 同事务 version+1（否则 invalidate refetch 后回落 V1）。
  experience.updateCard.mockImplementation(
    async (cardId: number, payload: Partial<ExperienceCard>) => {
      const card = serverCards.find((c) => c.id === cardId);
      if (card) {
        Object.assign(card, payload);
        card.version = (card.version ?? 1) + 1;
      }
      return card;
    },
  );
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
  const createResult = {
    record_id: 101,
    status: 'pending',
    qa_pairs: [{ sequence: 1, speaker: '面试官', question: '如何设计 RAG 评测体系？' }],
    qa_pair_count: 1,
    dialogue: '',
    speaker_count: 1,
    role_counts: ['interviewer', 'candidate'],
  };
  interview.createInterviewReview.mockImplementation(async () => {
    serverSubs = [REVIEWED_ROW];
    return createResult;
  });
  interview.uploadInterviewReview.mockImplementation(async () => {
    serverSubs = [REVIEWED_ROW];
    return createResult;
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

  it('FE-UPLOAD-01：file 走真实 multipart uploadInterviewReview，不落 JSON create', async () => {
    const file = new File(['面试逐字稿...'], '面试速记.txt', { type: 'text/plain' });
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness args={{ file }} />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    await waitForSeed();
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() => expect(screen.getByTestId('created-id').textContent).toBe('prep-7'));
    expect(interview.uploadInterviewReview).toHaveBeenCalledWith(
      file,
      {
        user_id: 1,
        company: '字节跳动',
        position: 'AI 产品经理',
        round_type: 'tech',
      },
    );
    expect(interview.createInterviewReview).not.toHaveBeenCalled();
    expect(screen.getByTestId('cache-status').textContent).toBe('completed');
  });

  it('FE-UPLOAD-01：file 与 transcript 皆缺时抛错，不提交空记录', async () => {
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness args={{}} />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    await waitForSeed();
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() =>
      expect(screen.getByTestId('create-error').textContent).toContain(
        '请粘贴面试速记文本或上传转录文档',
      ),
    );
    expect(interview.createInterviewReview).not.toHaveBeenCalled();
    expect(interview.uploadInterviewReview).not.toHaveBeenCalled();
    expect(tasks.runTaskOrSync).not.toHaveBeenCalled();
  });

  it('FE-UPLOAD-01：上传端点失败（断网）时向上抛，不产生成功结果', async () => {
    interview.uploadInterviewReview.mockRejectedValue(new Error('Failed to fetch'));
    const file = new File(['x'], '速记.txt', { type: 'text/plain' });
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <CreateHarness args={{ file }} />
        <CacheReader />
      </>,
    );

    await screen.findByText('生成复盘');
    await waitForSeed();
    fireEvent.click(screen.getByText('生成复盘'));

    await waitFor(() =>
      expect(screen.getByTestId('create-error').textContent).toContain('Failed to fetch'),
    );
    expect(screen.getByTestId('created-id').textContent).toBe('');
    expect(tasks.runTaskOrSync).not.toHaveBeenCalled();
  });
});

describe('useApplyReviewFeedbackMutation（反哺经历资产）', () => {
  beforeEach(() => {
    // 反哺的 updateCard 写入需在服务端可回读：listCards 返回有状态卡片，
    // EXPERIENCES invalidate refetch 后内容/版本与乐观补丁一致。
    serverCards = [{ ...CARD_A }];
  });

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
    // 内容已持久化到后端，且 P10-b-lite 轻闸门：只追加新版本、不强制定稿
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        problem: '新职责（含选型对比）',
        actions: ['旧动作A', '旧动作B'],
      }),
    );
    expect(experience.updateCard).not.toHaveBeenCalledWith(
      7,
      expect.objectContaining({ is_confirmed: true })
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
    // suggestions 前置动作已持久化到后端（P10-b-lite：不再强制定稿）
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        actions: ['[面试复盘升级] 补充量化选型对比', '旧动作A', '旧动作B'],
      }),
    );
    expect(experience.updateCard).not.toHaveBeenCalledWith(
      7,
      expect.objectContaining({ is_confirmed: true })
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

describe('P10-b-lite 轻闸门：复盘反哺写回前需二次确认', () => {
  beforeEach(() => {
    auth.getCurrentUser.mockResolvedValue(AUTH_USER);
    job.getDashboard.mockResolvedValue({ submissions: [] });
    interview.listInterviewPreps.mockResolvedValue([RECORD_YUAN, RECORD_TX]);
    experience.listCards.mockResolvedValue([CARD_A]);
    experience.updateCard.mockResolvedValue(CARD_A);
    experience.listCardVersions.mockResolvedValue({
      card_id: 7,
      current_version: 2,
      versions: [
        {
          id: 3,
          card_id: 7,
          version: 1,
          content: '旧内容',
          version_type: 'original',
          source_type: 'experience',
          source_id: 7,
          note: null,
          created_at: '2026-09-18',
        },
      ],
    });
  });

  // 带 qaList（relatedExperienceId 命中经历卡 7）→ 渲染反哺入口
  const REVIEW_QA: InterviewReview = {
    ...REVIEW,
    qaList: [
      {
        id: 'qa-1',
        qIndex: 1,
        question: '介绍端侧量化方案',
        candidateAnswer: '答题内容',
        interviewerIntent: { mainPoints: ['技术深度'], importanceStars: 4, productAbilityStars: 3, techDepthStars: 5 },
        answerAnalysis: { completeness: 80, structure: 75, persuasiveness: 70, jobRelevance: 85 },
        identifiedIssues: ['缺选型对比'],
        suggestionAdvice: '补充量化对比',
        relatedExperienceId: '7',
      },
    ],
  };

  const renderDetail = () =>
    renderWithProviders(
      <>
        <Seeder interviews={[buildInt(RECORD_YUAN, REVIEW_QA)]} experiences={[EXP_V1]} jobs={[JOB_12]} />
        <InterviewReviewDetailView interviewId="prep-7" />
      </>,
    );
  it('首次点击仅进入确认态，不触发写回', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));

    // 确认态出现（说明追加新版本 + 保留历史），且不写回
    expect(await screen.findByText('确认写入')).toBeInTheDocument();
    expect(screen.getByText(/保留历史/)).toBeInTheDocument();
    expect(experience.updateCard).not.toHaveBeenCalled();
  });

  it('二次点击确认后才写回，且不强制定稿', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));
    fireEvent.click(await screen.findByText('确认写入'));

    await waitFor(() => expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ problem: '新职责（含选型对比）' }),
    ));
    expect(experience.updateCard).not.toHaveBeenCalledWith(
      7,
      expect.objectContaining({ is_confirmed: true })
    );
  });

  it('确认态点取消则不写回', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));
    fireEvent.click(await screen.findByText('取消'));

    await waitFor(() => expect(screen.getByText('沉淀至经历库')).toBeInTheDocument());
    expect(experience.updateCard).not.toHaveBeenCalled();
  });
});

describe('FE-UPLOAD-01 CreateReview 上传路径（非法文件/缺文件不得成功）', () => {
  const createSeededQueryClient = () => {
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: Infinity },
        mutations: { retry: false },
      },
    });
    qc.setQueryData([...JOBS_QUERY_KEY], [JOB_12]);
    qc.setQueryData([...INTERVIEWS_QUERY_KEY], [INT_YUAN]);
    return qc;
  };

  /** 进入向导第 3 步「上传记录」。 */
  const gotoUploadStep = async () => {
    renderWithProviders(
      <>
        <CreateReview />
        <ToastContainer />
      </>,
      { queryClient: createSeededQueryClient() },
    );
    await screen.findByText('步骤 1: 关联岗位');
    fireEvent.click(screen.getByText('下一步'));
    await screen.findByText('步骤 2: 关联面试');
    fireEvent.click(screen.getByText('下一步'));
    await screen.findByText('步骤 3: 上传记录');
  };

  it('非法文件拖入 → 报错 toast、不选中、不触发上传接口', async () => {
    await gotoUploadStep();
    fireEvent.click(screen.getByText('上传转录文档'));

    const zone = screen.getByText('选择本地文件').closest('div') as HTMLElement;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['x'], '录音.m4a', { type: 'audio/mp4' })] },
    });

    expect(await screen.findByText('文件无法导入')).toBeInTheDocument();
    expect(screen.getByText(/不支持「\.m4a」格式/)).toBeInTheDocument();
    expect(screen.queryByText(/已选择：录音\.m4a/)).not.toBeInTheDocument();
    expect(interview.uploadInterviewReview).not.toHaveBeenCalled();
    expect(interview.createInterviewReview).not.toHaveBeenCalled();
  });

  it('合法文件仅选中（真实校验通过，不伪造成功 toast）', async () => {
    await gotoUploadStep();
    fireEvent.click(screen.getByText('上传转录文档'));

    const zone = screen.getByText('选择本地文件').closest('div') as HTMLElement;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['面试内容'], '速记.txt', { type: 'text/plain' })] },
    });

    expect(await screen.findByText('已选择：速记.txt')).toBeInTheDocument();
    expect(screen.queryByText('文件无法导入')).not.toBeInTheDocument();
    expect(interview.uploadInterviewReview).not.toHaveBeenCalled();
  });

  it('file 模式未选文件点开始 → 提示选择转录文档，不进入分析', async () => {
    await gotoUploadStep();
    fireEvent.click(screen.getByText('上传转录文档'));
    fireEvent.click(screen.getByText('开始 AI 智能复盘研判'));

    expect(await screen.findByText('请选择转录文档')).toBeInTheDocument();
    expect(screen.queryByText('AI 正在生成复盘报告')).not.toBeInTheDocument();
    expect(interview.uploadInterviewReview).not.toHaveBeenCalled();
  });

  it('粘贴模式不再显示「已载入示例速记对话」假提示', async () => {
    await gotoUploadStep();

    expect(screen.getByText('尚未输入文本')).toBeInTheDocument();
    expect(screen.queryByText(/已载入示例速记对话/)).not.toBeInTheDocument();
  });
});

describe('FE-REVIEW-01 手动录入新面试场次（表单字段必须进入 payload）', () => {
  const PREP_RESULT = {
    id: 77,
    round_type: '技术面',
    duration: '45分钟',
    elevator_pitch: '自我介绍',
    dimension_questions: [],
    full_version: '完整方案',
    html_content: '<div>方案</div>',
    created_at: '2026-10-01T10:00:00',
    company_research: null,
  };

  /** 手动录入路径的种子 QC：岗位带 jdAnalysisId（创建面试的前提），面试列表由各用例指定。 */
  const createManualQc = (seedInterviews: Interview[]) => {
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: Infinity },
        mutations: { retry: false },
      },
    });
    qc.setQueryData([...JOBS_QUERY_KEY], [{ ...JOB_12, jdAnalysisId: '12' } as unknown as Job]);
    qc.setQueryData([...INTERVIEWS_QUERY_KEY], seedInterviews);
    return qc;
  };

  beforeEach(() => {
    interview.generateInterviewPrep.mockResolvedValue(PREP_RESULT);
  });

  /** 步骤1 → 步骤2（上传记录），返回容器用于查日期/时间输入。 */
  const gotoUploadStep = async (qc: QueryClient) => {
    const view = renderWithProviders(
      <>
        <CreateReview />
        <ToastContainer />
      </>,
      { queryClient: qc },
    );
    await screen.findByText('步骤 1: 关联岗位');
    fireEvent.click(screen.getByText('下一步'));
    return view;
  };

  const pasteAndStart = async () => {
    await screen.findByText('步骤 3: 上传记录');
    fireEvent.change(screen.getByPlaceholderText(/【面试官】/), {
      target: { value: '面试内容：聊了 RAG 评测。' },
    });
    fireEvent.click(screen.getByText('开始 AI 智能复盘研判'));
  };

  // it 级超时须大于内层 waitFor(8000)：默认 5000 会在慢负载下先于 waitFor 判死（基线亦复现）
  it('岗位无面试记录：表单创建面试（轮次/日期时间/形式/面试官入 payload）再挂复盘', async () => {
    const qc = createManualQc([]);
    await gotoUploadStep(qc);

    // 该岗位无面试 → 直接呈现手动录入表单
    await screen.findByText('录入新面试场次信息');
    fireEvent.change(screen.getByDisplayValue('第1面 · 业务初面'), { target: { value: '4' } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-10-02' },
    });
    fireEvent.change(document.querySelector('input[type="time"]') as HTMLInputElement, {
      target: { value: '09:30' },
    });
    fireEvent.change(screen.getByPlaceholderText('如：业务主管、交叉技术官...'), {
      target: { value: '李面试官' },
    });

    fireEvent.click(screen.getByText('下一步'));
    await pasteAndStart();

    // 手动录入 → 先创建面试（roundType 由轮次号派生：第4面 → hr → HR面）
    await waitFor(
      () =>
        expect(interview.generateInterviewPrep).toHaveBeenCalledWith(12, {
          round_type: 'HR面',
          card_ids: [],
        }),
      { timeout: 8000 },
    );
    // 复盘挂到新建面试上（round_type 取新面试的 'hr'，而非残留旧选择）
    await waitFor(
      () =>
        expect(interview.createInterviewReview).toHaveBeenCalledWith(
          expect.objectContaining({ round_type: 'hr', raw_text: '面试内容：聊了 RAG 评测。' }),
        ),
      { timeout: 8000 },
    );

    // 表单字段全部落在新建 Interview 上
    const ivs = qc.getQueryData([...INTERVIEWS_QUERY_KEY]) as Interview[];
    expect(ivs).toHaveLength(1);
    expect(ivs[0]).toMatchObject({
      id: 'prep-77',
      jobId: '12',
      company: '字节跳动',
      role: 'AI 产品经理',
      roundNumber: 4,
      roundName: '第4面 · HRBP综合面',
      roundType: 'hr',
      time: '2026-10-02 09:30',
      format: 'video',
      interviewer: '李面试官',
    });

    // 成功 toast 的场次名来自实际创建的面试（此前固定用 manualForm 默认值）
    await screen.findByText(/第4面 · HRBP综合面/);
  }, 15000);

  it('已有面试但用户点「录入新面试场次」：创建新记录挂复盘，不挂残留的旧选择', async () => {
    const qc = createManualQc([INT_YUAN]);
    await gotoUploadStep(qc);

    // 已有面试列表可见，再切手动录入
    await screen.findByText(/选择面试场次/);
    fireEvent.click(screen.getByText('+ 录入新面试场次'));
    await screen.findByText('录入新面试场次信息');

    fireEvent.click(screen.getByText('下一步'));
    await pasteAndStart();

    // 必须走创建路径（旧行为：直接拿 selectedInterviewId=INT_YUAN 提交，表单被无视）
    await waitFor(
      () =>
        expect(interview.generateInterviewPrep).toHaveBeenCalledWith(12, {
          round_type: '业务面',
          card_ids: [],
        }),
      { timeout: 8000 },
    );
    // 复盘 round_type='business'（第1面派生）而非旧面试的 'tech'
    await waitFor(
      () =>
        expect(interview.createInterviewReview).toHaveBeenCalledWith(
          expect.objectContaining({ round_type: 'business' }),
        ),
      { timeout: 8000 },
    );
    expect(interview.createInterviewReview).not.toHaveBeenCalledWith(
      expect.objectContaining({ round_type: 'tech' }),
    );

    const ivs = qc.getQueryData([...INTERVIEWS_QUERY_KEY]) as Interview[];
    expect(ivs).toHaveLength(2);
    const created = ivs.find((i) => i.id === 'prep-77');
    expect(created).toMatchObject({
      roundNumber: 1,
      roundName: '第1面 · 业务初面',
      roundType: 'business',
      time: `${new Date().toISOString().split('T')[0]} 14:00`,
    });
    // 旧面试仍在（未被覆盖/删除）
    expect(ivs.find((i) => i.id === 'prep-7')).toBeTruthy();
  }, 15000);
});