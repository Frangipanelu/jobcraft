import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders, createTestQueryClient } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { useGenerateResumeFromJdMutation, useResumesQuery, useUpsertResumeMutation } from '../features/resume/hooks';
import { markdownToResume, resumeToMarkdown } from '../utils/resumeParser';
import type { DashboardItem, ResumeVersionWire, Submission } from '../api/types';
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
  listBaseResumes: vi.fn(),
  listJobAnalyses: vi.fn(),
  listResumeVersions: vi.fn(),
  updateResumeVersion: vi.fn(),
  saveResume: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
}));

const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
}));

vi.mock('../api/auth', async () => ({ ...(await vi.importActual('../api/auth')), ...auth }));
vi.mock('../api/job', async () => ({ ...(await vi.importActual('../api/job')), ...job }));
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
    '### 主导 RAG 评测体系搭建\n' +
    '**背景**：构建离线评测集\n' +
    '**行动**：拆解维度指标\n',
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

/** save-resume 正常产物：含 resume_markdown + resume_version_id（可解析出 ResumeVersion）。 */
const SAVE_OK = {
  file_path: 'resumes/zhang.md',
  file_name: 'zhang.md',
  size_bytes: 1024,
  selected_count: 1,
  resume_version_id: 300,
  resume_markdown: SUBMISSION_DETAIL.resume_markdown,
};

beforeEach(() => {
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  job.getDashboard.mockResolvedValue({ submissions: [DASH] });
  job.getSubmission.mockResolvedValue(SUBMISSION_DETAIL);
  job.updateSubmission.mockResolvedValue({ ok: true });
  job.listResumeVersions.mockResolvedValue([VERSION_WIRE]);
  job.updateResumeVersion.mockResolvedValue(VERSION_WIRE);
  job.saveResume.mockResolvedValue(SAVE_OK);
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
});

const UpsertHarness = () => {
  const upsert = useUpsertResumeMutation();
  const { data = {} } = useResumesQuery();
  return (
    <div>
      <button
        onClick={() => {
          const resume = markdownToResume(SUBMISSION_DETAIL.resume_markdown, {
            position: 'AI 产品经理',
            company: '字节跳动',
            id: '999',
          });
          if (resume) {
            upsert.mutate({ resumeId: '999', resume });
          }
        }}
      >
        并入生成简历
      </button>
      <span data-testid="upsert-count">{Object.keys(data).length}</span>
    </div>
  );
};

const GENERATE_ARGS = {
  jobAnalysisId: 12,
  selectedCardIds: [1, 2],
  position: 'AI 产品经理',
  company: '字节跳动',
};

const GenerateHarness = () => {
  const generate = useGenerateResumeFromJdMutation();
  return (
    <div>
      <button type="button" onClick={() => generate.mutate(GENERATE_ARGS)}>
        生成简历
      </button>
      <span data-testid="gen-status">{generate.status}</span>
    </div>
  );
};

function renderEditor() {
  return renderWithProviders(
    <>
      <ResumeEditorView resumeId="100" />
      <ToastContainer />
    </>,
  );
}

describe('resume-query', () => {
  it('空简历数据渲染空态 CTA', async () => {
    job.listResumeVersions.mockResolvedValue([]);
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
      </>,
    );
    expect(await screen.findByText('尚未生成简历，请先完成简历生成。')).toBeTruthy();
  });

  it('useResumesQuery 水合渲染简历标题与要点', async () => {
    renderEditor();
    expect(await screen.findByText('字节跳动 · AI 产品经理')).toBeTruthy();
    expect(screen.getByText('张三')).toBeTruthy();
    expect(screen.getByText(/主导 RAG 评测体系搭建/)).toBeTruthy();
  });

  it('编辑要点：保存修改后文本更新', async () => {
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByTitle('直接编辑'));
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: '全新要点内容' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(await screen.findByText('全新要点内容')).toBeTruthy();
    expect(screen.queryByText(/拆解维度指标/)).toBeNull();
  });

  it('删除要点：bullet 从正文移除', async () => {
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByTitle('删除要点'));

    await vi.waitFor(() => {
      expect(screen.queryByText(/主导 RAG 评测体系搭建/)).toBeNull();
    });
  });

  it('保存草稿：updateResumeVersion 携带序列化 markdown', async () => {
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));

    await vi.waitFor(() => {
      expect(job.updateResumeVersion).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('主导 RAG 评测体系搭建'),
        }),
      );
    });
    expect(job.updateSubmission).not.toHaveBeenCalled();
  });

  it('upsert：生成简历并入 RESUMES cache', async () => {
    renderWithProviders(
      <>
        <ResumeEditorView resumeId="100" />
        <UpsertHarness />
      </>,
    );
    await screen.findByText(/主导 RAG 评测体系搭建/);
    expect(screen.getByTestId('upsert-count').textContent).toBe('1');

    fireEvent.click(screen.getByRole('button', { name: '并入生成简历' }));

    expect(await screen.findByText('2')).toBeTruthy();
  });
});

