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
  useConfirmFeedbackDecisionsMutation,
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
  createInterviewSession: vi.fn(),
  createInterviewReview: vi.fn(),
  uploadInterviewReview: vi.fn(),
  analyzeInterviewReview: vi.fn(),
  listInterviewReviewRecords: vi.fn(),
  listQuestionBankQaPairs: vi.fn(),
  getInterviewReviewDetail: vi.fn(),
  // T-M8-1 反馈闸门
  listFeedbackCandidates: vi.fn(),
  acceptFeedbackCandidate: vi.fn(),
  rejectFeedbackCandidate: vi.fn(),
  // T-M8-9 遗留 C：§24.2 汇总一次确认
  confirmFeedbackCandidates: vi.fn(),
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
// T-M8-1：反馈闸门需要 interview_records.id 作定位键（缺则确认沉淀诚实报错）
const REVIEW_GATE: InterviewReview = { ...REVIEW, recordId: 55 };
const INT_YUAN_GATE = buildInt(RECORD_YUAN, REVIEW_GATE);
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

/** T-M8-9 遗留 C：§24.2 汇总一次确认 harness（accept + reject 合并为一次请求） */
const ConfirmHarness = ({
  ids = { acceptIds: ['7'], rejectIds: ['8'] },
}: {
  ids?: { acceptIds: string[]; rejectIds: string[] };
}) => {
  const confirmDecisions = useConfirmFeedbackDecisionsMutation();
  const [error, setError] = useState('');
  return (
    <div>
      <button
        onClick={() => {
          setError('');
          confirmDecisions
            .mutateAsync({ interviewId: 'prep-7', ...ids })
            .catch((e: unknown) => setError((e as Error).message));
        }}
      >
        汇总确认
      </button>
      <span data-testid="confirm-error">{error}</span>
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
  // T-M8-1 反馈闸门默认态：无候选（不伪造 pending 建议）
  interview.listFeedbackCandidates.mockResolvedValue({
    record_id: 55,
    candidates: [],
    candidate_count: 0,
    pending_count: 0,
    gate_status: 'none',
  });
  interview.acceptFeedbackCandidate.mockImplementation(
    async (
      recordId: number,
      payload: {
        target_ref: string;
        background?: string;
        problem?: string;
        actions?: string[];
        results?: string[];
      },
    ) => {
      // 服务端落卡语义：写四槽位 + version+1（前端不再直调 updateCard）
      const card = serverCards.find((c) => String(c.id) === payload.target_ref);
      if (card) {
        if (payload.background !== undefined) card.background = payload.background;
        if (payload.problem !== undefined) card.problem = payload.problem;
        if (payload.actions !== undefined) card.actions = payload.actions;
        if (payload.results !== undefined) card.results = payload.results;
        card.version = (card.version ?? 1) + 1;
      }
      return {
        record_id: recordId,
        target_ref: payload.target_ref,
        decision: 'accepted' as const,
        card_version: card?.version ?? null,
        decided_at: '2026-10-04T12:00:00',
        idempotent: false,
        gate_status: 'done' as const,
      };
    },
  );
  interview.rejectFeedbackCandidate.mockImplementation(
    async (recordId: number, payload: { target_ref: string }) => ({
      record_id: recordId,
      target_ref: payload.target_ref,
      decision: 'rejected' as const,
      card_version: null,
      decided_at: '2026-10-04T12:00:00',
      idempotent: false,
      gate_status: 'done' as const,
    }),
  );
  // T-M8-9 遗留 C：批量确认 mock——服务端语义（接受型写卡 version+1，忽略型只记台账）
  interview.confirmFeedbackCandidates.mockImplementation(
    async (
      recordId: number,
      payload: {
        decisions: Array<{
          target_ref: string;
          decision: 'accepted' | 'edited' | 'rejected';
          background?: string;
          problem?: string;
          actions?: string[];
          results?: string[];
        }>;
      },
    ) => {
      const results = payload.decisions.map((d) => {
        if (d.decision === 'rejected') {
          return {
            target_ref: d.target_ref,
            decision: 'rejected' as const,
            card_version: null,
            decided_at: '2026-10-04T12:00:00',
            idempotent: false,
          };
        }
        const card = serverCards.find((c) => String(c.id) === d.target_ref);
        if (card) {
          if (d.background !== undefined) card.background = d.background;
          if (d.problem !== undefined) card.problem = d.problem;
          if (d.actions !== undefined) card.actions = d.actions;
          if (d.results !== undefined) card.results = d.results;
          card.version = (card.version ?? 1) + 1;
        }
        return {
          target_ref: d.target_ref,
          decision: 'accepted' as const,
          card_version: card?.version ?? null,
          decided_at: '2026-10-04T12:00:00',
          idempotent: false,
        };
      });
      return {
        record_id: recordId,
        results,
        decision_count: results.length,
        gate_status: 'done' as const,
      };
    },
  );
  // T-M8-2 详情直读默认：服务端无 record（组件回退内存 review / 空态）
  interview.listInterviewReviewRecords.mockResolvedValue({ records: [] });
  interview.getInterviewReviewDetail.mockResolvedValue({
    record: {
      id: 55,
      user_id: 1,
      title: '腾讯 AI 产品经理产品面复盘',
      company: '腾讯',
      position: 'AI 产品经理',
      round_type: 'product',
      job_analysis_id: 13,
      status: 'done',
      created_at: '2026-09-21T10:00:00',
      analysis: {
        ...ANALYSIS,
        overall_score: 76,
        summary: '服务端直读总评',
        strengths: ['直读优势'],
        weaknesses: ['直读短板'],
      },
    },
    qa_pairs: [
      {
        id: 31,
        record_id: 55,
        sequence: 1,
        speaker: '面试官',
        start_time: '0.1',
        content: '服务端直读题目',
        is_question: true,
        question_text: '服务端直读题目',
        dimension: '技术深度',
        level: '深挖',
        intent: '考察直读链路',
        expected_answer: '期望回答',
        my_answer: '我的直读回答',
        feedback: ['直读反馈'],
        suggestions: ['直读建议'],
        score: 76,
        related_card_id: 7,
        related_card_title: '端侧大模型量化评测',
      },
    ],
  });
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
    expect(interview.createInterviewReview).toHaveBeenCalledWith(
      // T-M8-7：载荷新增 job_analysis_id / submission_id / record_id 透传
      expect.objectContaining({
        user_id: 1,
        company: '字节跳动',
        position: 'AI 产品经理',
        round_type: 'tech',
        raw_text: '面试逐字稿...',
      }),
    );
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
    // T-M8-8：分析缺失不再按题数伪造分数（原 1 题 → 10 分），记 0 = 未评分
    expect(screen.getByTestId('cache-score').textContent).toBe('0');
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
      expect.objectContaining({
        user_id: 1,
        company: '字节跳动',
        position: 'AI 产品经理',
        round_type: 'tech',
      }),
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
    // 反哺的写入需在服务端可回读：listCards 返回有状态卡片，
    // EXPERIENCES invalidate refetch 后内容/版本与乐观补丁一致。
    serverCards = [{ ...CARD_A }];
    // 详情直读返回 null → 视图回退内存 review（反哺用例聚焦闸门写卡链路）
    interview.getInterviewReviewDetail.mockResolvedValue(null);
  });

  it('proposedChanges 路径：accept 端点落卡 + EXPERIENCES/INTERVIEWS cache 反哺', async () => {
    renderWithProviders(
      <>
        <Seeder
          interviews={[INT_YUAN_GATE, INT_TX_PREP]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <ApplyHarness interviews={[INT_YUAN_GATE]} />
      </>,
    );

    await screen.findByText('应用反馈');
    await waitForSeed();
    fireEvent.click(screen.getByText('应用反馈'));

    // EXPERIENCES cache：字段变更 + 后端版本回流（versionHistory 来自 card_versions）
    await waitFor(() => expect(screen.getByTestId('cache-exp-version').textContent).toBe('V2'));
    // T-M8-1：内容变更交后端 accept 端点落盘（服务端版本化 + 决策记台账），
    // 前端不再直调 updateCard；P10-b-lite 轻闸门：只追加新版本、不强制定稿
    expect(interview.acceptFeedbackCandidate).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        target_ref: '7',
        problem: '新职责（含选型对比）',
        actions: ['旧动作A', '旧动作B'],
      }),
    );
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalledWith(
      55,
      expect.objectContaining({ is_confirmed: true })
    );
    expect(experience.updateCard).not.toHaveBeenCalled();
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
          interviews={[buildInt(RECORD_YUAN, { ...REVIEW_SUGG, recordId: 55 })]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <ApplyHarness
          interviews={[buildInt(RECORD_YUAN, { ...REVIEW_SUGG, recordId: 55 })]}
        />
      </>,
    );

    await screen.findByText('应用反馈');
    await waitForSeed();
    fireEvent.click(screen.getByText('应用反馈'));

    await waitFor(() => expect(screen.getByTestId('cache-exp-version').textContent).toBe('V2'));
    // suggestions 前置动作已随 accept 提交给后端（P10-b-lite：不再强制定稿）
    expect(interview.acceptFeedbackCandidate).toHaveBeenCalledWith(
      55,
      expect.objectContaining({
        target_ref: '7',
        actions: ['[面试复盘升级] 补充量化选型对比', '旧动作A', '旧动作B'],
      }),
    );
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalledWith(
      55,
      expect.objectContaining({ is_confirmed: true })
    );
    expect(experience.updateCard).not.toHaveBeenCalled();
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

