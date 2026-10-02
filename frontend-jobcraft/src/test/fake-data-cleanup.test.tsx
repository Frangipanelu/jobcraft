import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { InterviewReviewCenterView } from '../components/review/InterviewReviewCenterView';
import { InterviewPrepCenterView } from '../components/interview/InterviewPrepCenterView';
import { InterviewPrepWorkspaceView } from '../components/interview/InterviewPrepWorkspaceView';
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
}));
const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));
const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
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

/** 真实 prep 记录（无公司调研、无伪造指标）——用于 prep 域假数据断言。 */
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
  tasks.runTaskOrSync.mockImplementation(async (_t, _p, fallback) => fallback());
});

describe('FE-FAKE-01 复盘中心不回填硬编码假统计', () => {
  it('空数据下平均得分显示占位符，不出现假指标（反哺率/平均分/最高分/24h 建议）', async () => {
    renderWithProviders(<InterviewReviewCenterView />);

    await waitFor(() =>
      expect(screen.getByText('已完成逐题复盘')).toBeInTheDocument()
    );
    for (const fake of [
      '100% 反哺率',
      '85.0 分',
      '最高 88 分 (字节业务面)',
      '建议 24h 内完成',
    ]) {
      expect(screen.queryByText(fake)).not.toBeInTheDocument();
    }
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('FE-FAKE-01(prep) 面试准备域不回填硬编码假指标（T-M7-2）', () => {
  it('准备中心：备战度=真实已攻克题数占比，无假 40%；AI 模拟面试降级「待开发」', async () => {
    renderWithProviders(<InterviewPrepCenterView onOpenNewInterview={vi.fn()} />);

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    expect(screen.getByText('已攻克 0/1 题')).toBeInTheDocument();
    expect(screen.queryByText('40%')).not.toBeInTheDocument();
    expect(screen.getByText('模拟面试 · 待开发')).toBeInTheDocument();
    // 降级后不存在可点击的模拟面试入口按钮
    expect(screen.queryByRole('button', { name: /模拟面试/ })).not.toBeInTheDocument();
    // 真实入口保留
    expect(screen.getByRole('button', { name: '进入备战' })).toBeInTheDocument();
  });

  it('工作区收敛 3-tab（01 总览 / 02 演练 / 03 模拟），备战度按分区真实计算非伪造 40%', async () => {
    renderWithProviders(<InterviewPrepWorkspaceView interviewId="prep-7" />);

    // 新 3-tab 就位
    expect(await screen.findByRole('button', { name: '01 总览' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '02 演练' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '03 模拟' })).toBeInTheDocument();
    // 旧 5-tab 全部消失
    for (const oldTab of ['01 公司调研', '02 本场判断', '03 维度题准备', '04 面试逐字稿', '05 模拟面试']) {
      expect(screen.queryByRole('button', { name: oldTab })).not.toBeInTheDocument();
    }
    // 三分区均有真实数据 → 100%（真实完成占比）；mappers 不再伪造 40
    expect(await screen.findByText('100%')).toBeInTheDocument();
    expect(screen.queryByText('40%')).not.toBeInTheDocument();
  });

  it('prep 无公司调研时，总览不回填「核心业务线」假背景（mappers 源头已清）', async () => {
    renderWithProviders(<InterviewPrepWorkspaceView interviewId="prep-7" />);

    // 默认停在 01 总览（含公司调研区块）
    expect(await screen.findByRole('button', { name: '01 总览' })).toBeInTheDocument();
    expect(screen.queryByText(/核心业务线/)).not.toBeInTheDocument();
  });
});
