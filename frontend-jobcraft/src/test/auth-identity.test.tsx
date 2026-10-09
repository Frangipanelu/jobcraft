import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { useJobCraft } from '../context/JobCraftContext';
import { buildExportFileName } from '../components/user/UserProfileView';

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

vi.mock('../api/auth', () => ({ ...auth }));

/** 探针：把 currentUserId / isAuthenticated 映射成可观测文本，并暴露登录/登出动作。 */
const IdentityProbe = () => {
  const { currentUserId, isAuthenticated, login, logout } = useJobCraft();
  const [message, setMessage] = useState('');
  return (
    <div>
      <span data-testid="uid">{currentUserId === null ? 'null' : String(currentUserId)}</span>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="msg">{message}</span>
      <button
        onClick={async () => {
          try {
            await login('alice', 'Secret123');
            setMessage('login-ok');
          } catch (err) {
            setMessage(err instanceof Error ? err.message : 'login-error');
          }
        }}
      >
        登录
      </button>
      <button data-testid="logout" onClick={logout}>
        登出
      </button>
    </div>
  );
};

beforeEach(() => {
  vi.resetAllMocks();
});

describe('currentUserId 初值与空值语义（T-M10-4）', () => {
  it('渲染瞬间（autoLogin 未决）初值即为 null 且未登录——初值回归保护', () => {
    // autoLogin 永不 resolve：任何状态更新都不会发生，
    // 此时读到的就是 useState 初值本身（若被改回 1，此断言立即失败）
    auth.autoLogin.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<IdentityProbe />);

    expect(screen.getByTestId('uid')).toHaveTextContent('null');
    expect(screen.getByTestId('auth')).toHaveTextContent('no');
  });

  it('autoLogin 返回用户 id：置入该 id 并视为已登录', async () => {
    auth.autoLogin.mockResolvedValue(7);

    renderWithProviders(<IdentityProbe />);

    await waitFor(() => expect(screen.getByTestId('uid')).toHaveTextContent('7'));
    expect(screen.getByTestId('auth')).toHaveTextContent('yes');
  });

  it('autoLogin 无返回值（undefined，mock 未设 resolve）：不视为已登录，currentUserId 保持 null', async () => {
    auth.autoLogin.mockResolvedValue(undefined);

    renderWithProviders(<IdentityProbe />);

    await waitFor(() => expect(screen.getByTestId('auth')).toHaveTextContent('no'));
    expect(screen.getByTestId('uid')).toHaveTextContent('null');
  });

  it('autoLogin 返回 null（无 token/失效）：currentUserId 为 null', async () => {
    auth.autoLogin.mockResolvedValue(null);

    renderWithProviders(<IdentityProbe />);

    await waitFor(() => expect(screen.getByTestId('auth')).toHaveTextContent('no'));
    expect(screen.getByTestId('uid')).toHaveTextContent('null');
  });

  it('登录返回非数字身份：抛错且不置为已登录（不写入 undefined）', async () => {
    auth.autoLogin.mockResolvedValue(null);
    auth.login.mockResolvedValue(undefined);

    renderWithProviders(<IdentityProbe />);
    await waitFor(() => expect(screen.getByTestId('auth')).toHaveTextContent('no'));

    fireEvent.click(screen.getByText('登录'));

    await waitFor(() =>
      expect(screen.getByTestId('msg')).toHaveTextContent('未返回有效的用户 ID'),
    );
    expect(screen.getByTestId('auth')).toHaveTextContent('no');
    expect(screen.getByTestId('uid')).toHaveTextContent('null');
  });

  it('登录成功后登出：currentUserId 由身份值回到 null', async () => {
    auth.autoLogin.mockResolvedValue(null);
    auth.login.mockResolvedValue(5);

    renderWithProviders(<IdentityProbe />);
    await waitFor(() => expect(screen.getByTestId('auth')).toHaveTextContent('no'));

    fireEvent.click(screen.getByText('登录'));
    await waitFor(() => expect(screen.getByTestId('uid')).toHaveTextContent('5'));
    expect(screen.getByTestId('auth')).toHaveTextContent('yes');

    fireEvent.click(screen.getByTestId('logout'));
    await waitFor(() => expect(screen.getByTestId('uid')).toHaveTextContent('null'));
    expect(screen.getByTestId('auth')).toHaveTextContent('no');
    expect(auth.logout).toHaveBeenCalled();
  });
});

describe('导出文件名 null 语义（T-M10-4）', () => {
  it('有身份：拼接用户 id', () => {
    expect(buildExportFileName(7)).toBe('jobcraft_export_7.json');
  });

  it('null：不拼 "null" 字样，回退匿名标识', () => {
    expect(buildExportFileName(null)).toBe('jobcraft_export_anonymous.json');
  });
});
