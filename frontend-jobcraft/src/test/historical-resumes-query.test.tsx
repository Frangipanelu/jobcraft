import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { UserProfileView } from '../components/user/UserProfileView';
import {
  useHistoricalResumesQuery,
  useAddHistoricalResumeMutation,
} from '../features/historical-resumes/hooks';
import type { BaseResumeRecord } from '../api/job';

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
  listBaseResumes: vi.fn(),
  createBaseResume: vi.fn(),
  setDefaultBaseResume: vi.fn(),
  deleteBaseResume: vi.fn(),
  listJobAnalyses: vi.fn(),
}));

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
}));

const interview = vi.hoisted(() => ({
  listInterviewPreps: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/job', () => ({ ...job }));
vi.mock('../api/experience', () => ({ ...experience }));
vi.mock('../api/interview', () => ({ ...interview }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const REC_DEFAULT: BaseResumeRecord = {
  id: 1,
  user_id: 1,
  name: '2026_阿里高端AI产品简历.pdf',
  file_size: '1.2 MB',
  format: 'pdf',
  parsed_count: 5,
  tags: ['已解析', 'AI 结构化'],
  is_default: true,
  created_at: '2026-09-10T10:00:00',
  updated_at: '2026-09-10T10:00:00',
};

const REC_HISTORY: BaseResumeRecord = {
  id: 2,
  user_id: 1,
  name: '历史版本_腾讯产品简历.docx',
  file_size: '890 KB',
  format: 'docx',
  parsed_count: 3,
  tags: [],
  is_default: false,
  created_at: '2026-08-20T08:00:00',
  updated_at: '2026-08-20T08:00:00',
};

const REC_LIST = [REC_DEFAULT, REC_HISTORY];

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({});
  job.getDashboard.mockResolvedValue({ submissions: [] });
  job.listBaseResumes.mockResolvedValue(REC_LIST);
  job.createBaseResume.mockResolvedValue({ ...REC_DEFAULT, id: 99, name: '新上传.pdf' });
  job.setDefaultBaseResume.mockResolvedValue({ ...REC_DEFAULT, id: 2, is_default: true });
  job.deleteBaseResume.mockResolvedValue({ ok: true });
  job.listJobAnalyses.mockResolvedValue([]);
  experience.listCards.mockResolvedValue([]);
  interview.listInterviewPreps.mockResolvedValue([]);
});

const AddHarness = () => {
  const add = useAddHistoricalResumeMutation();
  const { data = [] } = useHistoricalResumesQuery();
  return (
    <div>
      <button
        onClick={() =>
          add.mutate({
            name: '新上传.pdf',
            fileSize: '1.0 MB',
            isDefault: false,
            parsedExperiencesCount: 4,
            format: 'pdf',
            tags: ['本地上传'],
          })
        }
      >
        添加简历
      </button>
      <ul>
        {data.map((r) => (
          <li key={r.id}>
            {r.name}|{r.serverId ?? 'none'}
          </li>
        ))}
      </ul>
    </div>
  );
};

/** 向上寻找包含指定文本的最近元素（用于定位按钮所属的简历卡片）。 */
const nearestCardContains = (el: HTMLElement, text: string): boolean => {
  let node: HTMLElement | null = el;
  while (node && !node.textContent?.includes(text)) {
    node = node.parentElement;
  }
  return Boolean(node?.textContent?.includes(text));
};

describe('FE-HISTORICAL-RESUMES-01 历史简历域迁移', () => {
  it('UserProfileView 从 query 渲染历史简历列表、计数与默认徽标', async () => {
    renderWithProviders(<UserProfileView />);

    expect(await screen.findByText('2026_阿里高端AI产品简历.pdf')).toBeInTheDocument();
    expect(screen.getByText('历史版本_腾讯产品简历.docx')).toBeInTheDocument();
    expect(screen.getByText('默认底座简历')).toBeInTheDocument();
    expect(screen.getByText(/已解析沉淀 5/)).toBeInTheDocument();

    // tab 徽标展示总数
    const tab = screen.getByRole('button', { name: /历史简历管理/ });
    expect(tab.textContent).toContain('2');
  });

  it('删除：deleteBaseResume 成功后从列表移除，默认项保留', async () => {
    renderWithProviders(<UserProfileView />);
    await screen.findByText('历史版本_腾讯产品简历.docx');

    const deleteButtons = screen.getAllByTitle('删除此简历');
    fireEvent.click(deleteButtons[1]);

    await waitFor(() => expect(job.deleteBaseResume).toHaveBeenCalledWith(2));
    await waitFor(() =>
      expect(screen.queryByText('历史版本_腾讯产品简历.docx')).not.toBeInTheDocument(),
    );
    expect(screen.getByText('2026_阿里高端AI产品简历.pdf')).toBeInTheDocument();
  });

  it('删除后端失败：条目保留、不误删本地记录', async () => {
    job.deleteBaseResume.mockRejectedValue(new Error('network'));
    renderWithProviders(<UserProfileView />);
    await screen.findByText('历史版本_腾讯产品简历.docx');

    const deleteButtons = screen.getAllByTitle('删除此简历');
    fireEvent.click(deleteButtons[1]);

    await waitFor(() => expect(job.deleteBaseResume).toHaveBeenCalledWith(2));
    await waitFor(() =>
      expect(screen.getByText('历史版本_腾讯产品简历.docx')).toBeInTheDocument(),
    );
  });

  it('设为默认：setDefaultBaseResume 调用 + 默认徽标迁移到新项', async () => {
    renderWithProviders(<UserProfileView />);
    await screen.findByText('历史版本_腾讯产品简历.docx');

    // 默认项是简历 1，因此「设为默认底座」当前出现在简历 2 卡片
    const setDefaultButton = screen.getByRole('button', { name: '设为默认底座' });
    expect(nearestCardContains(setDefaultButton, '历史版本_腾讯产品简历.docx')).toBe(true);

    fireEvent.click(setDefaultButton);

    await waitFor(() => expect(job.setDefaultBaseResume).toHaveBeenCalledWith(2));
    await waitFor(() => {
      // 迁移后唯一「设为默认底座」出现在原默认简历（简历 1）卡片
      const btn = screen.getByRole('button', { name: '设为默认底座' });
      expect(nearestCardContains(btn, '2026_阿里高端AI产品简历.pdf')).toBe(true);
    });
    expect(screen.getAllByText('默认底座简历')).toHaveLength(1);
  });

  it('新增：createBaseResume 落库回填 serverId 后前置入列', async () => {
    job.listBaseResumes.mockResolvedValue([]);
    renderWithProviders(<AddHarness />);
    await screen.findByText('添加简历');

    fireEvent.click(screen.getByRole('button', { name: '添加简历' }));

    await waitFor(() =>
      expect(job.createBaseResume).toHaveBeenCalledWith({
        name: '新上传.pdf',
        file_size: '1.0 MB',
        format: 'pdf',
        parsed_count: 4,
        tags: ['本地上传'],
      }),
    );
    expect(await screen.findByText('新上传.pdf|99')).toBeInTheDocument();
  });

  it('新增落库失败：仅保留内存记录（无 serverId），不崩溃', async () => {
    job.listBaseResumes.mockResolvedValue([]);
    job.createBaseResume.mockRejectedValue(new Error('network'));
    renderWithProviders(<AddHarness />);
    await screen.findByText('添加简历');

    fireEvent.click(screen.getByRole('button', { name: '添加简历' }));

    expect(await screen.findByText('新上传.pdf|none')).toBeInTheDocument();
  });
});