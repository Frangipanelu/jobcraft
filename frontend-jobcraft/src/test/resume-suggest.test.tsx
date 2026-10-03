import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useEffect, useRef } from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';
import { renderWithProviders } from './test-utils';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { ToastContainer } from '../components/common/Toast';
import { useResumesQuery } from '../features/resume/hooks';
import { RESUMES_QUERY_KEY } from '../features/resume/mappers';
import { hydrateResumeSuggestions } from '../utils/resumeSuggestionMapper';
import type {
  DashboardItem,
  ResumeSuggestionWire,
  ResumeVersionWire,
  Submission,
} from '../api/types';
import type { ResumeVersion } from '../types/jobcraft';

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
  listResumeVersions: vi.fn(),
  updateResumeVersion: vi.fn(),
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

/** T-M6-2：简历读写源 = resume_version（id 100 沿用原 submission id 便于断言） */
const VERSION_WIRE: ResumeVersionWire = {
  id: 100,
  user_id: 1,
  job_id: null,
  job_analysis_id: 12,
  direction_id: null,
  version_no: 1,
  version_name: null,
  sections: null,
  resume_markdown: SUBMISSION_DETAIL.resume_markdown,
  selected_for_application: false,
  source_expression_refs: null,
  company: '字节跳动',
  position: 'AI 产品经理',
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
  job.listResumeVersions.mockResolvedValue([VERSION_WIRE]);
  job.updateResumeVersion.mockResolvedValue(VERSION_WIRE);
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
  tasks.runTaskOrSync.mockImplementation(
    async (_type: string, _params: unknown, fallback: () => unknown) => fallback(),
  );
});

/**
 * 水合完成后向 RESUMES cache 注入一条建议（wire → AISuggestion，与 hydrate 同契约）。
 * T-M6-2 起 version 读源不再携带 resume_suggestions，注入用于验证 apply/reject 写路径。
 */
const SuggestionSeeder = ({ wire }: { wire: ResumeSuggestionWire }) => {
  const queryClient = useQueryClient();
  const { data } = useResumesQuery();
  const onceRef = useRef(false);
  const hydrated = data ? '100' in data : false;

  useEffect(() => {
    if (onceRef.current || !hydrated) return;
    const t = setTimeout(() => {
      onceRef.current = true;
      const map =
        queryClient.getQueryData<Record<string, ResumeVersion>>([...RESUMES_QUERY_KEY]) || {};
      const built = map['100'];
      if (!built) return;
      queryClient.setQueryData([...RESUMES_QUERY_KEY], {
        ...map,
        '100': { ...built, aiSuggestions: hydrateResumeSuggestions(built, [wire]) },
      });
    }, 0);
    return () => clearTimeout(t);
  }, [hydrated, wire, queryClient]);

  return null;
};

function renderEditor(wire?: ResumeSuggestionWire) {
  return renderWithProviders(
    <>
      {wire ? <SuggestionSeeder wire={wire} /> : null}
      <ResumeEditorView resumeId="100" />
      <ToastContainer />
    </>,
  );
}

describe('resume-suggest (FE-RESUME-02 · T-M6-2)', () => {
  it('存量建议不再水合：version 读源无建议列 → 面板空态且不走 submission 接口', async () => {
    renderEditor();

    expect(await screen.findByText('尚未生成优化建议')).toBeTruthy();
    expect(screen.getByRole('button', { name: '生成 AI 优化建议' })).toBeTruthy();
    expect(job.getSubmission).not.toHaveBeenCalled();
    expect(job.listResumeVersions).toHaveBeenCalled();
  });

  it('生成建议：暂不可用 → info toast「AI 建议待接入」，不打任务/端点/PATCH', async () => {
    renderEditor();

    expect(await screen.findByText('尚未生成优化建议')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '生成 AI 优化建议' }));

    expect(await screen.findByText('AI 建议待接入')).toBeTruthy();
    expect(tasks.runTaskOrSync).not.toHaveBeenCalled();
    expect(job.suggestResume).not.toHaveBeenCalled();
    expect(job.updateSubmission).not.toHaveBeenCalled();
    expect(job.updateResumeVersion).not.toHaveBeenCalled();
  });

  it('注入 pending 建议 → 应用：updateResumeVersion 仅 PATCH resume_markdown（建议列已剥离）', async () => {
    renderEditor(PENDING_WIRE);

    expect(await screen.findByText(/补充 JD 关键词/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '应用优化' }));

    expect(await screen.findByText('已应用')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateResumeVersion).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('覆盖 3 大维度'),
        }),
      );
    });
    const [, payload] = job.updateResumeVersion.mock.calls.at(-1) as [
      number,
      Record<string, unknown>,
    ];
    expect(payload.resume_suggestions).toBeUndefined();
    expect(job.updateSubmission).not.toHaveBeenCalled();
    expect(screen.getAllByText(/覆盖 3 大维度/).length).toBeGreaterThan(0);
  });

  it('注入 pending 建议 → 忽略：本地标记，不打 PATCH（建议状态暂不持久化）', async () => {
    renderEditor(PENDING_WIRE);

    expect(await screen.findByText(/补充 JD 关键词/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));

    expect(await screen.findByText('已忽略')).toBeTruthy();
    expect(await screen.findByText('已在本地标记忽略，建议域改版完成后将支持同步。')).toBeTruthy();
    expect(job.updateResumeVersion).not.toHaveBeenCalled();
    expect(job.updateSubmission).not.toHaveBeenCalled();
  });

  it('注入定位失败的 pending 建议 → stale「已失效」徽标且应用按钮禁用', async () => {
    renderEditor(STALE_WIRE);

    expect(await screen.findByText(/措辞润色/)).toBeTruthy();
    expect(await screen.findByText('已失效')).toBeTruthy();
    const applyBtn = screen.getByRole('button', { name: '应用优化' }) as HTMLButtonElement;
    expect(applyBtn.disabled).toBe(true);
  });

  it('编辑要点保存 → updateResumeVersion PATCH resume_markdown 真实落库', async () => {
    renderEditor();

    expect(await screen.findByText(BULLET_TEXT)).toBeTruthy();
    fireEvent.click(screen.getByTitle('直接编辑'));
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: '全新要点内容' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(await screen.findByText('全新要点内容')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateResumeVersion).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('全新要点内容'),
        }),
      );
    });
    expect(await screen.findByText('要点已保存')).toBeTruthy();
    expect(job.updateSubmission).not.toHaveBeenCalled();
  });
});
