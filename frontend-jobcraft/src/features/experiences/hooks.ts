import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as experienceApi from '../../api/experience';
import * as jobApi from '../../api/job';
import * as tasksApi from '../../api/tasks';
import type { ExperienceCard } from '../../api/types';
import type { Experience, ExperienceVersionRecord } from '../../types/jobcraft';
import {
  EXPERIENCES_QUERY_KEY,
  cardToExperience,
  versionsToHistory,
} from './mappers';

/** updateCard 可提交的 payload（Experience 四槽位 + 可选 raw_text 原文回滚）。 */
type ExperienceUpdatePayload = Partial<Experience> & { raw_text?: string };

/** 某张经历卡的版本明细缓存 key（T-M1-2 懒加载：面板打开才拉）。 */
export const experienceVersionsQueryKey = (cardId: number) =>
  ['experience-versions', cardId] as const;

/**
 * 从后端拉取经历卡版本历史（EXP-P1-05 §28 / §34.6）。
 * 版本服务失败时返回 null（列表/写入不阻塞，回退保留现有信息）。
 */
async function loadVersionMeta(cardId: number): Promise<{
  currentVersion: string;
  versionHistory: ExperienceVersionRecord[];
} | null> {
  try {
    const res = await experienceApi.listCardVersions(cardId);
    return {
      currentVersion: `V${res.current_version}`,
      versionHistory: versionsToHistory(res.versions, res.current_version),
    };
  } catch {
    return null;
  }
}

/**
 * 版本历史明细查询（T-M1-2 懒加载腿）。
 *
 * 列表首屏不再逐卡拉版本（N+1→1，摘要走 GET /cards 内嵌字段）；
 * 仅当面板挂载（enabled）时按卡拉明细。失败回退 null，由调用方
 * 回落 cache 内的 exp.versionHistory（写路径回流的历史仍可用）。
 */
export function useCardVersionsQuery(cardId: number, enabled: boolean) {
  return useQuery<{
    currentVersion: string;
    versionHistory: ExperienceVersionRecord[];
  } | null>({
    queryKey: experienceVersionsQueryKey(cardId),
    queryFn: () => loadVersionMeta(cardId),
    enabled: enabled && !isNaN(cardId),
    staleTime: 30_000,
  });
}

/** 把前端 Experience 更新字段翻译为后端 updateCard payload（四槽位 + 定稿）。 */
function toUpdateCardPayload(
  updates: ExperienceUpdatePayload
): Partial<ExperienceCard> {
  const payload: Partial<ExperienceCard> = {
    title: updates.title,
    company: updates.company,
    role: updates.role,
    period: updates.period,
    tags: updates.tags,
    background: updates.background,
    problem: updates.problem,
    actions: updates.actions,
    results: updates.results,
    card_type: updates.category ? categoryToCardType(updates.category) : undefined,
    // EXP-P1-03：卡片页保存即定稿（V1），服务端写哨兵基线并幂等置位
    is_confirmed: true,
  };
  if (updates.raw_text !== undefined) {
    payload.raw_text = updates.raw_text;
  }
  return payload;
}

/**
 * 查询当前用户的经历卡列表（listCards → cardToExperience）。
 * 数据源：experienceApi.listCards；userId 取自已认证用户的 auth profile。
 *
 * T-M1-2：版本/表达摘要由 GET /cards 内嵌（current_version/version_count/
 * expression_summary），首屏单请求（原逐卡 listCardVersions 的 N+1 已移除）；
 * 版本历史明细改由 useCardVersionsQuery 在面板打开时懒加载。
 */
/**
 * 经历卡列表查询函数（W12：抽出让 useExperiencesQuery 与复盘反哺 mutation 复用，
 * 详情页可能未挂 useExperiencesQuery，写路径不得假设缓存已存在）。
 */
export function makeExperiencesQueryFn(queryClient: QueryClient) {
  return async () => {
    const user = await authApi.getCurrentUser();
    const cards = await experienceApi.listCards(user.id);
    // 列表响应不含版本明细（N+1→1 后明细只走 useCardVersionsQuery）；
    // refetch 时保留写路径（加版本/复盘反哺）已回流的 versionHistory，
    // 避免 invalidate 后明细被空数组抹掉。currentVersion 始终以后端列为准。
    const cached = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]);
    const cachedById = new Map((cached ?? []).map((e) => [e.id, e]));
    return cards.map((card) => {
      const exp = cardToExperience(card);
      const prev = cachedById.get(exp.id);
      if (prev && (prev.versionHistory?.length ?? 0) > 0) {
        exp.versionHistory = prev.versionHistory;
      }
      return exp;
    });
  };
}

export function useExperiencesQuery() {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: [...EXPERIENCES_QUERY_KEY],
    queryFn: makeExperiencesQueryFn(queryClient),
  });
}

/**
 * W12 终审：读经历卡列表（复盘反哺 mutation 专用）。
 * 缓存已定义（含空数组——用户真无卡）直接返回；未挂载/从未加载时 fetchQuery 拉取。
 */
