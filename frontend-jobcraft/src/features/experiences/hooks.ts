import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as experienceApi from '../../api/experience';
import type { ExperienceCard } from '../../api/types';
import type { Experience, ExperienceVersionRecord } from '../../types/jobcraft';
import {
  EXPERIENCES_QUERY_KEY,
  cardToExperience,
  versionsToHistory,
} from './mappers';

/** updateCard 可提交的 payload（Experience 四槽位 + 可选 raw_text 原文回滚）。 */
type ExperienceUpdatePayload = Partial<Experience> & { raw_text?: string };

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
 * 版本历史（EXP-P1-05 §34.6）：列表并行拉取各卡 card_versions 快照，
 * versionHistory/currentVersion 以后端为准（失败静默保留空历史）。
 */
export function useExperiencesQuery() {
  return useQuery({
    queryKey: [...EXPERIENCES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const cards = await experienceApi.listCards(user.id);
      return Promise.all(
        cards.map(async (card) => {
          const exp = cardToExperience(card);
          const meta = await loadVersionMeta(card.id);
          if (meta) {
            exp.currentVersion = meta.currentVersion;
            exp.versionHistory = meta.versionHistory;
          }
          return exp;
        }),
      );
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

    },
  });
}