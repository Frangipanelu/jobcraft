import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, fireEvent, within } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { ToastContainer } from '../components/common/Toast';
import type { ResumeVersionWire } from '../api/types';

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
  rewriteResumeBullet: vi.fn(),
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

const BULLET_TEXT = '主导 RAG 评测体系搭建';

const RESUME_MD =
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
  `### ${BULLET_TEXT}\n`;

/**
 * T-M6-4：结构化 sections JSON（编辑权威）。
 * 含 md 中不存在的条目（腾讯）与隐藏模块（教育经历）——用于证明水合 JSON 优先。
 */
const STRUCTURED_SECTIONS = [
  { id: 'sec-core', title: '核心能力', items: [] },
  {
    id: 'sec-work',
    title: '工作经历',
    items: [
      {
        id: 'item-a',
        title: '字节跳动 · AI 产品经理 · 2022.04-至今',
        bullets: [{ id: 'b1', text: BULLET_TEXT }],
      },
      {
        id: 'item-b',
        title: '腾讯 · 产品经理 · 2019.07-2022.03',
        bullets: [{ id: 'b2', text: '负责社交产品增长' }],
      },
    ],
  },
  {
    id: 'sec-edu',
    title: '教育经历',
    hidden: true,
    items: [
      {
        id: 'item-c',
        title: '北京大学 · 计算机科学 · 2015-2019',
        bullets: [{ id: 'b3', text: '理学学士' }],
      },
    ],
  },
];

function versionWire(overrides: Partial<ResumeVersionWire> = {}): ResumeVersionWire {
  return {
    id: 100,
    user_id: 1,
    job_id: null,
    job_analysis_id: null,
    direction_id: null,
    version_no: 1,
    version_name: null,
    sections: null,
    resume_markdown: RESUME_MD,
    selected_for_application: false,
    source_expression_refs: null,
    company: '字节跳动',
    position: 'AI 产品经理',
    created_at: '2026-09-18T08:00:00',
    updated_at: '2026-09-18T08:00:00',
    ...overrides,
  };
}

/** 最近一次 PATCH 的 payload（updateResumeVersion mock.calls）。 */
function lastPatch() {
  const calls = job.updateResumeVersion.mock.calls;
  expect(calls.length).toBeGreaterThan(0);
  const [versionId, payload] = calls[calls.length - 1];
  expect(versionId).toBe(100);
  return payload as {
    resume_markdown?: string;
    sections?: { id: string; title: string; hidden?: boolean; items: { id: string; title: string; bullets: { id: string; text: string }[] }[] }[];
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  job.getDashboard.mockResolvedValue({ submissions: [] });
  job.getSubmission.mockResolvedValue(null);
  job.updateSubmission.mockResolvedValue({ ok: true });
  job.listResumeVersions.mockResolvedValue([
    versionWire({ sections: STRUCTURED_SECTIONS as unknown }),
  ]);
  job.updateResumeVersion.mockResolvedValue(versionWire());
  job.rewriteResumeBullet.mockResolvedValue({ rewritten_text: 'x' });
  job.listJobAnalyses.mockResolvedValue({ analyses: [] });
  job.listBaseResumes.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderEditor() {
  return renderWithProviders(
    <>
      <ResumeEditorView resumeId="100" />
      <ToastContainer />
    </>,
  );
}

describe('resume-layout 结构化编辑（T-M6-4 · M6-Q6）', () => {
  it('水合 sections JSON 优先：渲染 md 中不存在的条目与隐藏模块徽标', async () => {
    renderEditor();

    expect(await screen.findByText('腾讯 · 产品经理 · 2019.07-2022.03')).toBeTruthy();
    expect(screen.getByText('教育经历')).toBeTruthy();
    expect(screen.getByText('已隐藏')).toBeTruthy();
    expect(screen.getByText('负责社交产品增长')).toBeTruthy();
  });

  it('单击仅选中不进编辑；双击直编保存 → PATCH 双写 sections+markdown', async () => {
    renderEditor();

    fireEvent.click(await screen.findByText(BULLET_TEXT));
    expect(screen.queryByRole('textbox')).toBeNull();

    fireEvent.doubleClick(screen.getByText(BULLET_TEXT));
    const textarea = await screen.findByRole('textbox');
    fireEvent.change(textarea, { target: { value: '双击直编后的新要点' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));

    expect(await screen.findByText('双击直编后的新要点')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.resume_markdown).toContain('双击直编后的新要点');
      expect(payload.sections?.[1].items[0].bullets[0].text).toBe('双击直编后的新要点');
    });
    expect(job.updateSubmission).not.toHaveBeenCalled();
  });

  it('模块 ↑↓：下移工作经历 → sections 顺序交换 + md 同步', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    // 模块序：核心能力 / 工作经历 / 教育经历 → 工作经历下移一位
    fireEvent.click(screen.getAllByTitle('下移模块')[1]);

    expect(await screen.findByText('模块顺序已调整')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.map((s) => s.title)).toEqual([
        '核心能力',
        '教育经历',
        '工作经历',
      ]);
      // md 与 sections 同步：可见的工作经历导出，隐藏的教育经历跳过
      expect(payload.resume_markdown).toContain('## 工作经历');
      expect(payload.resume_markdown).not.toContain('## 教育经历');
    });
  });

  it('模块拖拽：工作经历拖到核心能力上 → 重排落库', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    const work = screen.getByTestId('resume-section-sec-work');
    const core = screen.getByTestId('resume-section-sec-core');
    fireEvent.dragStart(within(work).getByTitle('拖动调整模块顺序'));
    fireEvent.dragOver(core);
    fireEvent.drop(core);

    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.map((s) => s.title)).toEqual([
        '工作经历',
        '核心能力',
        '教育经历',
      ]);
    });
  });

  it('模块显隐：隐藏工作经历 → sections.hidden=true 且导出 md 跳过其内容', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    // 模块序：核心能力 / 工作经历(显示) / 教育经历(已隐藏) → 第二个「隐藏模块」
    fireEvent.click(screen.getAllByTitle('隐藏模块')[1]);

    expect(await screen.findByText('模块已隐藏')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.[1]).toMatchObject({ id: 'sec-work', hidden: true });
      expect(payload.resume_markdown).not.toContain(BULLET_TEXT);
      expect(payload.resume_markdown).not.toContain('腾讯');
    });
    // 教育经历（原已隐藏）+ 工作经历（刚隐藏）两枚徽标
    expect((await screen.findAllByText('已隐藏')).length).toBe(2);
  });

  it('条目 ↑↓：上移第二条 → items 顺序交换', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    const work = screen.getByTestId('resume-section-sec-work');
    fireEvent.click(within(work).getAllByTitle('上移条目')[1]);

    expect(await screen.findByText('条目顺序已调整')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.[1].items.map((i) => i.id)).toEqual(['item-b', 'item-a']);
    });
  });

  it('添加条目：输入标题回车 → items 追加 + toast', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    const work = screen.getByTestId('resume-section-sec-work');
    fireEvent.click(within(work).getByTitle('在该模块末尾添加条目'));
    const input = screen.getByPlaceholderText(/条目标题/);
    fireEvent.change(input, { target: { value: '阿里巴巴 · 产品经理 · 2018.06-2019.06' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(await screen.findByText('条目已添加')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      const items = payload.sections?.[1].items ?? [];
      expect(items).toHaveLength(3);
      expect(items[2].title).toBe('阿里巴巴 · 产品经理 · 2018.06-2019.06');
    });
  });

  it('删除条目：confirm 取消 → 不落库；确认 → items 移除 + toast', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    const work = screen.getByTestId('resume-section-sec-work');
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    fireEvent.click(within(work).getAllByTitle('删除条目')[0]);
    expect(job.updateResumeVersion).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(within(work).getAllByTitle('删除条目')[0]);

    expect(await screen.findByText('条目已删除')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.[1].items.map((i) => i.id)).toEqual(['item-b']);
    });
  });

  it('条目双击标题 → 内联重命名落库', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    fireEvent.doubleClick(screen.getByText('字节跳动 · AI 产品经理 · 2022.04-至今'));
    const input = screen.getByDisplayValue('字节跳动 · AI 产品经理 · 2022.04-至今');
    fireEvent.change(input, { target: { value: '字节跳动 · 高级产品经理 · 2022.04-至今' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(await screen.findByText('条目已更新')).toBeTruthy();
    await vi.waitFor(() => {
      const payload = lastPatch();
      expect(payload.sections?.[1].items[0].title).toBe('字节跳动 · 高级产品经理 · 2022.04-至今');
    });
  });
});