describe('T-M8-3 聚合题库 tab（只读浏览 + 复制题目）', () => {
  const BANK_PAIR = {
    id: 31,
    record_id: 55,
    sequence: 2,
    speaker: '面试官',
    start_time: '00:10',
    content: '讲讲你的 RAG 项目',
    is_question: true,
    question_text: '讲讲你的 RAG 项目',
    dimension: '项目深挖',
    level: 'L2',
    intent: '验证真实性',
    expected_answer: 'STAR 展开',
    my_answer: '我做了评测集',
    feedback: [],
    suggestions: [],
    score: 80,
    related_card_id: null,
    related_card_title: null,
    record_title: '腾讯-后端-技术面',
    record_company: '腾讯',
    record_position: '后端工程师',
    record_round_type: '技术面',
    record_job_analysis_id: 12,
  };

  it('切到题库 tab 直读聚合端点，搜索过滤生效', async () => {
    interview.listQuestionBankQaPairs.mockResolvedValue({
      qa_pairs: [BANK_PAIR],
      qa_pair_count: 1,
      job_analysis_id: null,
    });
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <InterviewReviewCenterView />
      </>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '面试题库' }));

    // 单次聚合调用（不按 record 逐个拉详情）
    expect(await screen.findByText('讲讲你的 RAG 项目')).toBeInTheDocument();
    expect(interview.listQuestionBankQaPairs).toHaveBeenCalledTimes(1);
    expect(interview.listQuestionBankQaPairs).toHaveBeenCalledWith(undefined);
    expect(interview.getInterviewReviewDetail).not.toHaveBeenCalled();
    // 场次上下文 + 参考要点直读
    expect(screen.getByText(/腾讯 · 后端工程师/)).toBeInTheDocument();
    expect(screen.getByText(/STAR 展开/)).toBeInTheDocument();

    // 搜索过滤
    fireEvent.change(screen.getByPlaceholderText('搜索题目 / 公司 / 岗位'), {
      target: { value: '不存在的题' },
    });
    expect(screen.getByText('没有匹配的题目')).toBeInTheDocument();
  });

  it('复制失败如实报错，不假报成功', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('未授予剪贴板权限'));
    Object.assign(navigator, { clipboard: { writeText } });
    interview.listQuestionBankQaPairs.mockResolvedValue({
      qa_pairs: [BANK_PAIR],
      qa_pair_count: 1,
      job_analysis_id: null,
    });
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <InterviewReviewCenterView />
      </>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '面试题库' }));
    await screen.findByText('讲讲你的 RAG 项目');
    fireEvent.click(screen.getByRole('button', { name: /复制题目/ }));

    // 复制失败：按钮态与提示均如实报错，不假报成功
    expect(writeText).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /复制题目/ })).toHaveTextContent(
        '复制失败'
      )
    );
  });

  it('题库为空时给诚实空态，不显示假数据', async () => {
    interview.listQuestionBankQaPairs.mockResolvedValue({
      qa_pairs: [],
      qa_pair_count: 0,
      job_analysis_id: null,
    });
    renderWithProviders(
      <>
        <Seeder {...seedProps} />
        <InterviewReviewCenterView />
      </>,
    );

    fireEvent.click(await screen.findByRole('button', { name: '面试题库' }));
    expect(await screen.findByText('题库暂无内容')).toBeInTheDocument();
    expect(screen.getByText(/完成一次面试复盘后/)).toBeInTheDocument();
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
    // T-M8-1：详情直读返回 null → 回退内存 review（反哺入口来自内存 qaList）
    interview.getInterviewReviewDetail.mockResolvedValue(null);
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

  // T-M8-1：带 recordId 的复盘才能走闸门（interview_records.id 定位键）
  const REVIEW_QA_GATE: InterviewReview = { ...REVIEW_QA, recordId: 55 };

  const renderDetail = () =>
    renderWithProviders(
      <>
        <Seeder interviews={[buildInt(RECORD_YUAN, REVIEW_QA_GATE)]} experiences={[EXP_V1]} jobs={[JOB_12]} />
        <InterviewReviewDetailView interviewId="prep-7" />
      </>,
    );
  it('首次点击仅进入确认态，不触发写回', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));

    // 确认态出现（说明追加新版本 + 保留历史），且不写回
    expect(await screen.findByText('确认写入')).toBeInTheDocument();
    expect(screen.getByText(/保留历史/)).toBeInTheDocument();
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
  });

  it('二次点击确认后才写回，且不强制定稿', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));
    fireEvent.click(await screen.findByText('确认写入'));

    // T-M8-1：写卡与决策台账由服务端 accept 端点一次完成
    await waitFor(() => expect(interview.acceptFeedbackCandidate).toHaveBeenCalledWith(
      55,
      expect.objectContaining({ target_ref: '7', problem: '新职责（含选型对比）' }),
    ));
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalledWith(
      55,
      expect.objectContaining({ is_confirmed: true })
    );
  });

  it('确认态点取消则不写回', async () => {
    renderDetail();

    fireEvent.click(await screen.findByText('沉淀至经历库'));
    fireEvent.click(await screen.findByText('取消'));

    await waitFor(() => expect(screen.getByText('沉淀至经历库')).toBeInTheDocument());
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
  });
});

