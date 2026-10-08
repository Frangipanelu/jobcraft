import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { ExperiencesView, buildRestoreUpdates } from '../components/experiences/ExperiencesView';
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
  listCardVersions: vi.fn(),
  structureCard: vi.fn(),
  searchCards: vi.fn(),
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

// FE-CACHE-01：mock 服务端需有状态——updateCard 后 invalidate 触发 listCards
// refetch 时必须返回反映本次写入的服务端真相，否则乐观合并被静态 fixture 回滚。
let serverCards: ExperienceCard[] = [];

beforeEach(() => {
  vi.resetAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  auth.getProfile.mockResolvedValue({});
  auth.updateProfile.mockResolvedValue({});
  auth.getSettings.mockResolvedValue({ model_name: 'test', provider: 'x', status: 'running' });
  serverCards = [{ ...CARD_A }, { ...CARD_B }];
  experience.listCards.mockImplementation(async () => serverCards);
  // T-M1-2：currentVersion 只来自 GET /cards 的 version 列，故 mock 需模拟后端
  // updateCard 同事务 version+1（真实契约见 EXPERIENCE_SPEC §28）。
  experience.updateCard.mockImplementation(
    async (cardId: number, payload: Partial<ExperienceCard>) => {
      const card = serverCards.find((c) => c.id === cardId);
      if (card) {
        Object.assign(card, payload);
        card.version = (card.version ?? 1) + 1;
      }
      return card;
    },
  );
  // EXP-P1-06b：默认版本历史为空（版本服务仅在后端有快照时返回）
  experience.listCardVersions.mockImplementation(async (cardId: number) => ({
    card_id: cardId,
    current_version: cardId === 7 ? 3 : 1,
    versions: [],
  }));
  // T-M1-3：服务端搜索默认空结果（各用例按需覆写；避免 undefined 返回触发错误 toast）
  experience.searchCards.mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 100,
    total_pages: 0,
    query: null,
    direction_id: null,
  });
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
    // 版本明细按服务端 version 列回流：首屏不逐卡请求（见下方懒加载用例），
    // mutation 内的 loadVersionMeta 拿到 version+1 后的新快照链。
    experience.listCardVersions.mockImplementation(async (cardId: number) => {
      const card = serverCards.find((c) => c.id === cardId);
      const currentVersion = card?.version ?? 1;
      return {
        card_id: cardId,
        current_version: currentVersion,
        versions: currentVersion >= 4
          ? [
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
            ]
          : [],
      };
    });

    renderWithProviders(<VersionHarness />);

    expect(await screen.findByText('V3')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId('hist').textContent).toBe('0'));
    // T-M1-2：首屏列表不再逐卡调用 listCardVersions（N+1→1）
    expect(experience.listCardVersions).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('加版本'));

    await waitFor(() => expect(screen.getByTestId('ver').textContent).toBe('V4'));
    await waitFor(() => expect(screen.getByTestId('hist').textContent).toBe('2'));
    expect(experience.updateCard).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ results: ['留存 +22.8%'], is_confirmed: true }),
    );
  });
});