export async function ensureExperiencesLoaded(queryClient: QueryClient): Promise<Experience[]> {
  const cached = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]);
  if (cached !== undefined) return cached;
  return queryClient.fetchQuery({
    queryKey: [...EXPERIENCES_QUERY_KEY],
    queryFn: makeExperiencesQueryFn(queryClient),
  });
}

/**
 * 服务端搜索缓存 key（T-M1-3 检索 v1）。
 *
 * 以 EXPERIENCES_QUERY_KEY 为前缀 → 写路径（update/delete/addVersion）
 * 对 `['experiences']` 的既有 invalidate 自动覆盖搜索缓存，无需逐处补失效。
 * 读取时 getQueryData(['experiences']) 为精确匹配，不受前缀 key 影响。
 */
export const experienceSearchQueryKey = (keyword: string) =>
  [...EXPERIENCES_QUERY_KEY, 'search', keyword] as const;

/**
 * 经历卡服务端搜索（T-M1-3 检索 v1 / DB-03 解封：cards/search 前端消费者 0→1）。
 *
 * 关键词为空不请求（enabled=false，调用方回落本地过滤）；
 * 单页 pageSize=100（后端上限），更大数据量由 total 信封反映。
 * 失败时 isError=true，由调用方回落本地过滤并 toast（不隐藏问题）。
 */
export function useCardSearchQuery(keyword: string) {
  const q = keyword.trim();
  return useQuery<Experience[]>({
    queryKey: experienceSearchQueryKey(q),
    enabled: q.length > 0,
    staleTime: 30_000,
    queryFn: async () => {
      const res = await experienceApi.searchCards({ q, pageSize: 100 });
      return res.items.map(cardToExperience);
    },
  });
}

/**
 * 创建经历卡。与 legacy `JobCraftContext.createExperience` 行为等价：
 * 后端 createCard 成功 → 前端 Experience（cardToExperience + 草稿前端扩展字段）→ cache 前置插入；
 * 后端失败向上抛出（由消费方 toast）。
 *
 * 统一字段契约（EXPERIENCE_SPEC §30.4）：提交 background / problem / actions / results / tags / card_type。
 * raw_text 由四槽位拼装（后端 create 必填），card_type 由 category 收敛为 work|intern|project。
 */
export function useCreateExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<Experience, unknown, Partial<Experience>>({
    mutationFn: async (draft) => {
      const card = await experienceApi.createCard({
        title: draft.title || '新增核心经历',
        raw_text: [
          draft.background,
          draft.problem,
          ...(draft.actions || []),
          ...(draft.results || [])
        ].filter(Boolean).join('\n'),
        company: draft.company || '',
        role: draft.role || '',
        period: draft.period || '',
        tags: draft.tags || [],
        background: draft.background || undefined,
        problem: draft.problem || undefined,
        actions: draft.actions || undefined,
        results: draft.results || undefined,
        card_type: categoryToCardType(draft.category),
        source: 'manual',
        is_active: true,
      });

      const base = cardToExperience(card);
      const meta = await loadVersionMeta(card.id);
      return {
        ...base,
        category: draft.category,
        actions: draft.actions || base.actions,
        results: draft.results || base.results,
        currentVersion: meta?.currentVersion || base.currentVersion,
        versionHistory: meta?.versionHistory || base.versionHistory,
      };
    },
    onSuccess: (newExp) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = [newExp, ...prev];
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);

    },
  });
}

/** category → card_type（EXPERIENCE_SPEC §30.4.1，未知回退 project）。 */
function categoryToCardType(category?: Experience['category']): 'work' | 'intern' | 'project' {
  if (category === 'work' || category === 'intern') return category;
  return 'project';
}

interface UpdateExperienceArgs {
  id: string;
  updates: ExperienceUpdatePayload;
}

/**
 * 更新经历卡。与 legacy `JobCraftContext.updateExperience` 行为等价：
 * 后端 updateCard 成功 → cache 内按 updates 合并 + 版本历史后端回流；
 * 后端失败向上抛出（不产生本地变更）。
 *
 * 统一字段契约（EXPERIENCE_SPEC §30.4）：提交四槽位 + tags + card_type。
 * 注意：不再把 background 当作 raw_text 整体覆盖（旧实现会破坏已保存的原始文本）；
 * 仅显式传入 raw_text 时（版本回滚）直接 PATCH 原文，服务端自动快照版本化。
 */
