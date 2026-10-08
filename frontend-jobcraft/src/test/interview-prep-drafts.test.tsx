import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { InterviewPrepWorkspaceView } from '../components/interview/InterviewPrepWorkspaceView';
import { InterviewDetailsStep } from '../components/interview/InterviewDetailsStep';
import {
  useSavePrepDraftsMutation,
  useInterviewsQuery,
} from '../features/interview/hooks';
import type { InterviewPrepRecord } from '../api/types';

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
  saveInterviewPrepDrafts: vi.fn(),
  refreshInterviewPrepResearch: vi.fn(),
}));

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
  createExpression: vi.fn(),
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
  drafts: {},
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
  experience.listCards.mockResolvedValue({ cards: [] });
  interview.listInterviewPreps.mockResolvedValue({ records: [PREP_RECORD] });
  interview.saveInterviewPrepDrafts.mockResolvedValue({ id: 7, drafts: {} });
  interview.refreshInterviewPrepResearch.mockResolvedValue({
    id: 7,
    company_research: { basic: { name: '字节跳动' } },
  });
  tasks.runTaskOrSync.mockImplementation(async (_t, _p, fallback) => fallback());
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** 打开「演练」分区（T-M7-2 3-tab，原 03 维度题准备）并等待内容渲染。 */
async function openQuestionSection() {
  fireEvent.click(screen.getByText('02 演练'));
  await screen.findByText(/共 1 道维度题/);
  return screen.getByPlaceholderText(/STAR 结构/);
}

describe('FE-PREP-01 备战草稿落库', () => {
  it('从 prepSource.drafts 灌入本地编辑态，保存时 PATCH 并弹成功 toast', async () => {
    interview.listInterviewPreps.mockResolvedValue({
      records: [{ ...PREP_RECORD, drafts: { 'q-0': '服务端已有草稿' } }],
    });
    interview.saveInterviewPrepDrafts.mockResolvedValue({
      id: 7,
      drafts: { 'q-0': '本地编辑后的草稿' },
    });

    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );

    const textarea = await openQuestionSection();
    await waitFor(() => expect((textarea as HTMLTextAreaElement).value).toBe('服务端已有草稿'));

    fireEvent.change(textarea, { target: { value: '本地编辑后的草稿' } });
    fireEvent.click(screen.getByText('保存草稿'));

    await waitFor(() =>
      expect(interview.saveInterviewPrepDrafts).toHaveBeenCalledWith(7, {
        'q-0': '本地编辑后的草稿',
      })
    );
    await screen.findByText('回答草稿已保存');
  });

  it('保存失败时弹错误 toast（不上报假成功）', async () => {
    interview.saveInterviewPrepDrafts.mockRejectedValue(new Error('network down'));

    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );

    const textarea = await openQuestionSection();
    fireEvent.change(textarea, { target: { value: '将保存失败的草稿' } });
    fireEvent.click(screen.getByText('保存草稿'));

    await screen.findByText('草稿保存失败');
    expect(interview.saveInterviewPrepDrafts).toHaveBeenCalledWith(7, {
      'q-0': '将保存失败的草稿',
    });
    expect(screen.queryByText('回答草稿已保存')).not.toBeInTheDocument();
  });

  it('useSavePrepDraftsMutation 成功后就地更新 interviews cache 的 prepSource.drafts', async () => {
    interview.saveInterviewPrepDrafts.mockResolvedValue({
      id: 7,
      drafts: { 'q-0': '缓存草稿' },
    });

    const SaveHarness = () => {
      const save = useSavePrepDraftsMutation();
      return (
        <button onClick={() => save.mutateAsync({ prepId: 7, drafts: { 'q-0': '缓存草稿' } })}>
          hook保存
        </button>
      );
    };
    const CachedDrafts = () => {
      const { data: interviews = [] } = useInterviewsQuery();
      return (
        <span data-testid="cached-drafts">
          {JSON.stringify(interviews[0]?.prepSource?.drafts ?? null)}
        </span>
      );
    };

    renderWithProviders(
      <>
        <SaveHarness />
        <CachedDrafts />
      </>
    );

    await waitFor(() =>
      expect(screen.getByTestId('cached-drafts').textContent).toBe('{}')
    );
    fireEvent.click(screen.getByText('hook保存'));
    await waitFor(() =>
      expect(screen.getByTestId('cached-drafts').textContent).toBe('{"q-0":"缓存草稿"}')
    );
    expect(interview.saveInterviewPrepDrafts).toHaveBeenCalledWith(7, { 'q-0': '缓存草稿' });
  });
});

describe('FE-LOGIC-01 前端逻辑 bug 修复', () => {
  it('① 真实 duration 直接展示（|| 先于 ?: 的优先级修复）', async () => {
    renderWithProviders(
      <InterviewPrepWorkspaceView interviewId="prep-7" />
    );

    fireEvent.click(screen.getByText('01 总览'));
    await screen.findByText(/本场面试定位与考察维度研判|核心考察方向拆解/);
    expect(await screen.findByText('预计时长：45分钟')).toBeInTheDocument();
    expect(screen.queryByText('预计时长：见下方说明')).not.toBeInTheDocument();
  });

  it('② 轮次选择第4面（HR面）映射为「第4面 · HR面」而非「终面」', () => {
    const onRoundChange = vi.fn();
    renderWithProviders(
      <InterviewDetailsStep
        stepNumber={1}
        roundNumber={1}
        roundType="tech"
        interviewTime="2026-09-02 10:00"
        interviewFormat="video"
        platform=""
        interviewer=""
        onRoundChange={onRoundChange}
        onRoundTypeChange={vi.fn()}
        onTimeChange={vi.fn()}
        onFormatChange={vi.fn()}
        onPlatformChange={vi.fn()}
        onInterviewerChange={vi.fn()}
      />
    );

    fireEvent.change(screen.getByDisplayValue('第1面'), { target: { value: '4' } });
    expect(onRoundChange).toHaveBeenCalledWith(4, '第4面 · HR面');

    fireEvent.change(screen.getByDisplayValue('第1面'), { target: { value: '5' } });
    expect(onRoundChange).toHaveBeenCalledWith(5, '第5面 · 终面');
  });
});

