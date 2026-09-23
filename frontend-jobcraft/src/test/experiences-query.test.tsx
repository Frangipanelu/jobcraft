import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ExperiencesView } from '../components/experiences/ExperiencesView';
import { NewExperienceModal } from '../components/experiences/NewExperienceModal';
import {
  useExperiencesQuery,
  useUpdateExperienceMutation,
  useAddExperienceVersionMutation,
} from '../features/experiences/hooks';
import type { ExperienceCard } from '../api/types';

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

const experience = vi.hoisted(() => ({
  listCards: vi.fn(),
  createCard: vi.fn(),
  updateCard: vi.fn(),
  deleteCard: vi.fn(),
  uploadResume: vi.fn(),
  structureCard: vi.fn(),
  recommendTags: vi.fn(),
  backfillCards: vi.fn(),
  listCardVersions: vi.fn(),
}));

vi.mock('../api/auth', () => ({ ...auth }));
vi.mock('../api/experience', () => ({ ...experience }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

const CARD_A: ExperienceCard = {
  id: 7,
  user_id: 1,
  title: '端侧大模型量化评测',
  raw_text: '移动端端侧生成式体验的量产方案。',
  tags: ['端侧大模型'],
  ai_structured: null,
  company: '未来智能实验室',
  role: 'AI 产品经理',
  period: '2025.01 - 2025.08',
  source: 'manual',
  card_type: 'work',
  version: 3,
  is_active: true,
  is_confirmed: true,
};

const CARD_B: ExperienceCard = {
  id: 8,
  user_id: 1,
  title: 'CLI 工具开源贡献',
  raw_text: '开源命令行工具维护与文档编写。',
  tags: [],
  ai_structured: null,
  company: '开源社区',
  role: '维护者',
  period: '2023.01 - 2024.06',
  source: 'manual',
  card_type: 'work',
  version: 1,
  is_active: true,
  is_confirmed: true,
};

const ExpCacheCount = () => {
  const { data: experiences = [] } = useExperiencesQuery();
  return <span data-testid="exp-cache-count">{experiences.length}</span>;
};

const ExpCacheTitle = () => {
  const { data: experiences = [] } = useExperiencesQuery();
  return <span data-testid="exp-cache-title">{experiences[0]?.title ?? ''}</span>;
};

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  experience.listCards.mockResolvedValue([CARD_A, CARD_B]);
  // EXP-P1-06b：默认版本历史为空（版本服务仅在后端有快照时返回）
  experience.listCardVersions.mockImplementation(async (cardId: number) => ({
    card_id: cardId,
    current_version: cardId === 7 ? 3 : 1,
    versions: [],
  }));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useExperiencesQuery 迁移视图', () => {
  it('ExperiencesView 从 query 渲染列表、分类计数并支持搜索过滤', async () => {
    renderWithProviders(<ExperiencesView />);

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();
    expect(screen.getByText('CLI 工具开源贡献')).toBeInTheDocument();
    expect(screen.getByText('全部资产 (2)')).toBeInTheDocument();
    expect(experience.listCards).toHaveBeenCalledWith(1);

    fireEvent.change(screen.getByPlaceholderText('搜索经历名称、公司、能力标签、量化指标...'), {
      target: { value: '开源' },
    });
    expect(screen.queryByText('端侧大模型量化评测')).not.toBeInTheDocument();
    expect(screen.getByText('CLI 工具开源贡献')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索经历名称、公司、能力标签、量化指标...'), {
      target: { value: '不存在的经历关键词xyz' },
    });
    expect(await screen.findByText('未检索到符合条件的经历资产')).toBeInTheDocument();

    fireEvent.click(screen.getByText('重置筛选条件'));
    expect(screen.getByText('端侧大模型量化评测')).toBeInTheDocument();
  });

  it('create：cache 前置写入（未迁移视图可读）', async () => {
    experience.createCard.mockResolvedValue({
      id: 9,
      user_id: 1,
      title: '新经历',
      raw_text: '新背景',
      tags: [],
      ai_structured: null,
      company: '新公司',
      role: '负责人',
      period: '2026.01 - 2026.03',
      source: 'manual',
      card_type: 'work',
      version: 1,
      is_active: true,
    } as ExperienceCard);

    renderWithProviders(
      <>
        <ExperiencesView />
        <NewExperienceModal isOpen onClose={() => {}} />
        <ExpCacheCount />
      </>,
    );

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('例如：AI 搜索评测体系建设'), {
      target: { value: '新经历' },
    });
    fireEvent.change(screen.getByPlaceholderText('例如：快知智能科技'), {
      target: { value: '新公司' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存至经历资产库' }));

    expect(await screen.findByText('新公司')).toBeInTheDocument();
    expect(screen.getByText('全部资产 (3)')).toBeInTheDocument();
    expect(experience.createCard).toHaveBeenCalledWith(
      expect.objectContaining({ title: '新经历', company: '新公司', source: 'manual' }),
    );
    await screen.findByTestId('exp-cache-count');
    expect(screen.getByTestId('exp-cache-count').textContent).toBe('3');
  });

  it('delete：后端 deleteCard + cache 过滤', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderWithProviders(
      <>
        <ExperiencesView />
        <ExpCacheCount />
      </>,
    );

    await screen.findByText('端侧大模型量化评测');
    expect(screen.getByTestId('exp-cache-count').textContent).toBe('2');

    fireEvent.click(screen.getAllByTitle('删除此经历')[0]);

    expect(await screen.findByText('全部资产 (1)')).toBeInTheDocument();
    expect(experience.deleteCard).toHaveBeenCalledWith(7);
    expect(screen.queryByText('端侧大模型量化评测')).not.toBeInTheDocument();
    expect(screen.getByTestId('exp-cache-count').textContent).toBe('1');
    confirmSpy.mockRestore();
  });
});