export function useUpdateExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<
    { id: string; updates: ExperienceUpdatePayload; currentVersion?: string; versionHistory?: ExperienceVersionRecord[] },
    unknown,
    UpdateExperienceArgs
  >({
    mutationFn: async ({ id, updates }) => {
      const cardId = parseInt(id);
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, toUpdateCardPayload(updates));
      }
      const meta = cardId ? await loadVersionMeta(cardId) : null;
      return {
        id,
        updates,
        currentVersion: meta?.currentVersion,
        versionHistory: meta?.versionHistory,
      };
    },
    onSuccess: ({ id, updates, currentVersion, versionHistory }) => {
      const { raw_text: _rawText, ...contentUpdates } = updates;
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.map((exp) =>
        exp.id === id
          ? {
              ...exp,
              ...contentUpdates,
              isConfirmed: true,
              currentVersion: currentVersion || exp.currentVersion,
              versionHistory: versionHistory || exp.versionHistory || [],
            }
          : exp,
      );
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);
      // FE-CACHE-01：服务端 updateCard（usage/tags 派生字段）落库后重验
      queryClient.invalidateQueries({ queryKey: [...EXPERIENCES_QUERY_KEY] });
      // T-M1-2：版本明细懒加载缓存同步失效（面板打开时拉到新版本链）
      const cardId = parseInt(id);
      if (!isNaN(cardId)) {
        queryClient.invalidateQueries({
          queryKey: experienceVersionsQueryKey(cardId),
        });
      }
    },
  });
}

/**
 * 重新执行 AI 结构化抽取（T-M1-1 失败重试入口）。
 * 成功后重验经历列表（新 ai_structured/tags 以后端为准），失败上抛由视图 toast。
 */
export function useStructureExperienceMutation() {
  const queryClient = useQueryClient();

  return useMutation<ExperienceCard, unknown, string>({
    mutationFn: (id) => experienceApi.structureCard(parseInt(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...EXPERIENCES_QUERY_KEY] });
    },
  });
}

/**
 * 删除经历卡。与 legacy `JobCraftContext.deleteExperience` 行为等价：
 * 后端 deleteCard 成功 → cache 内过滤。
 */
export function useDeleteExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<string, unknown, string>({
    mutationFn: async (id) => {
      const cardId = parseInt(id);
      if (!isNaN(cardId)) await experienceApi.deleteCard(cardId);
      return id;
    },
    onSuccess: (id) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.filter((exp) => exp.id !== id);
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);

    },
  });
}

export interface AddExperienceVersionResult {
  expId: string;
  currentVersion?: string;
  versionHistory?: ExperienceVersionRecord[];
}

interface AddExperienceVersionArgs {
  expId: string;
  updatedFields: Partial<Experience>;
}

/**
 * 经历升级/深度润色落库（EXP-P1-06b §34.6）。
 *
 * 纯本地版本记录已下线：内容变更改走后端 updateCard（服务端自动写
 * card_versions 快照 + version+1，EXP-P1-05 §28），随后从
 * listCardVersions 回流真实版本历史到 cache；版本号以后端为准。
 */
export function useAddExperienceVersionMutation() {
  const queryClient = useQueryClient();


  return useMutation<AddExperienceVersionResult, unknown, AddExperienceVersionArgs>({
    mutationFn: async ({ expId, updatedFields }) => {
      const cardId = parseInt(expId);
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, toUpdateCardPayload(updatedFields));
        const meta = await loadVersionMeta(cardId);
        return {
          expId,
          currentVersion: meta?.currentVersion,
          versionHistory: meta?.versionHistory,
        };
      }
      return { expId };
    },
    onSuccess: ({ expId, currentVersion, versionHistory }, { updatedFields }) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.map((exp) =>
        exp.id === expId
          ? {
              ...exp,
              ...updatedFields,
              isConfirmed: true,
              currentVersion: currentVersion || exp.currentVersion,
              versionHistory: versionHistory || exp.versionHistory || [],
            }
          : exp,
      );
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);
      // FE-CACHE-01：升级落库（updateCard 版本化）后重验，版本号以后端为准
      queryClient.invalidateQueries({ queryKey: [...EXPERIENCES_QUERY_KEY] });
      // T-M1-2：版本明细懒加载缓存同步失效
      const cardId = parseInt(expId);
      if (!isNaN(cardId)) {
        queryClient.invalidateQueries({
          queryKey: experienceVersionsQueryKey(cardId),
        });
      }
    },
  });
}

interface PolishExperienceArgs {
  expId: string;
  rawText: string;
  company: string;
  role: string;
}

/**
 * AI 润色经历原文（任务 `experience_polish`，降级同步端点 polishExperience）。
 * 返回拆行后的候选 actions（去 bullet 前缀、保留 >5 字条目）；落库由调用方
 * 走 useAddExperienceVersionMutation（服务端自动版本化，EXP-P1-06b §34.6）。
 * 失败上抛（调用方 error toast）。
 */
export function usePolishExperienceMutation() {
  return useMutation<string[], unknown, PolishExperienceArgs>({
    mutationFn: async ({ expId, rawText, company, role }) => {
      const result = await tasksApi.runTaskOrSync<{ polished_text: string }>(
        'experience_polish',
        { raw_text: rawText, company, role },
        () => jobApi.polishExperience(parseInt(expId.replace('exp-', '')), rawText, company, role),
        { timeout: 120_000 },
      );
      return result.polished_text
        .split('\n')
        .map((l) => l.replace(/^[-·•]\s*/, '').trim())
        .filter((l) => l.length > 5);
    },
  });
}