describe('FE-RESUME-03 个人信息同步 / 打印导出', () => {
  it('从个人资料同步：profile 非空字段覆盖简历头部并落库', async () => {
    auth.getProfile.mockResolvedValue({
      display_name: '李雷',
      email: 'lilei@example.com',
      phone: '13900001111',
      city: '深圳',
      role: '算法工程师',
      github: 'https://github.com/lilei',
    });
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '同步资料' }));

    expect(await screen.findByText('已同步个人信息')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.updateResumeVersion).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('# 李雷'),
        }),
      );
    });
    expect(job.updateResumeVersion).toHaveBeenCalledWith(
      100,
      expect.objectContaining({
        resume_markdown: expect.stringContaining(
          'GitHub/作品：https://github.com/lilei',
        ),
      }),
    );
  });

  it('profile 无可同步字段：提示且不落库', async () => {
    job.updateResumeVersion.mockClear();
    auth.getCurrentUser.mockResolvedValue({
      id: 1,
      username: '',
      display_name: null,
      email: '',
      role: '',
    });
    auth.getProfile.mockResolvedValue({});
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '同步资料' }));

    expect(await screen.findByText('暂无可同步内容')).toBeTruthy();
    expect(job.updateResumeVersion).not.toHaveBeenCalled();
  });

  it('导出 PDF 打开只读 A4 预览，打印按钮触发 window.print', async () => {
    const printSpy = vi.fn();
    Object.defineProperty(window, 'print', {
      value: printSpy,
      writable: true,
      configurable: true,
    });
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '导出 PDF' }));
    expect(await screen.findByTestId('resume-print-preview')).toBeTruthy();
    expect(screen.getByTestId('resume-a4-page').textContent).toContain('张三');
    expect(screen.getByTestId('resume-a4-page').textContent).toContain(
      '主导 RAG 评测体系搭建',
    );

    fireEvent.click(screen.getByTestId('print-action'));
    expect(printSpy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId('print-preview-close'));
    expect(screen.queryByTestId('resume-print-preview')).toBeNull();
  });
});

describe('FE-RESUME-03 github 解析 / 序列化往返', () => {
  const FALLBACK = { position: 'AI 产品经理', company: '字节跳动', id: '100' };

  it('contact 行含 GitHub/作品 → 解析为 personalInfo.github', () => {
    const md =
      '# 张三\n电话：13812345678 | 邮箱：z@x.com | GitHub/作品：https://github.com/zhang\n求职意向：PM\n\n## 工作经历\n### 字节\n### 做了什么\n';
    const r = markdownToResume(md, FALLBACK);
    expect(r?.personalInfo.github).toBe('https://github.com/zhang');
  });

  it('独立 GitHub/作品 键值行 → 解析为 personalInfo.github', () => {
    const md =
      '# 张三\nGitHub/作品：https://github.com/zhang\n求职意向：PM\n\n## 工作经历\n### 字节\n### 做了什么\n';
    const r = markdownToResume(md, FALLBACK);
    expect(r?.personalInfo.github).toBe('https://github.com/zhang');
  });

  it('resumeToMarkdown 输出 GitHub/作品 片段（往返不丢字段）', () => {
    const md =
      '# 张三\n电话：13812345678 | GitHub/作品：https://github.com/zhang\n求职意向：PM\n\n## 工作经历\n### 字节\n### 做了什么\n';
    const r = markdownToResume(md, FALLBACK);
    expect(r).toBeTruthy();
    expect(resumeToMarkdown(r as ResumeVersion)).toContain(
      'GitHub/作品：https://github.com/zhang',
    );
  });
});

