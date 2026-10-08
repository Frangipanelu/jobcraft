import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import {
  HISTORY_PAGE_SIZE,
  JDAnalysisCenterView,
} from '../components/jd/JDAnalysisCenterView';
import { JDReportDetailView } from '../components/jd/JDReportDetailView';
import type { WireJdClassification } from '../api/types';

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
  listJobAnalyses: vi.fn(),
  getDashboard: vi.fn(),
  getSubmission: vi.fn(),
  listBaseResumes: vi.fn(),
  createSubmission: vi.fn(),
  updateSubmission: vi.fn(),
  deleteSubmission: vi.fn(),
  analyzeJob: vi.fn(),
  analyzeStructuredJd: vi.fn(),
  splitJd: vi.fn(),
  saveResume: vi.fn(),
  createBaseResume: vi.fn(),
  deleteBaseResume: vi.fn(),
  setDefaultBaseResume: vi.fn(),
  upsertJdClassification: vi.fn(),
}));

const direction = vi.hoisted(() => ({
  getDirectionSummary: vi.fn(),
  findDirectionOrCreate: vi.fn(),
  suggestDirection: vi.fn(),
  listDirections: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));
vi.mock('../api/direction', () => ({ ...direction }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const CLS_WIRE: WireJdClassification = {
  id: 9,
  job_analysis_id: 12,
  direction_id: 7,
  direction_name: '电商零售',
  direction_code: 'DIR-1',
  job_function: '产品',
  primary_role: 'AI 产品经理',
  industry: '电商与零售',
  product: '交易平台',
  scenario: '交易履约',
  skills: '数据分析',
  confidence: 'low',
  source: 'rule',
  status: 'proposed',
  created_at: '2026-10-01',
  updated_at: '2026-10-01',
};

const NEW_DIRECTION = {
  id: 9,
  user_id: 1,
  code: 'DIR-9',
  name: '人工智能',
  job_function: '产品',
  primary_role: 'AI 产品经理',
  industry: '电商与零售',
  product: '交易平台',
  scenario: '交易履约',
  skills: '数据分析',
  status: 'active' as const,
  created_at: '2026-10-05',
  updated_at: '2026-10-05',
};

/** 列表条目（wire 形状，mock 断言不走 TS 严格校验）。 */
function buildDetail(
  id: number,
  company: string,
  position: string,
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    job_analysis_id: id,
    job_id: id,
    company,
    position,
    jd_text: `${company} 的 JD 原文`,
    jd_requirements: null,
    match_score: 60,
    gap_analysis: `${company} 研判结论`,
    dimension_requirements: [],
    capability_gaps: [],
    created_at: '2026-01-01',
    ...extra,
  };
}

function renderHistory() {
  return renderWithProviders(
    <>
      <JDAnalysisCenterView />
      <ToastContainer />
    </>,
  );
}

function openHistory() {
  fireEvent.click(screen.getByText(/历史研判报告/));
}

beforeEach(() => {
  vi.resetAllMocks();
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  job.listJobAnalyses.mockResolvedValue({ analyses: [] });
  job.deleteSubmission.mockResolvedValue(undefined);
  job.upsertJdClassification.mockResolvedValue({});
  direction.findDirectionOrCreate.mockResolvedValue({
    direction: NEW_DIRECTION,
    created: false,
  });
  direction.suggestDirection.mockResolvedValue({
    matched: true,
    direction_name: '人工智能',
    industry: 'AI 平台',
    product: '大模型应用',
    scenario: '企业智能化',
    skills: '数据分析',
  });
  direction.listDirections.mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ============================================================
// ① 分类列渲染（有名 / 无名）
// ============================================================

describe('历史表格 · 方向分类列（T-M4-4）', () => {
  it('有分类行渲染方向名与来源徽标；无分类行渲染诚实空态 —', async () => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [
        buildDetail(12, '字节跳动', 'AI 产品经理', { jd_classification: CLS_WIRE }),
        buildDetail(13, '腾讯', '策略产品经理', { jd_classification: null }),
      ],
    });
    renderHistory();
    openHistory();

    expect(await screen.findByText('字节跳动')).toBeInTheDocument();
    const cells = screen.getAllByTestId('row-direction');
    expect(cells).toHaveLength(2);
    expect(cells[0].textContent).toContain('电商零售');
    expect(cells[0].textContent).toContain('词典');
    expect(cells[1].textContent).toBe('—');

    // 表头含「方向分类」列
    expect(screen.getByText('方向分类')).toBeInTheDocument();
    // 搜索框只过滤公司/岗位，不参与分类过滤
    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '腾讯' },
    });
    expect(screen.queryByText('字节跳动')).not.toBeInTheDocument();
    expect(screen.getAllByTestId('row-direction')).toHaveLength(1);
  });

  it('manual 来源徽标显示「手动」', async () => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [
        buildDetail(12, '字节跳动', 'AI 产品经理', {
          jd_classification: { ...CLS_WIRE, source: 'manual', status: 'confirmed' },
        }),
      ],
    });
    renderHistory();
    openHistory();

    expect(await screen.findByTestId('row-direction'));
    expect(screen.getByTestId('row-direction').textContent).toContain('手动');
    expect(screen.getByTestId('row-direction').textContent).not.toContain('词典');
  });
});