describe('T-M8-1 反馈闸门（决策以服务端台账为准）', () => {
  beforeEach(() => {
    auth.getCurrentUser.mockResolvedValue(AUTH_USER);
    job.getDashboard.mockResolvedValue({ submissions: [] });
    interview.listInterviewPreps.mockResolvedValue([RECORD_YUAN, RECORD_TX]);
    experience.listCards.mockResolvedValue([CARD_A]);
    experience.listCardVersions.mockResolvedValue({
      card_id: 7,
      current_version: 2,
      versions: [],
    });
    serverCards = [{ ...CARD_A }];
    interview.getInterviewReviewDetail.mockResolvedValue(null);
  });

  const REVIEW_QA_GATE: InterviewReview = {
    ...REVIEW,
    recordId: 55,
    qaList: [
      {
        id: 'qa-1',
        qIndex: 1,
        question: '介绍端侧量化方案',
        candidateAnswer: '答题内容',
        interviewerIntent: {
          mainPoints: ['技术深度'],
          importanceStars: 4,
          productAbilityStars: 3,
          techDepthStars: 5,
        },
        answerAnalysis: {
          completeness: 80,
          structure: 75,
          persuasiveness: 70,
          jobRelevance: 85,
        },
        identifiedIssues: ['缺选型对比'],
        suggestionAdvice: '补充量化对比',
        relatedExperienceId: '7',
      },
    ],
  };

  const gateCandidate = (
    decision: 'pending' | 'accepted' | 'edited' | 'rejected',
  ) => ({
    record_id: 55,
    candidates: [
      {
        target_type: 'experience',
        target_ref: '7',
        experience_id: '7',
        experience_title: '端侧大模型量化评测',
        discovered_issues: ['缺选型对比'],
        suggestions: ['补充量化对比'],
        current_version: 'V1',
        proposed_version: 'V2',
        proposed_changes: [],
        decision,
        card_version: decision === 'pending' || decision === 'rejected' ? null : 2,
        decided_at: decision === 'pending' ? null : '2026-10-04T12:00:00',
      },
    ],
    candidate_count: 1,
    pending_count: decision === 'pending' ? 1 : 0,
    gate_status:
      decision === 'pending' ? ('awaiting_confirmation' as const) : ('done' as const),
  });

  const renderGate = () =>
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_QA_GATE)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <InterviewReviewDetailView interviewId="prep-7" />
      </>,
    );

  it('台账 accepted → 直接显示已同步（刷新后不再显示可写按钮）', async () => {
    interview.listFeedbackCandidates.mockResolvedValue(gateCandidate('accepted'));
    renderGate();

    expect(await screen.findByText('已同步')).toBeInTheDocument();
    expect(screen.queryByText('沉淀至经历库')).not.toBeInTheDocument();
  });

  it('台账 rejected → 显示可反悔的「已忽略 · 重新确认」', async () => {
    interview.listFeedbackCandidates.mockResolvedValue(gateCandidate('rejected'));
    renderGate();

    expect(await screen.findByText('已忽略 · 重新确认')).toBeInTheDocument();
  });

  it('台账 edited（T-M8-9）→ 显示「已编辑确认」且无写入按钮', async () => {
    interview.listFeedbackCandidates.mockResolvedValue(gateCandidate('edited'));
    renderGate();

    expect(await screen.findByText('已编辑确认')).toBeInTheDocument();
    expect(screen.queryByText('沉淀至经历库')).not.toBeInTheDocument();
  });

  it('已确认沉淀的候选忽略失败 → 透传服务端 409 原因', async () => {
    interview.listFeedbackCandidates.mockResolvedValue(gateCandidate('pending'));
    interview.rejectFeedbackCandidate.mockRejectedValue(
      new Error('该候选已确认沉淀到经历卡，请先在卡片页回滚内容后再忽略'),
    );
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_QA_GATE)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <InterviewReviewDetailView interviewId="prep-7" />
        <ToastContainer />
      </>,
    );

    fireEvent.click(await screen.findByText('忽略'));

    expect(
      await screen.findByText(
        '该候选已确认沉淀到经历卡，请先在卡片页回滚内容后再忽略',
      ),
    ).toBeInTheDocument();
  });

  it('pending → 点忽略只记台账，不写卡', async () => {
    interview.listFeedbackCandidates.mockResolvedValue(gateCandidate('pending'));
    renderGate();

    fireEvent.click(await screen.findByText('忽略'));

    await waitFor(() =>
      expect(interview.rejectFeedbackCandidate).toHaveBeenCalledWith(55, {
        target_ref: '7',
        target_type: 'experience',
      }),
    );
    expect(experience.updateCard).not.toHaveBeenCalled();
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
  });

  it('复盘缺 recordId → 点确认沉淀诚实报错，不静默跳过', async () => {
    // 无 recordId 的复盘（老数据）：闸门无从定位，必须报错而不是假装成功
    interview.listFeedbackCandidates.mockResolvedValue({
      record_id: -1,
      candidates: [],
      candidate_count: 0,
      pending_count: 0,
      gate_status: 'none',
    });
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, { ...REVIEW_QA_GATE, recordId: undefined })]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <InterviewReviewDetailView interviewId="prep-7" />
        <ToastContainer />
      </>,
    );

    fireEvent.click(await screen.findByText('沉淀至经历库'));
    fireEvent.click(await screen.findByText('确认写入'));

    expect(await screen.findByText('沉淀失败')).toBeInTheDocument();
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
  });
});

