import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as experienceApi from '../../api/experience';
import type { Experience, ExperienceVersionRecord } from '../../types/jobcraft';
import { EXPERIENCES_QUERY_KEY, cardToExperience } from './mappers';


/**
 * 查询当前用户的经历卡列表（listCards → cardToExperience）。
 * 数据源：experienceApi.listCards；userId 取自已认证用户的 auth profile。
 */
export function useExperiencesQuery() {
  return useQuery({
    queryKey: [...EXPERIENCES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const cards = await experienceApi.listCards(user.id);
      return cards.map(cardToExperience);
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
      return {
        ...base,
        category: draft.category,
        actions: draft.actions || base.actions,
        results: draft.results || base.results,
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
  updates: Partial<Experience>;
}

/**
 * 更新经历卡。与 legacy `JobCraftContext.updateExperience` 行为等价：
 * 后端 updateCard 成功 → cache 内按 updates 合并；
 * 后端失败向上抛出（不产生本地变更）。
 *
 * 统一字段契约（EXPERIENCE_SPEC §30.4）：提交四槽位 + tags + card_type。
 * 注意：不再把 background 当作 raw_text 整体覆盖（旧实现会破坏已保存的原始文本）。
 */
export function useUpdateExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<UpdateExperienceArgs, unknown, UpdateExperienceArgs>({
    mutationFn: async ({ id, updates }) => {
      const cardId = parseInt(id);
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, {
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
        });
      }
      return { id, updates };
    },
    onSuccess: ({ id, updates }) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.map((exp) => (exp.id === id ? { ...exp, ...updates, isConfirmed: true } : exp));
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

interface AddExperienceVersionArgs {
  expId: string;
  version: string;
  reason: string;
  updatedFields: Partial<Experience>;
}

/**
 * 本地版本演进（后端无经历版本端点，纯前端状态）。
 * 与 legacy `JobCraftContext.addExperienceVersion` 语义逐字等价：
 * versionHistory 前置插入新版本记录，currentVersion 更新，不发网络请求。
 */
export function useAddExperienceVersionMutation() {
  const queryClient = useQueryClient();


  return useMutation<string, unknown, AddExperienceVersionArgs>({
    mutationFn: async (args) => args.expId,
    onMutate: (args) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.map((exp) => {
        if (exp.id !== args.expId) return exp;
        const newVersionRecord: ExperienceVersionRecord = {
          version: args.version,
          date: new Date().toISOString().split('T')[0],
          reason: args.reason,
          source: 'ai_optimization',
          changes: Object.keys(args.updatedFields).map((key) => ({
            field: key,
            from: '原版内容',
            to: String((args.updatedFields as Record<string, unknown>)[key]),
          })),
        };
        return {
          ...exp,
          ...args.updatedFields,
          currentVersion: args.version,
          versionHistory: [newVersionRecord, ...(exp.versionHistory || [])],
        };
      });
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);

    },
  });
}