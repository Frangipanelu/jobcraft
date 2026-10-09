import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { InterviewPrepWorkspaceView } from '../components/interview/InterviewPrepWorkspaceView';
import type { CompanyResearchShape, InterviewPrepRecord } from '../api/types';
import researchFixture from '../../../tests/fixtures/company_research_payload.json';

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

/** 共享契约 fixture（与 BE 同一份）→ 新结构 aspects。 */
const NEW_ASPECTS = researchFixture.aspects as CompanyResearchShape['aspects'];

/** 旧缓存自由结构（aspects 缺失的历史形态）。 */
const LEGACY_RESEARCH: CompanyResearchShape = {
  basic: {
    name: '字节跳动',
    full_name: '北京字节跳动科技有限公司',
    description: '人工智能公司',
    founded: '2012-03',
    headquarters: '北京',
    size: '10万+',
    stage: 'Pre-IPO',
    industry: '内容分发',
    website: 'https://www.bytedance.com',
  },
  business: {
    main_business: '智能助手',
    product_names: ['抖音', '今日头条'],
    business_model: '广告+电商',
    target_customers: '大众用户',
    competitors: '快手',
  },
  funding: { latest_round: 'Pre-IPO', investors: '红杉资本', valuation: '未披露' },
  team: { founders: '张一鸣', key_executives: '梁汝波' },
  industry: { sector: '内容分发/短视频', trends: '全面 AI 化', opportunities: '出海', risks: '监管' },
  news: [{ title: '发布新模型', date: '2026-01-15' }],
  sources: ['https://example.com'],
};

function buildRecord(overrides: Partial<InterviewPrepRecord> = {}): InterviewPrepRecord {
  return {
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
        answer_points: ['拆分评测维度'],
        card_ids: [3],
      },
    ],
    full_version: '完整方案',
    html_content: '<div>方案</div>',
    created_at: '2026-09-18T08:30:00',
    company_research: null,
    drafts: {},
    ...overrides,
  };
}

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
  interview.listInterviewPreps.mockResolvedValue({ records: [buildRecord()] });
  tasks.runTaskOrSync.mockImplementation(async (_t, _p, fallback) => fallback());
});

afterEach(() => {
  vi.restoreAllMocks();
});

/** 打开「01 总览」分区并等待公司调研区块就绪。 */
async function openOverview() {
  fireEvent.click(screen.getByText('01 总览'));
  await screen.findByText('公司调研与本场研判');
}

const BIZ_MAIN =
  '主营抖音、今日头条等内容产品，广告与电商为主要盈利方式，核心推荐算法自研';

describe('T-P7-1 工作区公司调研双形渲染', () => {
  it('新结构（cr.aspects 在）渲染 mapper 派生句：概况 / 核心产品 / 商业模式 / 赛道 / 近期动态', async () => {
    interview.listInterviewPreps.mockResolvedValue({
      records: [buildRecord({ company_research: { aspects: NEW_ASPECTS } })],
    });

    renderWithProviders(<InterviewPrepWorkspaceView interviewId="prep-7" />);
    await openOverview();

    // 概况区兜底：background（overview 各条连接）
    expect(await screen.findByText('公司概况')).toBeInTheDocument();
    expect(
      await screen.findByText(
        '字节跳动 2012 年成立于北京，团队规模 10 万+，处于 Pre-IPO 阶段；总部位于北京，在上海、深圳、杭州设有办公地'
      )
    ).toBeInTheDocument();

    // keyProducts 芯片 + coreBusiness 段落（business 前 3 条派生）
    expect(screen.getAllByText(BIZ_MAIN).length).toBeGreaterThan(0);

    // 行业区兜底：relevantBusiness（ecosystem 句）
    expect(screen.getByText('所处赛道')).toBeInTheDocument();
    expect(
      screen.getByText('位于短视频与内容分发赛道头部，海外 TikTok 面临多国监管不确定性（推断）')
    ).toBeInTheDocument();

    // 近期动态（recent 带日期）
    expect(
      await screen.findByText('2026-01-15 发布新一代 AI 编程助手，加码 to B 场景')
    ).toBeInTheDocument();

    // 新结构无 legacy 自由字段 → 裸读行自然隐藏（不崩、不显示占位）
    expect(screen.queryByText('成立时间')).not.toBeInTheDocument();
    expect(screen.queryByText('创始人')).not.toBeInTheDocument();
    expect(screen.queryByText('最新轮次')).not.toBeInTheDocument();
  });

  it('legacy 结构（无 aspects）按原样渲染 InfoRow，且不出现公司概况派生行', async () => {
    interview.listInterviewPreps.mockResolvedValue({
      records: [buildRecord({ company_research: LEGACY_RESEARCH })],
    });

    renderWithProviders(<InterviewPrepWorkspaceView interviewId="prep-7" />);
    await openOverview();

    expect(await screen.findByText('成立时间')).toBeInTheDocument();
    expect(screen.getByText('2012-03')).toBeInTheDocument();
    expect(screen.getByText('总部地点')).toBeInTheDocument();
    expect(screen.getByText('北京')).toBeInTheDocument();

    expect(screen.getByText('所处赛道')).toBeInTheDocument();
    expect(screen.getByText('内容分发/短视频')).toBeInTheDocument();

    expect(screen.getByText('创始人')).toBeInTheDocument();
    expect(screen.getByText('张一鸣')).toBeInTheDocument();

    expect(screen.getByText('最新轮次')).toBeInTheDocument();
    // 新闻素材在 cr.news 与 mapper 派生 recentNews 两处合并（既有行为）
    expect(screen.getAllByText('发布新模型').length).toBeGreaterThan(0);

    // aspects 缺失 → 不渲染新结构派生行
    expect(screen.queryByText('公司概况')).not.toBeInTheDocument();
  });

  it('两者皆缺（company_research 为 null）时不崩，落到既有空态文案', async () => {
    interview.listInterviewPreps.mockResolvedValue({
      records: [buildRecord({ company_research: null })],
    });

    renderWithProviders(<InterviewPrepWorkspaceView interviewId="prep-7" />);
    await openOverview();

    expect(await screen.findByText('暂无可展示的新闻素材。')).toBeInTheDocument();
    expect(screen.getAllByText('待补充').length).toBeGreaterThan(0);
    expect(screen.queryByText('公司概况')).not.toBeInTheDocument();
    expect(screen.queryByText('成立时间')).not.toBeInTheDocument();
  });
});