describe('T-M7-6 公司调研重新调研按钮', () => {
  /** 按钮在 interviews 加载完成前先渲染为 disabled，需等 prepSource 就绪。 */
  async function clickRefresh() {
    const btn = await screen.findByRole('button', { name: /重新调研/ });
    await waitFor(() => expect(btn).toBeEnabled());
    fireEvent.click(btn);
  }

  it('点击「重新调研」调用 force 端点并弹成功 toast', async () => {
    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );

    fireEvent.click(screen.getByText('01 总览'));
    await clickRefresh();

    await waitFor(() =>
      expect(interview.refreshInterviewPrepResearch).toHaveBeenCalledWith(7)
    );
    await screen.findByText('公司调研已更新');
    expect(screen.queryByText('重新调研失败')).not.toBeInTheDocument();
  });

  it('重新调研失败弹错误 toast（不上报假成功）', async () => {
    interview.refreshInterviewPrepResearch.mockRejectedValue(new Error('network down'));

    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );

    fireEvent.click(screen.getByText('01 总览'));
    await clickRefresh();

    await screen.findByText('重新调研失败');
    expect(interview.refreshInterviewPrepResearch).toHaveBeenCalledWith(7);
    expect(screen.queryByText('公司调研已更新')).not.toBeInTheDocument();
  });
});

describe('T-M9-3 演练草稿「沉淀为表达」', () => {
  /** 启用态经历卡（后端 GET /cards 默认 is_active=1 才返回）。 */
  const ACTIVE_CARD = {
    id: 5,
    user_id: 1,
    title: 'RAG 评测体系搭建',
    raw_text: '负责搭建 RAG 离线与在线评测体系',
    tags: ['RAG', '评测'],
    ai_structured: null,
    company: '字节跳动',
    role: 'AI 产品经理',
    period: '2024.06-2025.02',
    source: 'manual',
    card_type: 'project',
    version: 1,
    current_version: 1,
    is_active: true,
    is_confirmed: true,
  };

  /** 进入「02 演练」（服务端草稿已有一条 STAR 文本）并展开沉淀弹层。 */
  async function openSedimentPanel() {
    interview.listInterviewPreps.mockResolvedValue({
      records: [{ ...PREP_RECORD, drafts: { 'q-0': 'STAR：背景→行动→结果' } }],
    });
    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );
    await openQuestionSection();
    const trigger = await screen.findByRole('button', { name: '沉淀为表达' });
    await waitFor(() => expect(trigger).toBeEnabled());
    fireEvent.click(trigger);
    return trigger;
  }

  it('草稿为空时按钮 disabled，输入草稿后可用', async () => {
    renderWithProviders(
      <>
        <InterviewPrepWorkspaceView interviewId="prep-7" />
        <ToastContainer />
      </>
    );

    const textarea = await openQuestionSection();
    const trigger = await screen.findByRole('button', { name: '沉淀为表达' });
    expect(trigger).toBeDisabled();

    fireEvent.change(textarea, { target: { value: '刚写下的草稿' } });
    await waitFor(() => expect(trigger).toBeEnabled());
  });

  it('点击展开弹层：内容预填当前草稿，并懒加载列出启用经历卡', async () => {
    experience.listCards.mockResolvedValue([ACTIVE_CARD]);

    await openSedimentPanel();

    const content = (await screen.findByLabelText(/表达内容/)) as HTMLTextAreaElement;
    expect(content.value).toBe('STAR：背景→行动→结果');

    expect(
      await screen.findByRole('option', { name: /RAG 评测体系搭建/ })
    ).toBeInTheDocument();
    // 未选卡时确认按钮不可提交
    expect(screen.getByRole('button', { name: '确认沉淀' })).toBeDisabled();
  });

  it('选择卡并确认 → createExpression 收到 interview_prep 载荷，成功后 toast 并关闭弹层', async () => {
    experience.listCards.mockResolvedValue([ACTIVE_CARD]);
    experience.createExpression.mockResolvedValue({ id: 11, status: 'candidate' });

    await openSedimentPanel();

    // 等懒加载的经历卡选项就绪后再选卡（否则 select 上没有可选 value）
    await screen.findByRole('option', { name: /RAG 评测体系搭建/ });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: '确认沉淀' }));

    await waitFor(() =>
      expect(experience.createExpression).toHaveBeenCalledWith({
        experience_id: 5,
        type: 'standardized',
        content: 'STAR：背景→行动→结果',
        source_refs: [
          {
            id: 'interview_prep:7:q-0',
            source_type: 'interview_prep',
            source_id: '7',
            locator: 'q-0',
          },
        ],
      })
    );
    await screen.findByText('已沉淀为表达');
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: '确认沉淀' })).not.toBeInTheDocument()
    );
  });

  it('沉淀失败弹错误 toast 且弹层不关（禁止失败报成功）', async () => {
    experience.listCards.mockResolvedValue([ACTIVE_CARD]);
    experience.createExpression.mockRejectedValue(new Error('network down'));

    await openSedimentPanel();

    await screen.findByRole('option', { name: /RAG 评测体系搭建/ });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: '确认沉淀' }));

    await screen.findByText('沉淀失败');
    expect(experience.createExpression).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('已沉淀为表达')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '确认沉淀' })).toBeInTheDocument();
  });
});

