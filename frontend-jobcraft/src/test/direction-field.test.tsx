import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { JDAnalysisCenterView } from '../components/jd/JDAnalysisCenterView';
import { JDClassificationSection } from '../components/jd/JDClassificationSection';
import {
  EMPTY_CLASSIFICATION,
  submitClassification,
} from '../features/jd/classification';
import type { ClassificationValue } from '../features/jd/classification';
import type { JobAnalysisResult, ATSProfile } from '../api/types';

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

const tasks = vi.hoisted(() => ({
  runTaskOrSync: vi.fn(),
}));

const direction = vi.hoisted(() => ({
  getDirectionSummary: vi.fn(),
  findDirectionOrCreate: vi.fn(),
  suggestDirection: vi.fn(),
  listDirections: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));
vi.mock('../api/tasks', () => ({ ...tasks }));
vi.mock('../api/direction', () => ({ ...direction }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const SUGGEST_HIT = {
  matched: true,
  direction_name: '电商零售',
  industry: '电商与零售',
  product: '交易平台与商家经营工具',
  scenario: '交易履约、商家增长、选品定价',
  skills: '交易链路设计、商家侧增长、数据分析',
};

const EXISTING_DIRECTION = {
  id: 7,
  user_id: 1,
  code: 'DIR-1',
  name: '电商零售',
  job_function: '产品',
  primary_role: '',
  industry: '电商与零售',
  product: '',
  scenario: '',
  skills: '',
  status: 'active' as const,
  created_at: '2026-10-01',
  updated_at: '2026-10-01',
};

function buildResult(overrides: Partial<JobAnalysisResult> = {}): JobAnalysisResult {
  return {
    job_analysis_id: 12,
    user_id: 1,
    company: '字节跳动',
    position: 'AI 产品经理',
    jd_text: '原始 JD 文本',
    jd_requirements: null,
    ats_profile: null,
    company_context: null,
    match_score: 60,
    match_level: '中匹配',
    customization_needed: false,
    gap_analysis: '整体匹配待补充',
    gap_items: [],
    per_card_scores: [],
    suggestions: [],
    dimension_requirements: [],
    resume_markdown: null,
    created_at: '2026-10-04',
    ...overrides,
  } as JobAnalysisResult;
}

function fillBaseForm() {
  fireEvent.change(screen.getByPlaceholderText('例如：字节跳动、腾讯、某独角兽'), {
    target: { value: '字节跳动' },
  });
  fireEvent.change(screen.getByPlaceholderText('例如：AI 产品经理、算法专家'), {
    target: { value: '跨境电商产品经理' },
  });
  fireEvent.change(screen.getByPlaceholderText(/每行一条职责/), {
    target: { value: '负责跨境电商 GMV 增长' },
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  job.listJobAnalyses.mockResolvedValue({ analyses: [] });
  job.deleteSubmission.mockResolvedValue(undefined);
  job.upsertJdClassification.mockResolvedValue({});
  tasks.runTaskOrSync.mockResolvedValue(buildResult());
  direction.suggestDirection.mockResolvedValue(SUGGEST_HIT);
  direction.findDirectionOrCreate.mockResolvedValue({
    direction: EXISTING_DIRECTION,
    created: false,
  });
  direction.listDirections.mockResolvedValue([EXISTING_DIRECTION]);
});

// ============================================================
// 1. 组件层：JDClassificationSection 交互
// ============================================================

describe('JDClassificationSection（T-M4-3 方向分类区块）', () => {
  it('渲染六维 + 方向名 + 手动来源徽标；编辑回传 patch', () => {
    const onChange = vi.fn();
    renderWithProviders(
      <JDClassificationSection
        value={EMPTY_CLASSIFICATION}
        source="manual"
        suggesting={false}
        suggestDisabled={false}
        onChange={onChange}
        onSuggest={vi.fn()}
      />,
    );

    expect(screen.getByTestId('jd-classification')).toBeInTheDocument();
    expect(screen.getByTestId('cf-source-badge').textContent).toBe('手动填写');
    for (const key of ['jobFunction', 'primaryRole', 'industry', 'product', 'scenario', 'skills']) {
      expect(screen.getByTestId(`cf-${key}`)).toBeInTheDocument();
    }

    fireEvent.change(screen.getByTestId('cf-industry'), { target: { value: '电商' } });
    expect(onChange).toHaveBeenCalledWith({ industry: '电商' });
  });

  it('rule 来源徽标显示低置信提示；词典建议按钮触发 onSuggest', () => {
    const onSuggest = vi.fn();
    renderWithProviders(
      <JDClassificationSection
        value={EMPTY_CLASSIFICATION}
        source="rule"
        suggesting={false}
        suggestDisabled={false}
        onChange={vi.fn()}
        onSuggest={onSuggest}
      />,
    );

    expect(screen.getByTestId('cf-source-badge').textContent).toBe('词典建议 · 低置信');
    fireEvent.click(screen.getByTestId('cf-suggest'));
    expect(onSuggest).toHaveBeenCalledTimes(1);
  });

  it('suggestDisabled / suggesting 时建议按钮禁用', () => {
    const { rerender } = renderWithProviders(
      <JDClassificationSection
        value={EMPTY_CLASSIFICATION}
        source="manual"
        suggesting={false}
        suggestDisabled
        onChange={vi.fn()}
        onSuggest={vi.fn()}
      />,
    );
    expect(screen.getByTestId('cf-suggest')).toBeDisabled();

    rerender(
      <JDClassificationSection
        value={EMPTY_CLASSIFICATION}
        source="manual"
        suggesting
        suggestDisabled={false}
        onChange={vi.fn()}
        onSuggest={vi.fn()}
      />,
    );
    expect(screen.getByTestId('cf-suggest')).toBeDisabled();
  });

  it('方向名首次聚焦懒加载已有方向 → datalist 补全', async () => {
    const { container } = renderWithProviders(
      <JDClassificationSection
        value={EMPTY_CLASSIFICATION}
        source="manual"
        suggesting={false}
        suggestDisabled={false}
        onChange={vi.fn()}
        onSuggest={vi.fn()}
      />,
    );

    fireEvent.focus(screen.getByTestId('cf-direction-name'));
    await waitFor(() => expect(direction.listDirections).toHaveBeenCalledWith('active'));
    // jsdom 不把 datalist 内 option 暴露为 role=option，直接查 datalist 子节点
    await waitFor(() => {
      const options = container.querySelectorAll('#cf-direction-options option');
      expect(options.length).toBe(1);
      expect(options[0].getAttribute('value')).toBe('电商零售');
    });
  });
});

// ============================================================
// 2. 提交链 helper：submitClassification
// ============================================================

describe('submitClassification（提交链：find-or-create → upsert）', () => {
  const VALUE: ClassificationValue = {
    directionName: '',
    jobFunction: '',
    primaryRole: '',
    industry: '电商与零售',
    product: '',
    scenario: '',
    skills: '数据分析',
  };

  it('无任何输入 → skipped，零 API 调用', async () => {
    const result = await submitClassification(12, EMPTY_CLASSIFICATION, 'manual');
    expect(result).toEqual({ status: 'skipped' });
    expect(direction.findDirectionOrCreate).not.toHaveBeenCalled();
    expect(job.upsertJdClassification).not.toHaveBeenCalled();
  });

  it('有维度无方向名（manual）→ upsert direction_id=null + high/confirmed', async () => {
    const result = await submitClassification(12, VALUE, 'manual');
    expect(result.status).toBe('saved');
    expect(direction.findDirectionOrCreate).not.toHaveBeenCalled();
    expect(job.upsertJdClassification).toHaveBeenCalledWith(12, {
      direction_id: null,
      job_function: '',
      primary_role: '',
      industry: '电商与零售',
      product: '',
      scenario: '',
      skills: '数据分析',
      confidence: 'high',
      source: 'manual',
      status: 'confirmed',
    });
  });

  it('有方向名（rule）→ find-or-create 播种维度 + upsert low/proposed', async () => {
    const result = await submitClassification(
      12,
      { ...VALUE, directionName: '电商零售' },
      'rule',
    );
    expect(result.status).toBe('saved');
    expect(direction.findDirectionOrCreate).toHaveBeenCalledWith({
      name: '电商零售',
      industry: '电商与零售',
      skills: '数据分析',
    });
    expect(job.upsertJdClassification).toHaveBeenCalledWith(
      12,
      expect.objectContaining({
        direction_id: 7,
        industry: '电商与零售',
        confidence: 'low',
        source: 'rule',
        status: 'proposed',
      }),
    );
  });

  it('只填方向名 → 回退方向自带画像维度，落库', async () => {
    const result = await submitClassification(
      12,
      { ...EMPTY_CLASSIFICATION, directionName: '电商零售' },
      'manual',
    );
    expect(result.status).toBe('saved');
    expect(job.upsertJdClassification).toHaveBeenCalledWith(
      12,
      expect.objectContaining({
        direction_id: 7,
        job_function: '产品',
        industry: '电商与零售',
      }),
    );
  });

  it('只填方向名且方向无画像 → skipped + 提醒原因，不写分类行', async () => {
    direction.findDirectionOrCreate.mockResolvedValue({
      direction: { ...EXISTING_DIRECTION, job_function: '', industry: '', product: '', scenario: '', skills: '', primary_role: '' },
      created: false,
    });
    const result = await submitClassification(
      12,
      { ...EMPTY_CLASSIFICATION, directionName: '空画像方向' },
      'manual',
    );
    expect(result.status).toBe('skipped');
    expect(result.reason).toContain('至少填写一个分类维度');
    expect(job.upsertJdClassification).not.toHaveBeenCalled();
  });

  it('upsert 失败原样上抛（调用方 error toast）', async () => {
    job.upsertJdClassification.mockRejectedValue(new Error('boom'));
    await expect(submitClassification(12, VALUE, 'manual')).rejects.toThrow('boom');
  });
});

// ============================================================
// 3. 视图集成：词典建议 → 提交链 → 分类落库
// ============================================================

describe('JDAnalysisCenterView 接线（词典建议 → 提交链）', () => {
  it('建议按钮回填四维+方向名，提交后按 rule 落库并提示', async () => {
    renderWithProviders(<JDAnalysisCenterView />);
    fillBaseForm();

    fireEvent.click(screen.getByTestId('cf-suggest'));
    await waitFor(() => expect(direction.suggestDirection).toHaveBeenCalledTimes(1));
    const suggestText = direction.suggestDirection.mock.calls[0][0] as string;
    expect(suggestText).toContain('跨境电商产品经理');
    expect(suggestText).toContain('负责跨境电商 GMV 增长');

    await screen.findByTestId('cf-source-badge');
    expect(screen.getByTestId('cf-source-badge').textContent).toBe('词典建议 · 低置信');
    expect(screen.getByTestId('cf-industry')).toHaveValue('电商与零售');
    expect(screen.getByTestId('cf-direction-name')).toHaveValue('电商零售');

    fireEvent.click(screen.getByText('开始结构化深度研判 →'));

    await waitFor(() =>
      expect(direction.findDirectionOrCreate).toHaveBeenCalledWith({
        name: '电商零售',
        industry: '电商与零售',
        product: '交易平台与商家经营工具',
        scenario: '交易履约、商家增长、选品定价',
        skills: '交易链路设计、商家侧增长、数据分析',
      }),
    );
    await waitFor(() =>
      expect(job.upsertJdClassification).toHaveBeenCalledWith(
        12,
        expect.objectContaining({
          direction_id: 7,
          industry: '电商与零售',
          confidence: 'low',
          source: 'rule',
          status: 'proposed',
        }),
      ),
    );

    // 提交后表单复位（含分类区）
    await waitFor(() =>
      expect(screen.getByTestId('cf-industry')).toHaveValue(''),
    );
  });

  it('手动填写分类（无建议）→ 按 manual 落库且不查方向', async () => {
    renderWithProviders(<JDAnalysisCenterView />);
    fillBaseForm();

    fireEvent.change(screen.getByTestId('cf-industry'), {
      target: { value: '企业服务' },
    });

    fireEvent.click(screen.getByText('开始结构化深度研判 →'));

    await waitFor(() =>
      expect(job.upsertJdClassification).toHaveBeenCalledWith(
        12,
        expect.objectContaining({
          direction_id: null,
          industry: '企业服务',
          confidence: 'high',
          source: 'manual',
          status: 'confirmed',
        }),
      ),
    );
    expect(direction.findDirectionOrCreate).not.toHaveBeenCalled();
    expect(direction.suggestDirection).not.toHaveBeenCalled();
  });

  it('分类留空 → 提交链整体跳过（不触发方向/分类 API）', async () => {
    renderWithProviders(<JDAnalysisCenterView />);
    fillBaseForm();

    fireEvent.click(screen.getByText('开始结构化深度研判 →'));

    await waitFor(() => expect(tasks.runTaskOrSync).toHaveBeenCalledTimes(1));
    expect(direction.findDirectionOrCreate).not.toHaveBeenCalled();
    expect(job.upsertJdClassification).not.toHaveBeenCalled();
  });

  it('词典未命中 → info 提示且来源保持手动', async () => {
    direction.suggestDirection.mockResolvedValue({
      matched: false,
      direction_name: '',
      industry: '',
      product: '',
      scenario: '',
      skills: '',
    });
    renderWithProviders(<JDAnalysisCenterView />);
    fillBaseForm();

    fireEvent.click(screen.getByTestId('cf-suggest'));

    await waitFor(() => expect(direction.suggestDirection).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('cf-source-badge').textContent).toBe('手动填写');
    expect(screen.getByTestId('cf-industry')).toHaveValue('');
  });
});
