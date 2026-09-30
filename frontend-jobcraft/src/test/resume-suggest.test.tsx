import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { ToastContainer } from '../components/common/Toast';
import type { DashboardItem, ResumeSuggestionWire, Submission } from '../api/types';

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
  updateSubmission: vi.fn(),
  suggestResume: vi.fn(),
  listBaseResumes: vi.fn(),
  listJobAnalyses: vi.fn(),
}));

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
  submitTask: vi.fn(),
  getTask: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
}));

const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
}));

vi.mock('../api/auth', async () => ({ ...(await vi.importActual('../api/auth')), ...auth }));
vi.mock('../api/job', async () => ({ ...(await vi.importActual('../api/job')), ...job }));
vi.mock('../api/tasks', async () => ({ ...(await vi.importActual('../api/tasks')), ...tasks }));
vi.mock('../api/experience', async () => ({
  ...(await vi.importActual('../api/experience')),
  ...experience,
}));
vi.mock('../api/interview', async () => ({
  ...(await vi.importActual('../api/interview')),
  ...interview,
}));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const DASH: DashboardItem = {
  id: 100,
  company: '字节跳动',
  position: 'AI 产品经理',
  status: 'APPLIED',
  job_analysis_id: 12,
  has_analysis: true,
  card_version_count: 3,
  card_count: 3,
  has_resume: true,
  is_manual: false,
  delivered: false,
  prep_count: 0,
  review_count: 0,
  created_at: '2026-09-18T08:00:00',
  updated_at: '2026-09-18T08:00:00',
};

const BULLET_TEXT = '主导 RAG 评测体系搭建';

const SUBMISSION_DETAIL: Submission = {
  id: 100,
  user_id: 1,
  job_analysis_id: 12,
  company: '字节跳动',
  position: 'AI 产品经理',
  jd_text: 'AI 产品经理 JD',
  resume_markdown:
    '# 张三\n' +
    '电话：13812345678 | 邮箱：zhang@x.com\n' +
    '求职意向：AI 产品经理\n' +
    '目标公司：字节跳动\n' +
    '更新日期：2026-09-19\n' +
    '\n' +
    '## 核心能力\n' +
    'A、B、C\n' +
    '\n' +
    '## 工作经历\n' +
    '### 字节跳动 · AI 产品经理 · 2022.04-至今\n' +
    `### ${BULLET_TEXT}\n`,
  resume_file_path: null,
  card_version_ids: [1, 2, 3],
  status: 'APPLIED',
  notes: '',
  delivered: false,
  created_at: '2026-09-18T08:00:00',
  updated_at: '2026-09-18T08:00:00',
};

const PENDING_WIRE: ResumeSuggestionWire = {
  id: 'sg_test01',
  type: 'keyword',
  title: '补充 JD 关键词',
  original_text: BULLET_TEXT,
  suggested_text: `${BULLET_TEXT}，覆盖 3 大维度 20+ 指标`,
  reason: '缺失岗位关键词',
  item_index: 0,
  bullet_index: 0,
  status: 'pending',
};

const STALE_WIRE: ResumeSuggestionWire = {
  id: 'sg_stale1',
  type: 'polish',
  title: '措辞润色',
  original_text: '已被删除的旧要点原文',
  suggested_text: '改写后的要点',
  reason: '原文已不存在',
  item_index: 9,
  bullet_index: 9,
  status: 'pending',
};

beforeEach(() => {
  vi.clearAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  job.getDashboard.mockResolvedValue({ submissions: [DASH] });
  job.getSubmission.mockResolvedValue(SUBMISSION_DETAIL);
  job.updateSubmission.mockResolvedValue({ ok: true });
  job.suggestResume.mockResolvedValue({ suggestions: [PENDING_WIRE] });
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
  tasks.runTaskOrSync.mockImplementation(
    async (_type: string, _params: unknown, fallback: () => unknown) => fallback(),
  );
});

describe('resume-suggest (FE-RESUME-02)', () => {
  it('水合存量 pending 建议并应用 → PATCH resume_markdown + resume_suggestions(applied)', async () => {
    job.getSubmission.mockResolvedValue({
      ...SUBMISSION_DETAIL,
      resume_suggestions: [PENDING_WIRE],
    });
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText(/补充 JD 关键词/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '应用优化' }));

    expect(await screen.findByText('已应用')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateSubmission).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('覆盖 3 大维度'),
          resume_suggestions: expect.arrayContaining([
            expect.objectContaining({ id: 'sg_test01', status: 'applied' }),
          ]),
        }),
      );
    });
    expect(screen.getAllByText(/覆盖 3 大维度/).length).toBeGreaterThan(0);
  });

  it('定位失败的 pending 建议 → stale「已失效」徽标且应用按钮禁用', async () => {
    job.getSubmission.mockResolvedValue({
      ...SUBMISSION_DETAIL,
      resume_suggestions: [STALE_WIRE],
    });
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText(/措辞润色/)).toBeTruthy();
    expect(await screen.findByText('已失效')).toBeTruthy();
    const applyBtn = screen.getByRole('button', { name: '应用优化' }) as HTMLButtonElement;
    expect(applyBtn.disabled).toBe(true);
  });

  it('生成建议：runTaskOrSync(resume_suggest) → 降级端点 → PATCH resume_suggestions 落库', async () => {
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText('尚未生成优化建议')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '生成 AI 优化建议' }));

    expect(await screen.findByText(/补充 JD 关键词/)).toBeTruthy();
    await vi.waitFor(() => {
      expect(tasks.runTaskOrSync).toHaveBeenCalledWith(
        'resume_suggest',
        expect.objectContaining({
          submission_id: 100,
          user_id: 1,
          bullets: [{ item_index: 0, bullet_index: 0, text: BULLET_TEXT }],
        }),
        expect.any(Function),
        { timeout: 120_000 },
      );
      expect(job.suggestResume).toHaveBeenCalledWith(100, [
        { item_index: 0, bullet_index: 0, text: BULLET_TEXT },
      ]);
      expect(job.updateSubmission).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_suggestions: expect.arrayContaining([
            expect.objectContaining({ id: 'sg_test01', status: 'pending' }),
          ]),
        }),
      );
    });
    expect(await screen.findByText('优化建议已生成')).toBeTruthy();
  });

  it('忽略建议 → 仅 PATCH resume_suggestions(rejected)，不带正文', async () => {
    job.getSubmission.mockResolvedValue({
      ...SUBMISSION_DETAIL,
      resume_suggestions: [PENDING_WIRE],
    });
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText(/补充 JD 关键词/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));

    expect(await screen.findByText('已忽略')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateSubmission).toHaveBeenCalledTimes(1);
      const [, payload] = job.updateSubmission.mock.calls.at(-1) as [number, Record<string, unknown>];
      expect(payload.resume_markdown).toBeUndefined();
      expect(payload.resume_suggestions).toEqual([
        expect.objectContaining({ id: 'sg_test01', status: 'rejected' }),
      ]);
    });
  });

  it('编辑要点保存 → PATCH resume_markdown 真实落库（修「假 toast」）', async () => {
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText(BULLET_TEXT)).toBeTruthy();
    fireEvent.click(screen.getByTitle('直接编辑'));
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: '全新要点内容' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(await screen.findByText('全新要点内容')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateSubmission).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('全新要点内容'),
        }),
      );
    });
    expect(await screen.findByText('要点已保存')).toBeTruthy();
  });
});
