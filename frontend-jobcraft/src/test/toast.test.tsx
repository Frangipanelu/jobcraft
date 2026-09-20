import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { useJobCraft, useToastActions } from '../context/JobCraftContext';

const api = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...api }));

/** 触发 showToast 的消费者，模拟业务组件调用。 */
const Trigger: React.FC = () => {
  const { showToast } = useToastActions();
  return (
    <button onClick={() => showToast({ type: 'info', title: '测试通知', message: '通知内容' })}>
      触发
    </button>
  );
};

beforeEach(() => {
  vi.resetAllMocks();
  api.autoLogin.mockResolvedValue(1);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('ToastContainer（FE-TOAST-CLEANUP-01）', () => {
  it('展示后 4 秒自动消失（auto-dismiss 由 ToastItem 生命周期接管）', async () => {
    vi.useFakeTimers();
    renderWithProviders(
      <div>
        <Trigger />
        <ToastContainer />
      </div>,
    );
    await act(async () => {});

    fireEvent.click(screen.getByText('触发'));
    expect(screen.getByText('测试通知')).toBeInTheDocument();
    expect(screen.getByText('通知内容')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText('测试通知')).not.toBeInTheDocument();
  });

  it('卸载时清理定时器，卸载后推进时间不触发 setState 错误', async () => {
    vi.useFakeTimers();
    const { unmount } = renderWithProviders(
      <div>
        <Trigger />
        <ToastContainer />
      </div>,
    );
    await act(async () => {});

    fireEvent.click(screen.getByText('触发'));
    expect(screen.getByText('测试通知')).toBeInTheDocument();

    unmount();
    expect(() => {
      act(() => {
        vi.advanceTimersByTime(4000);
      });
    }).not.toThrow();
  });

  it('点击关闭按钮立即消失', () => {
    renderWithProviders(
      <div>
        <Trigger />
        <ToastContainer />
      </div>,
    );

    fireEvent.click(screen.getByText('触发'));
    expect(screen.getByText('测试通知')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '关闭通知' }));
    expect(screen.queryByText('测试通知')).not.toBeInTheDocument();
  });

  it('无 toast 时不渲染容器', () => {
    renderWithProviders(<ToastContainer />);
    expect(screen.queryByText('测试通知')).not.toBeInTheDocument();
  });

  it('触发 toast 不重渲染 useJobCraft 消费者（useMemo 隔离）', () => {
    let navRenders = 0;
    const NavConsumer: React.FC = () => {
      useJobCraft();
      navRenders += 1;
      return <div>导航消费者</div>;
    };

    renderWithProviders(
      <div>
        <NavConsumer />
        <Trigger />
        <ToastContainer />
      </div>,
    );
    const rendersBeforeToast = navRenders;
    expect(rendersBeforeToast).toBeGreaterThan(0);

    fireEvent.click(screen.getByText('触发'));
    expect(screen.getByText('测试通知')).toBeInTheDocument();

    expect(navRenders).toBe(rendersBeforeToast);
  });
});