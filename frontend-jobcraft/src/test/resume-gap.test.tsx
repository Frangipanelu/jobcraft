import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeEditorView } from '../components/resume/ResumeEditorView';
import { ToastContainer } from '../components/common/Toast';
import type { CapabilityGapWire, ResumeVersionWire } from '../api/types';

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
const REWRITTEN_TEXT = '主导 RAG 评测体系搭建，覆盖 3 大维度 20+ 指标';

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

/** T-M6-3：简历读写源 = resume_version（关联 job_analysis_id=12 → 缺口任务取数键）。 */
function versionWire(overrides: Partial<ResumeVersionWire> = {}): ResumeVersionWire {
  return {
    id: 100,
    user_id: 1,
    job_id: null,
    job_analysis_id: 12,
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

const GAP_REWRITE: CapabilityGapWire = {
  id: 1,
  dimension: 'D6',
  kind: 'rewrite',
  status: 'weak',
  severity: 'high',
  jd_evidence: '要求有 A/B 实验数据复盘经验',
  current: '现有表述未体现复盘闭环',
  rewrite_hint: '突出实验数据复盘闭环',
  card_id: null,
  note: '',
};

const GAP_EVIDENCE: CapabilityGapWire = {
  id: 2,
  dimension: 'D1',
  kind: 'evidence',
  status: 'missing',
  severity: 'medium',
  jd_evidence: '要求熟练掌握 Go',
  current: '无 Go 项目证据',
  rewrite_hint: '',
  card_id: 55,
  note: '',
};

function analysesResponse(gaps: CapabilityGapWire[]) {
  return {
    analyses: [
      {
        job_analysis_id: 12,
        company: '字节跳动',
        position: 'AI 产品经理',
        jd_text: 'AI 产品经理 JD',
        jd_requirements: {
          hard_skills: [],
          soft_skills: [],
          responsibilities: [],
          keywords: [],
        },
        match_score: 80,
        gap_analysis: '总体匹配良好',
        dimension_requirements: [],
        capability_gaps: gaps,
        created_at: '2026-09-18',
      },
    ],
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
  job.listResumeVersions.mockResolvedValue([versionWire()]);
  job.updateResumeVersion.mockResolvedValue(versionWire());
  job.rewriteResumeBullet.mockResolvedValue({ rewritten_text: REWRITTEN_TEXT });
  job.listJobAnalyses.mockResolvedValue(analysesResponse([GAP_REWRITE, GAP_EVIDENCE]));
  job.listBaseResumes.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
});

function renderEditor() {
  return renderWithProviders(
    <>
      <ResumeEditorView resumeId="100" />
      <ToastContainer />
    </>,
  );
}

describe('resume-gap 缺口任务列（T-M6-3 · M6-Q2）', () => {
  it('版本未关联 JD 分析 → 空态提示「该简历未关联 JD 分析」', async () => {
    job.listResumeVersions.mockResolvedValue([versionWire({ job_analysis_id: null })]);
    job.listJobAnalyses.mockResolvedValue({ analyses: [] });
    renderEditor();

    expect(await screen.findByText('暂无缺口任务')).toBeTruthy();
    expect(screen.getByText(/该简历未关联 JD 分析/)).toBeTruthy();
    expect(job.rewriteResumeBullet).not.toHaveBeenCalled();
  });

  it('已关联但分析无缺口清单 → 空态提示未产出能力缺口', async () => {
    job.listJobAnalyses.mockResolvedValue({ analyses: [] });
    renderEditor();

    expect(await screen.findByText('暂无缺口任务')).toBeTruthy();
    expect(screen.getByText(/该岗位分析未产出能力缺口清单/)).toBeTruthy();
  });

  it('渲染缺口清单：维度/严重度/需补强/可改写/改写方向', async () => {
    renderEditor();

    expect(await screen.findByText('缺口任务 (2)')).toBeTruthy();
    expect(screen.getByText('D6 数据复盘')).toBeTruthy();
    expect(screen.getByText('D1 技术深度')).toBeTruthy();
    expect(screen.getByText('高')).toBeTruthy();
    expect(screen.getByText('需补强')).toBeTruthy();
    expect(screen.getByText('可改写')).toBeTruthy();
    expect(screen.getByText(/要求有 A\/B 实验数据复盘经验/)).toBeTruthy();
    expect(screen.getByText(/突出实验数据复盘闭环/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /去经历资产库补强/ })).toBeTruthy();
  });

  it('中栏未点选要点 → AI 改写提示「请先点选要点」，不打端点', async () => {
    renderEditor();

    fireEvent.click(await screen.findByRole('button', { name: /AI 改写选中要点/ }));

    expect(await screen.findByText('请先点选要点')).toBeTruthy();
    expect(job.rewriteResumeBullet).not.toHaveBeenCalled();
    expect(job.updateResumeVersion).not.toHaveBeenCalled();
  });

  it('点选要点 → AI 改写：rewrite 端点带原文+缺口，PATCH 落库并 toast', async () => {
    renderEditor();

    fireEvent.click(await screen.findByText(BULLET_TEXT));
    fireEvent.click(screen.getByRole('button', { name: /AI 改写选中要点/ }));

    expect(await screen.findByText('已 AI 改写')).toBeTruthy();
    await vi.waitFor(() => {
      expect(job.rewriteResumeBullet).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          original_text: BULLET_TEXT,
          dimension: 'D6',
          gap_current: '现有表述未体现复盘闭环',
          jd_evidence: '要求有 A/B 实验数据复盘经验',
          rewrite_hint: '突出实验数据复盘闭环',
        }),
      );
    });
    await vi.waitFor(() => {
      expect(job.updateResumeVersion).toHaveBeenCalledWith(
        100,
        expect.objectContaining({
          resume_markdown: expect.stringContaining(REWRITTEN_TEXT),
        }),
      );
    });
    expect(job.updateSubmission).not.toHaveBeenCalled();
    expect(await screen.findByText(REWRITTEN_TEXT)).toBeTruthy();
  });

  it('rewrite 失败 → error toast「改写失败」，正文不变', async () => {
    job.rewriteResumeBullet.mockRejectedValue(new Error('改写服务暂不可用'));
    renderEditor();

    fireEvent.click(await screen.findByText(BULLET_TEXT));
    fireEvent.click(screen.getByRole('button', { name: /AI 改写选中要点/ }));

    expect(await screen.findByText('改写失败')).toBeTruthy();
    expect(await screen.findByText('改写服务暂不可用')).toBeTruthy();
    expect(job.updateResumeVersion).not.toHaveBeenCalled();
    expect(screen.getByText(BULLET_TEXT)).toBeTruthy();
  });

  it('evidence 缺口未锚定经历卡 → 跳转按钮禁用', async () => {
    job.listJobAnalyses.mockResolvedValue(
      analysesResponse([{ ...GAP_EVIDENCE, card_id: null }]),
    );
    renderEditor();

    const btn = (await screen.findByRole('button', {
      name: /去经历资产库补强/,
    })) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.title).toContain('未锚定经历卡');
  });
});