// ---------------------------------------------------------------------------
// T-M6-7/8 终审跟进②：生成简历成功后失效 resume-versions 版本列表
// ---------------------------------------------------------------------------

describe('T-M6-7/8 终审跟进② 生成简历失效 resume-versions', () => {
  function renderGenerate() {
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    renderWithProviders(<GenerateHarness />, { queryClient: qc });
    return invalidateSpy;
  }

  /**
   * 全量 key 纪律：每一次 invalidateQueries 都必须只打 resume-versions——
   * 首元素不是 resume-versions（含无 queryKey 的全量失效）即失败，锁死「禁双 key 合并」。
   * 配合 toHaveBeenCalledWith 保证至少发生一次，避免空数组空真。
   */
  function expectOnlyResumeVersionsInvalidated(spy: ReturnType<typeof renderGenerate>) {
    expect(
      spy.mock.calls.every(([filters]) => filters?.queryKey?.[0] === 'resume-versions'),
    ).toBe(true);
  }

  it('生成成功（返回 {resumeId, resume}）→ invalidateQueries 含 resume-versions key', async () => {
    const invalidateSpy = renderGenerate();

    fireEvent.click(screen.getByRole('button', { name: '生成简历' }));

    await vi.waitFor(() =>
      expect(screen.getByTestId('gen-status').textContent).toBe('success'),
    );
    expect(job.saveResume).toHaveBeenCalledWith(
      expect.objectContaining({ job_analysis_id: 12 }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['resume-versions'] });
    expectOnlyResumeVersionsInvalidated(invalidateSpy);
  });

  it('API 成功但解析失败返回 null（缺 resume_markdown）→ 同样失效', async () => {
    job.saveResume.mockResolvedValue({
      file_path: 'resumes/zhang.md',
      file_name: 'zhang.md',
      size_bytes: 1024,
      selected_count: 1,
      resume_version_id: 300,
    });
    const invalidateSpy = renderGenerate();

    fireEvent.click(screen.getByRole('button', { name: '生成简历' }));

    await vi.waitFor(() =>
      expect(screen.getByTestId('gen-status').textContent).toBe('success'),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['resume-versions'] });
    expectOnlyResumeVersionsInvalidated(invalidateSpy);
  });

  it('saveResume 抛错 → 不失效 resume-versions', async () => {
    job.saveResume.mockRejectedValue(new Error('生成失败'));
    const invalidateSpy = renderGenerate();

    fireEvent.click(screen.getByRole('button', { name: '生成简历' }));

    await vi.waitFor(() =>
      expect(screen.getByTestId('gen-status').textContent).toBe('error'),
    );
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['resume-versions'] });
  });

  it('时序：saveResume 未 resolve 之前不失效，resolve 后才失效', async () => {
    let release: (value: typeof SAVE_OK) => void = () => undefined;
    job.saveResume.mockImplementation(
      () =>
        new Promise<typeof SAVE_OK>((resolve) => {
          release = resolve;
        }),
    );
    const invalidateSpy = renderGenerate();
    const saveCallsBefore = job.saveResume.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: '生成简历' }));

    // 本文件 beforeEach 不清 mock 记录，用增量而非总次数判断本次调用
    await vi.waitFor(() =>
      expect(job.saveResume.mock.calls.length).toBe(saveCallsBefore + 1),
    );
    expect(screen.getByTestId('gen-status').textContent).toBe('pending');
    expect(invalidateSpy).not.toHaveBeenCalled();

    release(SAVE_OK);
    await vi.waitFor(() =>
      expect(screen.getByTestId('gen-status').textContent).toBe('success'),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['resume-versions'] });
    expectOnlyResumeVersionsInvalidated(invalidateSpy);
  });
});