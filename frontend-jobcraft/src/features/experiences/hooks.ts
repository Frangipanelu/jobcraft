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
 */
export function useCreateExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<Experience, unknown, Partial<Experience>>({
    mutationFn: async (draft) => {
      const card = await experienceApi.createCard({
        title: draft.title || '新增核心经历',
        raw_text: draft.background || draft.responsibility || '',
        company: draft.company || '',
        role: draft.role || '',
        period: draft.period || '',
        tags: draft.capabilityTags || [],
        source: 'manual',
        card_type: 'work',
        is_active: true,
      });

      const base = cardToExperience(card);
      return {
        ...base,
        category: draft.category,
        actions: draft.actions || base.actions,
        results: draft.results || base.results,
        metrics: draft.metrics || base.metrics,
        targetJobs: draft.targetJobs || [],
        jdMatches: draft.jdMatches || [],
        resumeVersionsUsed: draft.resumeVersionsUsed || [],
      };
    },
    onSuccess: (newExp) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = [newExp, ...prev];
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], next);

    },
  });
}

interface UpdateExperienceArgs {
  id: string;
  updates: Partial<Experience>;
}

/**
 * 更新经历卡。与 legacy `JobCraftContext.updateExperience` 行为等价：
 * 后端 updateCard 成功 → cache 内按 updates 合并；
 * 后端失败向上抛出（不产生本地变更）。
 */
export function useUpdateExperienceMutation() {
  const queryClient = useQueryClient();


  return useMutation<UpdateExperienceArgs, unknown, UpdateExperienceArgs>({
    mutationFn: async ({ id, updates }) => {
      const cardId = parseInt(id);
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, {
          title: updates.title,
          raw_text: updates.background,
          company: updates.company,
          role: updates.role,
          period: updates.period,
          tags: updates.capabilityTags,
        });
      }
      return { id, updates };
    },
    onSuccess: ({ id, updates }) => {
      const prev = queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const next = prev.map((exp) => (exp.id === id ? { ...exp, ...updates } : exp));
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