describe('T-M8-9 遗留 C：§24.2 汇总一次确认', () => {
  const REVIEW_BATCH_GATE: InterviewReview = {
    ...REVIEW,
    recordId: 55,
    experienceFeedbacks: [
      ...REVIEW.experienceFeedbacks!,
      {
        experienceId: '8',
        experienceTitle: '第二段经历',
        discoveredIssues: ['缺口径'],
        suggestions: ['补指标'],
        currentVersion: 'V1',
        proposedVersion: 'V2',
        proposedChanges: [],
        applied: false,
      },
    ],
  };

  const pendingGate = (overrides: Record<string, unknown> = {}) => ({
    record_id: 55,
    candidates: [
      {
        target_type: 'experience',
        target_ref: '7',
        experience_id: '7',
        experience_title: '端侧大模型量化评测',
        discovered_issues: ['缺选型对比'],
        suggestions: ['补充量化对比'],
        current_version: 'V1',
        proposed_version: 'V2',
        proposed_changes: [],
        decision: 'pending',
        card_version: null,
        decided_at: null,
      },
    ],
    candidate_count: 1,
    pending_count: 1,
    gate_status: 'awaiting_confirmation',
    ...overrides,
  });

  beforeEach(() => {
    serverCards = [{ ...CARD_A }];
    // 聚焦闸门写卡链路：详情直读返回 null → 视图/缓存回退内存 review
    interview.getInterviewReviewDetail.mockResolvedValue(null);
    interview.listInterviewReviewRecords.mockResolvedValue({ records: [] });
  });

  it('accept + reject 合并为一次批量请求（不再逐条调单端点）', async () => {
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_BATCH_GATE)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <ConfirmHarness />
      </>,
    );

    await screen.findByText('汇总确认');
    await waitForSeed();
    fireEvent.click(screen.getByText('汇总确认'));

    await waitFor(() =>
      expect(interview.confirmFeedbackCandidates).toHaveBeenCalledWith(55, {
        decisions: [
          expect.objectContaining({
            target_ref: '7',
            decision: 'accepted',
            problem: '新职责（含选型对比）',
            actions: ['旧动作A', '旧动作B'],
          }),
          expect.objectContaining({ target_ref: '8', decision: 'rejected' }),
        ],
      }),
    );
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
    expect(interview.rejectFeedbackCandidate).not.toHaveBeenCalled();
    // 服务端落卡后 EXPERIENCES refetch 回流版本；INTERVIEWS applied 标记同步
    await waitFor(() =>
      expect(screen.getByTestId('cache-exp-version').textContent).toBe('V2'),
    );
    expect(screen.getByTestId('cache-applied').textContent).toBe('true');
    expect(screen.getByTestId('confirm-error').textContent).toBe('');
  });

  it('空选择 → 报错且不发请求', async () => {
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_BATCH_GATE)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <ConfirmHarness ids={{ acceptIds: [], rejectIds: [] }} />
      </>,
    );

    await screen.findByText('汇总确认');
    await waitForSeed();
    fireEvent.click(screen.getByText('汇总确认'));

    expect(await screen.findByTestId('confirm-error')).toHaveTextContent(
      '未选择任何候选决策',
    );
    expect(interview.confirmFeedbackCandidates).not.toHaveBeenCalled();
  });

  const renderPanel = (gate: ReturnType<typeof pendingGate> = pendingGate()) => {
    interview.listFeedbackCandidates.mockResolvedValue(gate);
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, REVIEW_BATCH_GATE)]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <InterviewReviewDetailView interviewId="prep-7" />
        <ToastContainer />
      </>,
    );
  };

  it('pending → 汇总面板默认全选，一次请求完成确认沉淀', async () => {
    renderPanel();

    expect(await screen.findByTestId('feedback-batch-panel')).toBeInTheDocument();
    fireEvent.click(await screen.findByText('确认沉淀（1 条）'));

    await waitFor(() =>
      expect(interview.confirmFeedbackCandidates).toHaveBeenCalledWith(55, {
        decisions: [
          expect.objectContaining({ target_ref: '7', decision: 'accepted' }),
        ],
      }),
    );
    expect(interview.acceptFeedbackCandidate).not.toHaveBeenCalled();
    expect(await screen.findByText('已沉淀 1 条建议')).toBeInTheDocument();
  });

  it('反选后按钮为 0 条并禁用，点击不发请求', async () => {
    renderPanel();

    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);

    const submit = screen.getByText('确认沉淀（0 条）');
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(interview.confirmFeedbackCandidates).not.toHaveBeenCalled();
  });

  it('全部忽略走两段确认，批量提交 rejected 决策', async () => {
    renderPanel();

    await screen.findByTestId('feedback-batch-panel');
    fireEvent.click(screen.getByText('全部忽略'));
    fireEvent.click(await screen.findByText('确认忽略全部 1 条？'));

    await waitFor(() =>
      expect(interview.confirmFeedbackCandidates).toHaveBeenCalledWith(55, {
        decisions: [
          expect.objectContaining({ target_ref: '7', decision: 'rejected' }),
        ],
      }),
    );
    expect(interview.rejectFeedbackCandidate).not.toHaveBeenCalled();
    expect(await screen.findByText('已忽略 1 条候选')).toBeInTheDocument();
  });

  it('无 pending 候选 → 不渲染汇总面板', async () => {
    renderPanel({
      ...pendingGate(),
      candidates: [],
      candidate_count: 0,
      pending_count: 0,
      gate_status: 'done',
    });

    expect(await screen.findByText('QA 题目清单 (0)')).toBeInTheDocument();
    expect(screen.queryByTestId('feedback-batch-panel')).not.toBeInTheDocument();
  });
});