describe('T-M1-2 版本明细懒加载（N+1→1）', () => {
  it('首屏不拉 card_versions，展开「版本演进」面板才按卡请求', async () => {
    experience.listCardVersions.mockResolvedValue({
      card_id: 7,
      current_version: 3,
      versions: [
        {
          id: 1, card_id: 7, version_type: 'original', source_type: 'original',
          source_id: 0, title: '端侧大模型量化评测', raw_text: '移动端端侧生成式体验的量产方案。',
          tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-20T10:00:00',
        },
      ],
    });

    renderWithProviders(<ExperiencesView />);

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();
    expect(screen.getByText('CLI 工具开源贡献')).toBeInTheDocument();
    expect(experience.listCards).toHaveBeenCalled();
    expect(experience.listCardVersions).not.toHaveBeenCalled();

    fireEvent.click(screen.getAllByRole('button', { name: /版本演进/ })[0]);

    await waitFor(() => expect(experience.listCardVersions).toHaveBeenCalledWith(7));
    expect(await screen.findByText('V1 哨兵基线（确认定稿）')).toBeInTheDocument();
  });

  it('FE-JDVER-01：jd 快照标 JD 不抢「当前激活版本」徽标，「累计迭代」只数非 jd 版本', async () => {
    experience.listCardVersions.mockResolvedValue({
      card_id: 7,
      current_version: 3,
      versions: [
        {
          id: 4, card_id: 7, version_type: 'jd_alignment', source_type: 'resume_version',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'JD 对齐后的原文。',
          tags: ['端侧大模型'], note: null, created_at: '2026-09-24T10:00:00',
        },
        {
          id: 3, card_id: 7, version_type: 'user_edit', source_type: 'card_edit',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'V3 原文。',
          tags: ['端侧大模型'], note: null, created_at: '2026-09-23T10:00:00',
        },
        {
          id: 2, card_id: 7, version_type: 'user_edit', source_type: 'card_edit',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'V2 原文。',
          tags: ['端侧大模型'], note: null, created_at: '2026-09-22T10:00:00',
        },
        {
          id: 1, card_id: 7, version_type: 'original', source_type: 'original',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'V1 原文。',
          tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-20T10:00:00',
        },
      ],
    });

    renderWithProviders(<ExperiencesView />);

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /版本演进/ })[0]);

    // 4 行快照含 1 条 jd → 迭代口径只数 3 条内容版本
    expect(
      await screen.findByText('版本演进时间轴（累计迭代 3 个版本）'),
    ).toBeInTheDocument();
    // jd 行标 'JD'，永不匹配 V{n} → 不抢当前徽标；真正当前行（V3）持徽标
    expect(screen.getAllByText('当前激活版本')).toHaveLength(1);
    const jdRow = screen.getByText('JD').parentElement?.parentElement;
    expect(jdRow).toBeDefined();
    expect(jdRow?.textContent).not.toContain('当前激活版本');
    // 列表卡头徽标也渲染 'V3'，须在面板行内定位持「当前激活版本」的行
    const currentRow = screen
      .getAllByText('V3')
      .map((el) => el.parentElement?.parentElement)
      .find((row) => row?.textContent?.includes('当前激活版本'));
    expect(currentRow).toBeDefined();
    // 当前行持徽标并隐藏「激活此版本」按钮（既有行为）
    expect(currentRow?.textContent).not.toContain('激活此版本');
    // jd 快照正文可被激活（期望行为）
    expect(jdRow?.textContent).toContain('激活此版本');
  });

  it('FE-JDVER-01：无 rawText 的 jd 快照激活 → updateCard payload 不含 currentVersion', async () => {
    experience.listCardVersions.mockResolvedValue({
      card_id: 7,
      current_version: 3,
      versions: [
        {
          // 遗留分支：jd 快照无正文（raw_text 空串为 falsy）→ 走 /^V\d+$/ 守卫
          id: 4, card_id: 7, version_type: 'jd_alignment', source_type: 'resume_version',
          source_id: 0, title: '端侧大模型量化评测', raw_text: '',
          tags: ['端侧大模型'], note: null, created_at: '2026-09-24T10:00:00',
        },
        {
          id: 3, card_id: 7, version_type: 'user_edit', source_type: 'card_edit',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'V3 原文。',
          tags: ['端侧大模型'], note: null, created_at: '2026-09-23T10:00:00',
        },
        {
          id: 1, card_id: 7, version_type: 'original', source_type: 'original',
          source_id: 0, title: '端侧大模型量化评测', raw_text: 'V1 原文。',
          tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-20T10:00:00',
        },
      ],
    });

    renderWithProviders(
      <>
        <ExperiencesView />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /版本演进/ })[0]);
    // 3 行快照含 1 条 jd → 迭代口径只数 2 条内容版本
    expect(
      await screen.findByText('版本演进时间轴（累计迭代 2 个版本）'),
    ).toBeInTheDocument();

    // 面板首行 = jd 快照（标签 'JD' 非当前行）→ 其「激活此版本」走遗留分支
    const restoreButtons = screen.getAllByRole('button', { name: /激活此版本/ });
    fireEvent.click(restoreButtons[0]);

    await waitFor(() => expect(experience.updateCard).toHaveBeenCalled());
    const calls = experience.updateCard.mock.calls;
    const payload = calls[calls.length - 1][1] as Record<string, unknown>;
    // FE-JDVER-01 守卫：'JD' 不匹配 /^V\d+$/ → updates 不含 currentVersion
    expect(payload).not.toHaveProperty('currentVersion');
  });
});

