import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '../context/JobCraftContext';
import { ToastContainer } from '../components/common/Toast';
import { ExpressionPanel } from '../components/experiences/ExpressionPanel';
import type { Experience } from '../types/jobcraft';
import type { Expression } from '../api/types';

const api = vi.hoisted(() => ({
  listExpressions: vi.fn(),
  generateExpression: vi.fn(),
  activateExpression: vi.fn(),
  deprecateExpression: vi.fn(),
}));

vi.mock('../api/experience', () => ({ ...api }));

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <ToastProvider>
        {children}
        <ToastContainer />
      </ToastProvider>
    </QueryClientProvider>
  );
  return { wrapper, client };
}

const EXP: Experience = {
  id: '7',
  title: '端侧大模型量化评测',
  category: 'work',
  company: '未来智能实验室',
  role: 'AI 产品经理',
  period: '2025.01 - 2025.08',
  background: '移动端端侧生成式体验的量产方案。',
  problem: '主导从 0 到 1 方案设计与落地。',
  actions: ['建立量产评估体系'],
  results: ['留存 +22.8%'],
  tags: ['端侧大模型'],
  currentVersion: 'V3',
  versionHistory: [],
  isConfirmed: true,
};

const CANDIDATE: Expression = {
  id: 11,
  user_id: 1,
  experience_id: 7,
  type: 'standardized',
  content: '负责端侧大模型量化评测，建立量产评估体系，显著提升留存。',
  version: 2,
  validation_level: 0,
  usage_count: 0,
  source_refs: [],
  status: 'candidate',
};

const ACTIVE: Expression = { ...CANDIDATE, id: 9, version: 1, status: 'active' };

describe('ExpressionPanel（EXP-P2-09）', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('空态展示生成按钮，点击后调用 generate 并显示成功 toast', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [] });
    api.generateExpression.mockResolvedValue(CANDIDATE);
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    expect(await screen.findByText('暂无标准化表达')).toBeInTheDocument();
    fireEvent.click(screen.getByText('AI 生成标准化表达'));
    await waitFor(() => expect(api.generateExpression).toHaveBeenCalledWith(7));
    expect(await screen.findByText('标准化表达已生成')).toBeInTheDocument();
  });

  it('候选表达展示版本链与候选徽标，激活按钮可用', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [CANDIDATE] });
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    expect(await screen.findByText('V2')).toBeInTheDocument();
    expect(screen.getByText('候选')).toBeInTheDocument();
    expect(screen.getByText('激活')).toBeInTheDocument();
    expect(screen.getByText('弃用')).toBeInTheDocument();
  });

  it('激活成功后调用 activate 端点', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [CANDIDATE] });
    api.activateExpression.mockResolvedValue({ ...CANDIDATE, status: 'active' });
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    fireEvent.click(await screen.findByText('激活'));
    await waitFor(() => expect(api.activateExpression).toHaveBeenCalledWith(11));
  });

  it('弃用成功后调用 deprecate 端点', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [ACTIVE] });
    api.deprecateExpression.mockResolvedValue({ ...ACTIVE, status: 'deprecated' });
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    fireEvent.click(await screen.findByText('弃用'));
    await waitFor(() => expect(api.deprecateExpression).toHaveBeenCalledWith(9));
  });

  it('active 表达不显示激活按钮', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [ACTIVE] });
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    expect(await screen.findByText('V1')).toBeInTheDocument();
    expect(screen.getByText('已激活')).toBeInTheDocument();
    expect(screen.queryByText('激活')).not.toBeInTheDocument();
  });

  it('展开 diff 展示原文 vs content 的行级对比', async () => {
    api.listExpressions.mockResolvedValue({ experience_id: 7, items: [CANDIDATE] });
    const { wrapper } = createWrapper();

    render(<ExpressionPanel exp={EXP} />, { wrapper });

    fireEvent.click(await screen.findByText('对比原文'));
    expect(screen.getByText(/行级 diff/)).toBeInTheDocument();
    // 原文基线四槽位文本应出现在 diff 中
    expect(screen.getAllByText(/建立量产评估体系/).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.queryByText('对比原文')).toBeInTheDocument());
  });
});