describe('W12 终审：确认链实时数据源（候选正文不读 INTERVIEWS 缓存）', () => {
  const RECORD_YUAN_ROW = {
    id: 55,
    user_id: 1,
    title: '字节跳动 AI 产品经理技术面复盘',
    company: '字节跳动',
    position: 'AI 产品经理',
    round_type: 'tech',
    job_analysis_id: 12,
    status: 'done',
    created_at: '2026-10-01T09:00:00',
  };

  const buildDetail = (experienceFeedbacks: InterviewReview['experienceFeedbacks']) => ({
    record: {
      ...RECORD_YUAN_ROW,
      analysis: { ...ANALYSIS, record_id: 55, experienceFeedbacks },
    },
    qa_pairs: [
      {
        id: 41,
        record_id: 55,
        sequence: 1,
        speaker: '面试官',
        start_time: '0.1',
        content: '介绍端侧量化方案',
        is_question: true,
        question_text: '介绍端侧量化方案',
        dimension: '技术深度',
        level: '深挖',
        intent: '考察量化落地',
        expected_answer: '量化指标拆解',
        my_answer: '端侧量化评测方案与指标',
        feedback: ['缺选型对比'],
        suggestions: ['补充量化对比'],
        score: 70,
        related_card_id: 7,
        related_card_title: '端侧大模型量化评测',
      },
    ],
  });

  const GATE_PENDING = {
    record_id: 55,
    candidates: [
      {
        target_type: 'experience',
        target_ref: '7',
        experience_id: '7',
        experience_title: '端侧大模型量化评测',
        discovered_issues: ['缺选型对比'],
        suggestions: ['补充量化对比'],
        current_version: 'V1',
        proposed_version: 'V2',
        proposed_changes: [],
        decision: 'pending',
        card_version: null,
        decided_at: null,
      },
    ],
    candidate_count: 1,
    pending_count: 1,
    gate_status: 'awaiting_confirmation',
  };

  beforeEach(() => {
    serverCards = [{ ...CARD_A }];
    interview.listInterviewReviewRecords.mockResolvedValue({ records: [{ ...RECORD_YUAN_ROW }] });
    interview.getInterviewReviewDetail.mockResolvedValue(buildDetail(REVIEW.experienceFeedbacks));
    interview.listFeedbackCandidates.mockResolvedValue(GATE_PENDING);
  });

  it('详情 analysis.experienceFeedbacks 直读进 review（徽章实时渲染；缓存 review 候选正文为空）', async () => {
    renderWithProviders(
      <>
        <Seeder
          interviews={[buildInt(RECORD_YUAN, { ...REVIEW, recordId: 55, experienceFeedbacks: [] })]}
          experiences={[EXP_V1]}
          jobs={[JOB_12]}
        />
        <InterviewReviewDetailView interviewId="prep-7" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText('已关联经历资产：端侧大模型量化评测')).toBeInTheDocument();
  });
});