// ============================================================
// ② 分页切片与控件（翻页 / 越界回退 / 搜索重置页码）
// ============================================================

describe('历史表格 · 客户端分页（T-M4-4）', () => {
  function buildAnalyses(count: number) {
    return {
      analyses: Array.from({ length: count }, (_, i) =>
        buildDetail(100 + i, `公司${String(i + 1).padStart(2, '0')}`, '岗位'),
      ),
    };
  }

  it('超过 pageSize 只渲染一页，第 2 页展示余下行；控件显示第 x/y 页与共 N 条', async () => {
    job.listJobAnalyses.mockResolvedValue(buildAnalyses(13));
    renderHistory();
    openHistory();

    expect(await screen.findByText('公司01')).toBeInTheDocument();
    expect(screen.getByText(`公司${String(HISTORY_PAGE_SIZE).padStart(2, '0')}`)).toBeInTheDocument();
    expect(screen.queryByText('公司11')).not.toBeInTheDocument();
    // 切片边界 = HISTORY_PAGE_SIZE
    expect(document.querySelectorAll('tbody tr')).toHaveLength(HISTORY_PAGE_SIZE);
    expect(screen.getByTestId('jd-history-pagination').textContent).toContain('共 13 条');
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 1/2 页');
    expect(screen.getByTestId('jd-history-prev')).toBeDisabled();
    expect(screen.getByTestId('jd-history-next')).not.toBeDisabled();

    fireEvent.click(screen.getByTestId('jd-history-next'));
    expect(await screen.findByText('公司11')).toBeInTheDocument();
    expect(screen.getByText('公司13')).toBeInTheDocument();
    expect(screen.queryByText('公司01')).not.toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 2/2 页');
    expect(screen.getByTestId('jd-history-prev')).not.toBeDisabled();
    expect(screen.getByTestId('jd-history-next')).toBeDisabled();

    fireEvent.click(screen.getByTestId('jd-history-prev'));
    expect(await screen.findByText('公司01')).toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 1/2 页');
  });

  it('搜索词变化重置到第 1 页', async () => {
    job.listJobAnalyses.mockResolvedValue(buildAnalyses(13));
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('jd-history-next'));
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 2/2 页');

    fireEvent.change(screen.getByPlaceholderText('搜索公司或岗位名称...'), {
      target: { value: '公司13' },
    });
    expect(await screen.findByText('公司13')).toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 1/1 页');
    expect(screen.getByTestId('jd-history-pagination').textContent).toContain('共 1 条');
  });

  it('当前页越界（删除后行数变少）自动回退到最后一页', async () => {
    job.listJobAnalyses.mockResolvedValue(buildAnalyses(12));
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('jd-history-next'));
    expect(await screen.findByText('公司11')).toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 2/2 页');

    // 删掉第 2 页第一行 → 11 条仍 2 页，停在第 2 页
    fireEvent.click(screen.getAllByTitle('删除记录')[0]);
    await waitFor(() => expect(screen.queryByText('公司11')).not.toBeInTheDocument());
    expect(screen.getByText('公司12')).toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 2/2 页');
    expect(job.deleteSubmission).not.toHaveBeenCalled();

    // 再删最后一行 → 10 条只剩 1 页，越界回退
    fireEvent.click(screen.getAllByTitle('删除记录')[0]);
    expect(await screen.findByText('公司01')).toBeInTheDocument();
    expect(screen.queryByText('公司12')).not.toBeInTheDocument();
    expect(screen.getByTestId('jd-history-page-info').textContent).toBe('第 1/1 页');
  });
});

// ============================================================
// ③ 编辑分类弹窗（预填 / 保存入参 / 失败不关弹窗）
// ============================================================