describe('T-M6-5 真下载接线（下载 MD / 下载 HTML）', () => {
  /** jsdom 的 Blob 无 .text()，统一走 FileReader 读文本。 */
  function blobText(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob);
    });
  }

  const createUrlSpy = vi.fn((_content: Blob | string) => 'blob:mock-url');
  const revokeUrlSpy = vi.fn();

  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      value: createUrlSpy,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      value: revokeUrlSpy,
      writable: true,
      configurable: true,
    });
    createUrlSpy.mockClear();
    revokeUrlSpy.mockClear();
    // 文件级 restoreAllMocks 可能清掉 vi.fn 实现 → 每个用例前恢复
    createUrlSpy.mockImplementation(() => 'blob:mock-url');
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  it('顶栏「下载 MD」：导出当前编辑态 markdown 为 .md 文件 + toast', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    fireEvent.click(screen.getByTestId('download-md-action'));

    expect(await screen.findByText('已下载 Markdown')).toBeTruthy();
    expect(createUrlSpy).toHaveBeenCalledTimes(1);
    const blob = createUrlSpy.mock.calls[0][0] as Blob;
    expect(blob.type).toContain('text/markdown');
    const text = await blobText(blob);
    expect(text).toContain('# 张三');
    expect(text).toContain(BULLET_TEXT);
    expect(revokeUrlSpy).toHaveBeenCalledWith('blob:mock-url');
  });

  it('预览「下载 HTML」：A4 页序列化为独立 html 文档', async () => {
    renderEditor();
    await screen.findByText(BULLET_TEXT);

    fireEvent.click(screen.getByRole('button', { name: '导出 PDF' }));
    await screen.findByTestId('resume-print-preview');

    fireEvent.click(screen.getByTestId('download-html-action'));

    // downloadElementAsHtml 为 async（收集样式）→ 等待触发
    await vi.waitFor(() => {
      expect(createUrlSpy).toHaveBeenCalledTimes(1);
    });
    const blob = createUrlSpy.mock.calls[0][0] as Blob;
    expect(blob.type).toContain('text/html');
    const text = await blobText(blob);
    expect(text).toContain('<!DOCTYPE html>');
    expect(text).toContain(BULLET_TEXT);
    expect(text).toContain('张三');
  });
});
