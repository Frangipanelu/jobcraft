import { describe, expect, it, vi, beforeEach } from 'vitest';
import { renderWithProviders } from './test-utils';
import { DirectionInsightPanel } from '../components/workbench/DirectionInsightPanel';
import { WorkbenchView } from '../components/workbench/WorkbenchView';
import * as directionApi from '../api/direction';
import type { DirectionSummary } from '../api/direction';

vi.mock('../api/direction', () => ({
  getDirectionSummary: vi.fn(),
}));

const getDirectionSummary = vi.mocked(directionApi.getDirectionSummary);

const FULL: DirectionSummary = {
  directions: [
    {
      id: 1,
      code: 'DIR-1',
      name: '策略运营-跨境电商',
      status: 'active',
      expression_count: 5,
      jd_classification_count: 2,
    },
    {
      id: 2,
      code: 'DIR-2',
      name: '旧方向',
      status: 'archived',
      expression_count: 0,
      jd_classification_count: 0,
    },
  ],
  top_gaps: [
    { dimension: 'D6', count: 5 },
    { dimension: 'EXT', count: 1 },
  ],
};

describe('DirectionInsightPanel（T-M3-6 方向沉淀）', () => {
  beforeEach(() => {
    getDirectionSummary.mockReset();
  });

  it('渲染方向列表（code/名称/表达计数）与高频缺口（维度中文词表）', async () => {
    getDirectionSummary.mockResolvedValue(FULL);
    const ui = renderWithProviders(<DirectionInsightPanel />);

    expect(await ui.findByText('方向沉淀')).toBeInTheDocument();
    expect(ui.getByTestId('direction-insight')).toBeInTheDocument();
    expect(ui.getByText('策略运营-跨境电商')).toBeInTheDocument();
    expect(ui.getByTestId('direction-1-expressions').textContent).toContain('5');
    expect(ui.getByTestId('direction-1-expressions').textContent).toContain('条表达');
    expect(ui.getByText('已归档')).toBeInTheDocument();
    // 维度词表复用 utils/dimensions（D6 → 数据复盘，EXT 原样）
    expect(ui.getByText('D6 数据复盘')).toBeInTheDocument();
    expect(ui.getByTestId('gap-D6').textContent).toContain('5');
    expect(ui.getByTestId('gap-EXT').textContent).toContain('缺口 1');
  });

  it('双空（无方向且缺口缺表降级）→ 段落空态提示而非报错', async () => {
    getDirectionSummary.mockResolvedValue({ directions: [], top_gaps: [] });
    const ui = renderWithProviders(<DirectionInsightPanel />);

    expect(await ui.findByText('尚无方向，完成一次 JD 分析后将自动沉淀。')).toBeInTheDocument();
    expect(
      ui.getByText('暂无缺口数据，完成一次 JD 分析后这里会显示待补齐的能力项。'),
    ).toBeInTheDocument();
  });

  it('加载中 → 骨架提示', () => {
    getDirectionSummary.mockReturnValue(new Promise(() => {}));
    const ui = renderWithProviders(<DirectionInsightPanel />);
    expect(ui.getByText('正在加载方向沉淀…')).toBeInTheDocument();
  });

  it('接口失败 → 面板静默隐藏（不阻断工作台主体）', async () => {
    getDirectionSummary.mockRejectedValue(new Error('boom'));
    const ui = renderWithProviders(<DirectionInsightPanel />);
    await vi.waitFor(() => {
      expect(ui.queryByTestId('direction-insight')).toBeNull();
    });
  });
});

describe('WorkbenchView 接线', () => {
  beforeEach(() => {
    getDirectionSummary.mockReset();
  });

  it('方向沉淀区块出现在工作台内（区块数据由 /direction/summary 提供）', async () => {
    getDirectionSummary.mockResolvedValue(FULL);
    const ui = renderWithProviders(<WorkbenchView onOpenNewJob={() => {}} />);
    expect(await ui.findByText('策略运营-跨境电商')).toBeInTheDocument();
    expect(getDirectionSummary).toHaveBeenCalledTimes(1);
    expect(ui.getByTestId('direction-insight')).toBeInTheDocument();
  });
});
