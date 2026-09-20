import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useEffect, useRef } from 'react';
import { fireEvent, screen } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';
import { renderWithProviders } from './test-utils';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { useResumesQuery, useUpsertResumeMutation } from '../features/resume/hooks';
import { RESUMES_QUERY_KEY } from '../features/resume/mappers';
import { markdownToResume } from '../utils/resumeParser';
import type { DashboardItem, Submission } from '../api/types';
import type { AISuggestion, ResumeVersion } from '../types/jobcraft';

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

const SUGGESTED_TEXT = '主导 RAG 评测体系搭建，覆盖 3 大维度 20+ 指标';

beforeEach(() => {
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  job.getDashboard.mockResolvedValue({ submissions: [DASH] });
  job.getSubmission.mockResolvedValue(SUBMISSION_DETAIL);
  job.updateSubmission.mockResolvedValue({ ok: true });
  job.listBaseResumes.mockResolvedValue([]);
  job.listJobAnalyses.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
});

/**
 * 等 useResumesQuery 水合完成后，向 RESUMES cache 注入一条 AI 优化建议。
 * 解析产物 aiSuggestions 恒为空（resumeParser 不产出建议），注入用于验证建议写路径。
 * onceRef 只注入一次，之后 mutation 的 cache 写入不会被覆盖。
 */
const ResumeSeeder = ({ injectSuggestion = false }: { injectSuggestion?: boolean }) => {
  const queryClient = useQueryClient();
  const { data } = useResumesQuery();
  const onceRef = useRef(false);

  const hydrated = data ? '100' in data : false;

  useEffect(() => {
    if (onceRef.current || !hydrated || !injectSuggestion) return;
    const t = setTimeout(() => {
      onceRef.current = true;
      const map =
        queryClient.getQueryData<Record<string, ResumeVersion>>([...RESUMES_QUERY_KEY]) || {};
      const built = map['100'];
      if (!built) return;
      const work =
        built.sections.find((s) => s.title === '工作经历') || built.sections[0];
      const bullet = work.items[0].bullets[0];
      const suggestion: AISuggestion = {
        id: 's1',
        type: 'polish',
        title: '突出量化结果',
        originalText: bullet.text,
        suggestedText: SUGGESTED_TEXT,
        applied: false,
        rejected: false,
        reason: '补充量化指标提升 ATS 关键词命中率',
        targetBulletId: bullet.id,
      };
      queryClient.setQueryData([...RESUMES_QUERY_KEY], {
        ...map,
        '100': { ...built, aiSuggestions: [suggestion] },
      });
    }, 0);
    return () => clearTimeout(t);
  }, [hydrated, injectSuggestion, queryClient]);

  return null;
};

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

function renderEditor(injectSuggestion = false) {
  return renderWithProviders(
    <>
      <ResumeSeeder injectSuggestion={injectSuggestion} />
      <ResumeEditorView resumeId="100" />
    </>,
  );
}

describe('resume-query', () => {
  it('空简历数据渲染空态 CTA', async () => {
    job.getDashboard.mockResolvedValue({ submissions: [] });
    renderWithProviders(
      <>
        <ResumeSeeder />
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

  it('应用单条 AI 建议：bullet 改写 + 标记已应用', async () => {
    renderEditor(true);
    expect(await screen.findByText(/突出量化结果/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '应用优化' }));

    expect(await screen.findByText('已应用')).toBeTruthy();
    const updated = await screen.findAllByText(SUGGESTED_TEXT);
    expect(updated.length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: '应用优化' })).toBeNull();
  });

  it('忽略建议：标记已忽略且不应用', async () => {
    renderEditor(true);
    expect(await screen.findByText(/突出量化结果/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));

    expect(await screen.findByText('已忽略')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '应用优化' })).toBeNull();
  });

  it('全部应用：批量改写 bullet', async () => {
    renderEditor(true);
    expect(await screen.findByText(/突出量化结果/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '全部应用' }));

    expect(await screen.findByText('已应用')).toBeTruthy();
    const updated = await screen.findAllByText(SUGGESTED_TEXT);
    expect(updated.length).toBeGreaterThan(0);
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

  it('保存草稿：updateSubmission 携带序列化 markdown', async () => {
    renderEditor();
    expect(await screen.findByText(/主导 RAG 评测体系搭建/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }));

    await vi.waitFor(() => {
      expect(job.updateSubmission).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining('主导 RAG 评测体系搭建'),
        }),
      );
    });
  });

  it('upsert：生成简历并入 RESUMES cache', async () => {
    renderWithProviders(
      <>
        <ResumeSeeder />
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