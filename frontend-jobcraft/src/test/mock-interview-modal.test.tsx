import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders, createTestQueryClient } from './test-utils';
import { MockInterviewModal } from '../components/interview/MockInterviewModal';

const auth = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
}));
const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
  mockChat: vi.fn(),
  createInterviewReview: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/interview', () => ({ ...interview }));

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue({ id: 1 });
  interview.listInterviewPreps.mockResolvedValue({ records: [] });
});

describe('FE-MOCK-01 模拟面试启动失败必须显式报错', () => {
  it('启动失败不伪造面试官开场白，展示错误态并禁用发送', async () => {
    interview.mockChat.mockRejectedValue(new Error('后端服务不可用'));

    renderWithProviders(<MockInterviewModal isOpen onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText(/模拟面试启动失败/)).toBeInTheDocument()
    );
    expect(
      screen.queryByText(/你好，请做一个简短的自我介绍/)
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/输入你的现场回答/), {
      target: { value: '我的自我介绍' },
    });
    expect(
      screen.getByRole('button', { name: /发送回答/ })
    ).toBeDisabled();
  });

  it('重试成功后展示真实开场白并恢复发送', async () => {
    interview.mockChat.mockRejectedValueOnce(new Error('临时故障'));

    renderWithProviders(<MockInterviewModal isOpen onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText('重试连接')).toBeInTheDocument()
    );

    interview.mockChat.mockResolvedValue({ reply: '真实开场白：请做自我介绍' });
    fireEvent.click(screen.getByText('重试连接'));

    await waitFor(() =>
      expect(screen.getByText(/真实开场白/)).toBeInTheDocument()
    );
    fireEvent.change(screen.getByPlaceholderText(/输入你的现场回答/), {
      target: { value: '我的自我介绍' },
    });
    expect(
      screen.getByRole('button', { name: /发送回答/ })
    ).toBeEnabled();
  });
});

describe('FE-LAYER-01 模拟面试复盘保存必须失效 INTERVIEWS 列表', () => {
  it('完成并生成复盘：createInterviewReview 落库后 invalidate ["interviews"]', async () => {
    interview.mockChat.mockResolvedValue({ reply: '开场白：请做自我介绍' });
    interview.createInterviewReview.mockResolvedValue({ record_id: 9, qa_pair_count: 2 });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');

    renderWithProviders(<MockInterviewModal isOpen onClose={vi.fn()} />, { queryClient: qc });

    await screen.findByText(/开场白/);
    fireEvent.click(screen.getByText('完成并生成复盘'));

    await waitFor(() =>
      expect(interview.createInterviewReview).toHaveBeenCalledWith(
        expect.objectContaining({ raw_text: expect.stringContaining('开场白') }),
      ),
    );
    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['interviews'] }),
    );
  });
});