describe('T-M8-2 详情页直读 interview_qa_pairs', () => {
  const RECORD_TX_ROW = {
    id: 55,
    user_id: 1,
    title: '腾讯 AI 产品经理产品面复盘',
    company: '腾讯',
    position: 'AI 产品经理',
    round_type: 'product',
    job_analysis_id: 13,
    status: 'done',
    created_at: '2026-09-21T10:00:00',
  };

  it('刷新场景（内存无 review）：按 company/position/round 定位 record 后直读渲染题库', async () => {
    interview.listInterviewReviewRecords.mockResolvedValue({ records: [RECORD_TX_ROW] });

    renderWithProviders(
      <>
        <Seeder interviews={[INT_TX_PREP]} experiences={[EXP_V1]} jobs={[]} />
        <InterviewReviewDetailView interviewId="prep-8" />
      </>,
    );

    // 直读数据渲染（record.analysis 总评 + qa_pairs 题目），而非「暂无复盘报告」空态
    expect(await screen.findByText('腾讯 · AI 产品经理')).toBeInTheDocument();
    expect(
      (await screen.findAllByText('服务端直读题目')).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/识别 1 组 QA/)).toBeInTheDocument();
    expect(interview.listInterviewReviewRecords).toHaveBeenCalled();
    expect(interview.getInterviewReviewDetail).toHaveBeenCalledWith(55);
  });

  it('直读为 SoT：服务端 record+题库优先于内存 review 展示', async () => {
    interview.listInterviewReviewRecords.mockResolvedValue({
      records: [{ ...RECORD_TX_ROW, id: 99, company: '字节跳动', round_type: 'tech', job_analysis_id: 12 }],
    });
    interview.getInterviewReviewDetail.mockResolvedValue({
      record: {
        id: 99,
        user_id: 1,
        title: '字节跳动 AI 产品经理技术面复盘',
        company: '字节跳动',
        position: 'AI 产品经理',
        round_type: 'tech',
        job_analysis_id: 12,
        status: 'done',
        created_at: '2026-09-22T09:00:00',
        analysis: { ...ANALYSIS, overall_score: 62, summary: '直读总评覆盖内存' },
      },
      qa_pairs: [
        {
          id: 41,
          record_id: 99,
          sequence: 1,
          speaker: '面试官',
          start_time: '0.1',
          content: '服务端直读题目覆盖内存',
          is_question: true,
          question_text: '服务端直读题目覆盖内存',
          dimension: '技术深度',
          level: '深挖',
          intent: '考察直读链路',
          expected_answer: '期望回答',
          my_answer: '我的直读回答',
          feedback: ['直读反馈'],
          suggestions: ['直读建议'],
          score: 62,
          related_card_id: null,
          related_card_title: null,
        },
      ],
    });

    renderWithProviders(
      <>
        <Seeder interviews={[INT_YUAN]} experiences={[EXP_V1]} jobs={[JOB_12]} />
        <InterviewReviewDetailView interviewId="prep-7" />
      </>,
    );

    // 内存 REVIEW.overallScore=85/qaList=[]；直读 analysis=62 + 1 条题目
    expect(await screen.findByText('字节跳动 · AI 产品经理')).toBeInTheDocument();
    expect(
      (await screen.findAllByText('服务端直读题目覆盖内存')).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/识别 1 组 QA/)).toBeInTheDocument();
    expect(screen.getAllByText('62').length).toBeGreaterThan(0);
    expect(screen.queryByText(/识别 0 组 QA/)).not.toBeInTheDocument();
  });

  it('服务端无匹配 record：回退内存 review（不回归现状）', async () => {
    renderWithProviders(
      <>
        <Seeder interviews={[INT_YUAN]} experiences={[EXP_V1]} jobs={[JOB_12]} />
        <InterviewReviewDetailView interviewId="prep-7" />
      </>,
    );

    expect(await screen.findByText('字节跳动 · AI 产品经理')).toBeInTheDocument();
    expect(screen.getAllByText('85').length).toBeGreaterThan(0);
    expect(interview.getInterviewReviewDetail).not.toHaveBeenCalled();
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
    // T-M8-5：去音频后标注「待接入转写」（spec §3 转写=上游）
    expect(screen.getByText(/音频\/录音上传待接入转写/)).toBeInTheDocument();
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

describe('T-M8-4 向导收敛（删手动录入表单，关联已有/新建面试）', () => {
  /** 种子 QC：岗位带 jdAnalysisId（关联岗位的前提），面试列表由各用例指定。 */
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
    // T-M8-4：手动录入路径已删；场次预建 mock 供 Modal 创建链路触达
    interview.createInterviewSession.mockResolvedValue({ record_id: 902, status: 'planned' });
    interview.generateInterviewPrep.mockResolvedValue({
      id: 77,
      round_type: '技术面',
      duration: '45分钟',
      elevator_pitch: '自我介绍',
      dimension_questions: [],
      full_version: '完整方案',
      html_content: '<div>方案</div>',
      created_at: '2026-10-01T10:00:00',
      company_research: null,
    });
  });

  /** 步骤1 → 步骤2（关联面试）。 */
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
  it('岗位无面试记录：空态引导新建、无手动录入表单、下一步禁用，Modal 可开合', async () => {
    const qc = createManualQc([]);
    await gotoUploadStep(qc);

    // T-M8-4：手动录入表单已删（Q3 删表单分支），空态引导经 NewInterviewModal 新建
    await screen.findByText('步骤 2: 关联面试');
    expect(screen.queryByText('录入新面试场次信息')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('第1面 · 业务初面')).not.toBeInTheDocument();
    expect(screen.getByText('该岗位暂无面试场次')).toBeInTheDocument();

    // 无场次可关联 → 下一步禁用
    expect(screen.getByRole('button', { name: /下一步/ })).toBeDisabled();

    // 「新建面试」复用 Modal（from-job）；关掉后仍停在向导（不跳备战工作台）
    fireEvent.click(screen.getByText('+ 新建面试'));
    expect(await screen.findByText('新建面试准备')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('关闭'));
    expect(screen.queryByText('新建面试准备')).not.toBeInTheDocument();
    expect(screen.getByText('步骤 2: 关联面试')).toBeInTheDocument();
  }, 15000);

  it('关联已有面试直接挂复盘：不中途创建面试，成功后落库跳详情', async () => {
    const qc = createManualQc([INT_YUAN]);
    await gotoUploadStep(qc);

    // 已有面试列表（自动选中唯一场次）；入口按钮为「+ 新建面试」而非手动表单
    await screen.findByText(/选择面试场次/);
    expect(screen.getByText('+ 新建面试')).toBeInTheDocument();

    fireEvent.click(screen.getByText('下一步'));
    await pasteAndStart();

    // T-M8-4：手动录入路径已删 → 不再中途创建面试，直接挂既有场次
    await waitFor(
      () =>
        expect(interview.createInterviewReview).toHaveBeenCalledWith(
          expect.objectContaining({
            company: '字节跳动',
            position: 'AI 产品经理',
            round_type: 'tech',
            raw_text: '面试内容：聊了 RAG 评测。',
            // T-M8-7：透传岗位分析/投递（题库回流断点），无预建场次则 record_id 为 null
            job_analysis_id: 12,
            submission_id: 1,
            record_id: null,
          }),
        ),
      { timeout: 8000 },
    );
    expect(interview.generateInterviewPrep).not.toHaveBeenCalled();

    // 成功 toast + 复盘落回 INT_YUAN（status preparing → completed）
    await screen.findByText('面试复盘已生成');
    await waitFor(
      () => {
        const ivs = qc.getQueryData([...INTERVIEWS_QUERY_KEY]) as Interview[];
        expect(ivs.find((i) => i.id === INT_YUAN.id)?.status).toBe('completed');
      },
      { timeout: 8000 },
    );
  }, 15000);

  // T-M8-7：预建 planned 行在场（sessionRecordId）→ 复盘走 update 分支复用该行，不重复插行
  it('预建场次在场：复盘透传 record_id 复用 planned 行', async () => {
    const planned = { ...INT_YUAN, sessionRecordId: 902 };
    const qc = createManualQc([planned]);
    await gotoUploadStep(qc);

    await screen.findByText(/选择面试场次/);
    fireEvent.click(screen.getByText('下一步'));
    await pasteAndStart();

    await waitFor(
      () =>
        expect(interview.createInterviewReview).toHaveBeenCalledWith(
          expect.objectContaining({
            record_id: 902,
            job_analysis_id: 12,
            submission_id: 1,
          }),
        ),
      { timeout: 8000 },
    );
    // 走 update 分支 → 绝不新建面试行
    expect(interview.createInterviewSession).not.toHaveBeenCalled();
  }, 15000);
});