describe('历史表格 · 编辑分类弹窗（T-M4-4）', () => {
  beforeEach(() => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [
        buildDetail(12, '字节跳动', 'AI 产品经理', { jd_classification: CLS_WIRE }),
      ],
    });
  });

  it('打开弹窗预填该行分类（方向名 + 六维）', async () => {
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));

    expect(screen.getByTestId('jd-classification-edit-modal')).toBeInTheDocument();
    expect(screen.getByTestId('cf-direction-name')).toHaveValue('电商零售');
    expect(screen.getByTestId('cf-jobFunction')).toHaveValue('产品');
    expect(screen.getByTestId('cf-primaryRole')).toHaveValue('AI 产品经理');
    expect(screen.getByTestId('cf-industry')).toHaveValue('电商与零售');
    expect(screen.getByTestId('cf-product')).toHaveValue('交易平台');
    expect(screen.getByTestId('cf-scenario')).toHaveValue('交易履约');
    expect(screen.getByTestId('cf-skills')).toHaveValue('数据分析');
    // 预填来源 = rule（词典建议低置信）
    expect(screen.getByTestId('cf-source-badge').textContent).toBe('词典建议 · 低置信');
  });

  it('方向名未变保存 → 保留 direction_id，不发 find-or-create，成功后关弹窗', async () => {
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));
    fireEvent.click(await screen.findByTestId('cf-edit-save'));

    await waitFor(() =>
      expect(job.upsertJdClassification).toHaveBeenCalledWith(12, {
        direction_id: 7,
        job_function: '产品',
        primary_role: 'AI 产品经理',
        industry: '电商与零售',
        product: '交易平台',
        scenario: '交易履约',
        skills: '数据分析',
        confidence: 'low',
        source: 'rule',
        status: 'proposed',
      }),
    );
    expect(direction.findDirectionOrCreate).not.toHaveBeenCalled();
    // 成功：弹窗关闭 + success toast
    await waitFor(() =>
      expect(screen.queryByTestId('jd-classification-edit-modal')).not.toBeInTheDocument(),
    );
    expect(await screen.findByText('方向分类已保存')).toBeInTheDocument();
  });

  it('方向名变化保存 → find-or-create 拿新 direction_id', async () => {
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));
    fireEvent.change(screen.getByTestId('cf-direction-name'), {
      target: { value: '人工智能' },
    });
    fireEvent.click(screen.getByTestId('cf-edit-save'));

    await waitFor(() =>
      expect(direction.findDirectionOrCreate).toHaveBeenCalledWith({
        name: '人工智能',
        job_function: '产品',
        primary_role: 'AI 产品经理',
        industry: '电商与零售',
        product: '交易平台',
        scenario: '交易履约',
        skills: '数据分析',
      }),
    );
    await waitFor(() =>
      expect(job.upsertJdClassification).toHaveBeenCalledWith(
        12,
        expect.objectContaining({
          direction_id: 9,
          confidence: 'high',
          source: 'manual',
          status: 'confirmed',
        }),
      ),
    );
  });

  it('保存失败 → error toast 不静默、弹窗保持打开', async () => {
    job.upsertJdClassification.mockRejectedValue(new Error('方向分类写入失败'));
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));
    fireEvent.click(screen.getByTestId('cf-edit-save'));

    expect(await screen.findByText('方向分类保存失败')).toBeInTheDocument();
    expect(screen.getByTestId('jd-classification-edit-modal')).toBeInTheDocument();
  });

  it('全空输入保存 → 提醒原因且不发请求、不关弹窗', async () => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [buildDetail(12, '字节跳动', 'AI 产品经理', { jd_classification: null })],
    });
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));
    fireEvent.click(await screen.findByTestId('cf-edit-save'));

    expect(await screen.findByText('方向分类未保存：请至少填写方向名或一个分类维度')).toBeInTheDocument();
    expect(job.upsertJdClassification).not.toHaveBeenCalled();
    expect(screen.getByTestId('jd-classification-edit-modal')).toBeInTheDocument();
  });

  it('ESC 关闭弹窗', async () => {
    renderHistory();
    openHistory();

    fireEvent.click(await screen.findByTestId('edit-classification'));
    expect(screen.getByTestId('jd-classification-edit-modal')).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('jd-classification-edit-modal')).not.toBeInTheDocument();
  });
});

// ============================================================
// ④ 报告详情 · 方向分类展示区段（含空态）
// ============================================================

describe('JDReportDetailView · 方向分类区段（T-M4-4）', () => {
  it('有分类 → 渲染方向名、六维、来源/状态徽标', async () => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [
        buildDetail(12, '字节跳动', 'AI 产品经理', { jd_classification: CLS_WIRE }),
      ],
    });
    renderWithProviders(<JDReportDetailView analysisId="12" />);

    const section = await screen.findByTestId('direction-classification');
    expect(section.textContent).toContain('方向分类');
    expect(section.textContent).toContain('电商零售');
    expect(section.textContent).toContain('词典建议');
    expect(section.textContent).toContain('待确认');
    expect(section.textContent).toContain('低置信');
    expect(section.textContent).toContain('行业');
    expect(section.textContent).toContain('电商与零售');
    expect(section.textContent).toContain('技能');
    expect(section.textContent).toContain('数据分析');
    expect(section.textContent).not.toContain('未录入方向分类');
  });

  it('无分类 → 诚实空态「未录入方向分类」，不造假数据', async () => {
    job.listJobAnalyses.mockResolvedValue({
      analyses: [buildDetail(12, '字节跳动', 'AI 产品经理', { jd_classification: null })],
    });
    renderWithProviders(<JDReportDetailView analysisId="12" />);

    const section = await screen.findByTestId('direction-classification');
    expect(section.textContent).toContain('未录入方向分类');
    expect(section.textContent).not.toContain('电商零售');
  });
});