const UpdateHarness = () => {
  const { data } = useExperiencesQuery();
  const update = useUpdateExperienceMutation();
  const first = (data ?? [])[0];
  return (
    <>
      <span data-testid="cache-title">{first?.title ?? ''}</span>
      <button onClick={() => first && update.mutate({ id: first.id, updates: { title: '改名后的经历' } })}>
        更新标题
      </button>
    </>
  );
};

const VersionHarness = () => {
  const { data } = useExperiencesQuery();
  const addVersion = useAddExperienceVersionMutation();
  const first = (data ?? [])[0];
  return (
    <>
      <span data-testid="ver">{first?.currentVersion ?? ''}</span>
      <span data-testid="hist">{(first?.versionHistory ?? []).length}</span>
      <button
        onClick={() =>
          first &&
          addVersion.mutate({
            expId: first.id,
            updatedFields: { results: ['留存 +22.8%'] },
          })
        }
      >
        加版本
      </button>
    </>
  );
};

describe('useUpdateExperienceMutation / 版本保存（EXP-P1-06b 后端回流）', () => {
  it('update：后端 updateCard 成功 → cache 乐观合并', async () => {
    experience.updateCard.mockResolvedValue(CARD_A);

    renderWithProviders(
      <>
        <UpdateHarness />
        <ExpCacheTitle />
      </>,
    );

    await screen.findByTestId('cache-title');
    await waitFor(() => expect(screen.getByTestId('cache-title').textContent).toBe('端侧大模型量化评测'));

    fireEvent.click(screen.getByText('更新标题'));

    await waitFor(() => expect(screen.getByTestId('cache-title').textContent).toBe('改名后的经历'));
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ title: '改名后的经历', is_confirmed: true }),
    );
    await waitFor(() => expect(screen.getByTestId('exp-cache-title').textContent).toBe('改名后的经历'));
  });

  it('加版本：updateCard 持久化四槽位，versionHistory/currentVersion 以后端回流为准', async () => {
    experience.updateCard.mockResolvedValue(CARD_A);
    // 前两次调用 = 初始列表拉取（CARD_A / CARD_B，空历史）；
    // 点击「加版本」后的第三次调用 = mutation 回流（后端已新增 user_edit 快照 V4）。
    let versionCalls = 0;
    experience.listCardVersions.mockImplementation(async (cardId: number) => {
      versionCalls += 1;
      if (versionCalls <= 2) {
        return { card_id: cardId, current_version: cardId === 7 ? 3 : 1, versions: [] };
      }
      return {
        card_id: cardId,
        current_version: 4,
        versions: [
          {
            id: 2, card_id: cardId, version_type: 'user_edit', source_type: 'card_edit',
            source_id: 0, title: '端侧大模型量化评测', raw_text: '移动端端侧生成式体验的量产方案。',
            tags: ['端侧大模型'], note: '编辑保存 V4', created_at: '2026-09-23T10:00:00',
          },
          {
            id: 1, card_id: cardId, version_type: 'original', source_type: 'original',
            source_id: 0, title: '端侧大模型量化评测', raw_text: '移动端端侧生成式体验的量产方案。',
            tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-20T10:00:00',
          },
        ],
      };
    });

    renderWithProviders(<VersionHarness />);

    expect(await screen.findByText('V3')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('hist').textContent).toBe('0'));

    fireEvent.click(screen.getByText('加版本'));

    await waitFor(() => expect(screen.getByTestId('ver').textContent).toBe('V4'));
    await waitFor(() => expect(screen.getByTestId('hist').textContent).toBe('2'));
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ results: ['留存 +22.8%'], is_confirmed: true }),
    );
  });
});