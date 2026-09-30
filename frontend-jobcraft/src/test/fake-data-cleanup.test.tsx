import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { InterviewReviewCenterView } from '../components/review/InterviewReviewCenterView';

const auth = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
}));
const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/interview', () => ({ ...interview }));

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue({ id: 1, username: 'dev' });
  interview.listInterviewPreps.mockResolvedValue({ records: [] });
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