describe('FE-JDVER-01 restore 遗留分支守卫（buildRestoreUpdates 纯函数）', () => {
  const baseRecord = {
    date: '2026-09-24',
    reason: 'JD 深度对齐',
    source: 'jd_alignment' as const,
    changes: [],
  };

  it('无 rawText + JD 标签 → 空 updates，不写 currentVersion（防 cache 污染）', () => {
    const updates = buildRestoreUpdates(
      { ...baseRecord, version: 'JD' },
      '端侧大模型量化评测',
    );
    expect(updates).toEqual({});
    expect(updates).not.toHaveProperty('currentVersion');
  });

  it('无 rawText + V{n} 标签 → 回写 currentVersion', () => {
    const updates = buildRestoreUpdates(
      { ...baseRecord, version: 'V2' },
      '端侧大模型量化评测',
    );
    expect(updates).toEqual({ currentVersion: 'V2' });
  });

  it('有 rawText → 原文回滚 {title, raw_text}，不写 currentVersion', () => {
    const updates = buildRestoreUpdates(
      { ...baseRecord, version: 'V3', title: '快照标题', rawText: '快照原文' },
      '端侧大模型量化评测',
    );
    expect(updates).toEqual({ title: '快照标题', raw_text: '快照原文' });
    expect(updates).not.toHaveProperty('currentVersion');
  });
});

describe('T-M1-1 structure 失败重试入口', () => {
  it('STAR 为空的卡展示「重新结构化」，点击调用 structureCard 并 toast 成功', async () => {
    experience.structureCard.mockImplementation(async (cardId: number): Promise<ExperienceCard> => {
      const card = serverCards.find((c) => c.id === cardId);
      if (!card) throw new Error(`card ${cardId} not found`);
      return {
        ...card,
        ai_structured: {
          summary: '结构化摘要',
          achievements: [{ title: '落地量化', result: '留存 +22.8%' }],
        },
      };
    });

    renderWithProviders(
      <>
        <ExperiencesView />
        <ToastContainer />
      </>,
    );

    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();
    // 两张卡 ai_structured 均为 null 且 A/R 槽位空 → 都展示入口
    expect(screen.getAllByRole('button', { name: /重新结构化/ })).toHaveLength(2);

    fireEvent.click(screen.getAllByRole('button', { name: /重新结构化/ })[0]);

    await waitFor(() => expect(experience.structureCard).toHaveBeenCalledWith(7));
    expect(await screen.findByText('AI 结构化完成')).toBeInTheDocument();
  });
});

describe('T-M1-3 服务端搜索接线（DB-03 解封：cards/search 消费者 0→1）', () => {
  const searchInput = () =>
    screen.getByPlaceholderText('搜索经历名称、公司、能力标签、量化指标...');

  it('关键词静止过 debounce 后调 searchCards，并以服务端结果为准', async () => {
    // 服务端返回与本地匹配不同的卡（本地 '量化评测' 只命中 A）→ 断言列表显示 B，
    // 证明展示结果来自服务端而非本地过滤。
    experience.searchCards.mockResolvedValue({
      items: [CARD_B],
      total: 1,
      page: 1,
      page_size: 100,
      total_pages: 1,
      query: '量化评测',
      direction_id: null,
    });

    renderWithProviders(<ExperiencesView />);
    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();

    fireEvent.change(searchInput(), { target: { value: '量化评测' } });

    await waitFor(
      () => expect(experience.searchCards).toHaveBeenCalledWith({ q: '量化评测', pageSize: 100 }),
      { timeout: 2000 },
    );
    expect(await screen.findByText('CLI 工具开源贡献')).toBeInTheDocument();
    expect(screen.queryByText('端侧大模型量化评测')).not.toBeInTheDocument();
  });

  it('未输入关键词不请求 searchCards，列表保持全量本地', async () => {
    renderWithProviders(<ExperiencesView />);
    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();

    // 等过 debounce 窗口，确认空关键词不产生请求
    await new Promise((resolve) => setTimeout(resolve, 350));

    expect(experience.searchCards).not.toHaveBeenCalled();
    expect(screen.getByText('CLI 工具开源贡献')).toBeInTheDocument();
    expect(screen.getByText('全部资产 (2)')).toBeInTheDocument();
  });

  it('服务端搜索失败 → toast 报错并回落本地过滤（不隐藏问题）', async () => {
    experience.searchCards.mockRejectedValue(new Error('boom'));

    renderWithProviders(
      <>
        <ExperiencesView />
        <ToastContainer />
      </>,
    );
    expect(await screen.findByText('端侧大模型量化评测')).toBeInTheDocument();

    fireEvent.change(searchInput(), { target: { value: '开源' } });

    await waitFor(() => expect(experience.searchCards).toHaveBeenCalled(), { timeout: 2000 });
    expect(await screen.findByText('搜索失败')).toBeInTheDocument();
    // 回落本地：'开源' 仍能过滤出本地匹配的卡
    expect(screen.getByText('CLI 工具开源贡献')).toBeInTheDocument();
    expect(screen.queryByText('端侧大模型量化评测')).not.toBeInTheDocument();
  });
});