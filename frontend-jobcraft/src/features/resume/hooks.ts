import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import { ResumeVersion } from '../../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../../utils/resumeParser';
import { RESUMES_QUERY_KEY } from './mappers';

/**
 * 读取当前 RESUMES cache。
 * 简历 map 为 `Record<submissionId, ResumeVersion>`（submissionId 为字符串），缺失时回退空对象。
 */
function readResumesMap(
  queryClient: ReturnType<typeof useQueryClient>,
): Record<string, ResumeVersion> {
  return (
    queryClient.getQueryData<Record<string, ResumeVersion>>([...RESUMES_QUERY_KEY]) || {}
  );
}

/** 写入 RESUMES cache。 */
function writeResumesMap(
  queryClient: ReturnType<typeof useQueryClient>,
  next: Record<string, ResumeVersion>,
): void {
  queryClient.setQueryData([...RESUMES_QUERY_KEY], next);
}

/**
 * 查询简历编辑 map。与 legacy `loadDashboard` 内联水合行为等价：
 * - getDashboard → 对 `has_resume` 的投递调 getSubmission → `markdownToResume`；
 * - 单条失败容忍（返回 null 跳过），不抛错、不留 console；空数据返回 {}。
 * @returns 以 submission id（字符串）为键的简历 map
 */
export function useResumesQuery() {
  return useQuery({
    queryKey: [...RESUMES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.getDashboard(user.id);
      const submissions = data.submissions || [];

      const entries = await Promise.all(
        submissions.map(async (item) => {
          if (!item.has_resume) return null;
          try {
            const detail = await jobApi.getSubmission(item.id);
            const resume = markdownToResume(detail.resume_markdown, {
              position: detail.position,
              company: detail.company,
              id: String(item.id),
            });
            return resume ? ([String(item.id), resume] as const) : null;
          } catch {
            return null;
          }
        }),
      );

      const next: Record<string, ResumeVersion> = {};
      for (const entry of entries) {
        if (entry) next[entry[0]] = entry[1];
      }
      return next;
    },
  });
}

// ---------------------------------------------------------------------------
// 纯编辑 mutation（cache 内函数式更新，无 API，与 legacy apply/reject/… 等价）
// ---------------------------------------------------------------------------

/**
 * 应用单条 AI 优化建议：命中 `targetBulletId` 时改写 bullet 文本，并把建议标记 applied。
 * @param mutationFn 入参 { resumeId, suggestionId }；无对应建议时抛错（视图 toast）。
 */
export function useApplyResumeAiSuggestionMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    suggestionId: string;
  }>({
    mutationFn: async ({ resumeId, suggestionId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const sug = (activeResume.aiSuggestions || []).find((s) => s.id === suggestionId);
      if (!sug) throw new Error('未找到该条优化建议');

      let updatedSections = [...activeResume.sections];

      if (sug.targetBulletId) {
        updatedSections = updatedSections.map((sec) => ({
          ...sec,
          items: sec.items.map((item) => ({
            ...item,
            bullets: item.bullets.map((b) =>
              b.id === sug.targetBulletId ? { ...b, text: sug.suggestedText } : b,
            ),
          })),
        }));
      }

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) =>
        s.id === suggestionId ? { ...s, applied: true, rejected: false } : s,
      );

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions,
          sections: updatedSections,
          updatedAt: '刚刚',
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

/**
 * 忽略单条 AI 优化建议（标记 rejected，正文不变）。
 * @param mutationFn 入参 { resumeId, suggestionId }
 */
export function useRejectResumeAiSuggestionMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    suggestionId: string;
  }>({
    mutationFn: async ({ resumeId, suggestionId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) =>
        s.id === suggestionId ? { ...s, rejected: true, applied: false } : s,
      );

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions,
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

/**
 * 全部应用 AI 优化建议：逐个改写 target bullet 文本（已 reject 的跳过），全部标记 applied。
 * @param mutationFn 入参 { resumeId }
 */
export function useApplyAllResumeAiSuggestionsMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, { resumeId: string }>({
    mutationFn: async ({ resumeId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      let updatedSections = [...activeResume.sections];

      (activeResume.aiSuggestions || []).forEach((sug) => {
        if (sug.targetBulletId && !sug.rejected) {
          updatedSections = updatedSections.map((sec) => ({
            ...sec,
            items: sec.items.map((item) => ({
              ...item,
              bullets: item.bullets.map((b) =>
                b.id === sug.targetBulletId ? { ...b, text: sug.suggestedText } : b,
              ),
            })),
          }));
        }
      });

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) => ({
        ...s,
        applied: !s.rejected,
      }));

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions,
          sections: updatedSections,
          updatedAt: '刚刚',
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

/**
 * 更新指定 bullet 的文本（section/item/bullet 逐层定位）。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, bulletId, newText }
 */
export function useUpdateResumeBulletTextMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    sectionId: string;
    itemId: string;
    bulletId: string;
    newText: string;
  }>({
    mutationFn: async ({ resumeId, sectionId, itemId, bulletId, newText }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: item.bullets.map((b) =>
                b.id === bulletId ? { ...b, text: newText } : b,
              ),
            };
          }),
        };
      });

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚',
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

/**
 * 向指定 item 追加一条 bullet（legacy `addResumeBullet`，当前无 UI 消费，保留域能力）。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, text, experienceId? }
 */
export function useAddResumeBulletMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    sectionId: string;
    itemId: string;
    text: string;
    experienceId?: string;
  }>({
    mutationFn: async ({ resumeId, sectionId, itemId, text, experienceId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const newBullet = {
        id: 'bullet-' + Date.now(),
        text,
        originalExperienceId: experienceId,
        jdMatchTag: experienceId ? '来源经历资产 · 关联' : '自定义补充',
      };

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: [...item.bullets, newBullet],
            };
          }),
        };
      });

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚',
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

/**
 * 删除指定 bullet。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, bulletId }
 */
export function useDeleteResumeBulletMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    sectionId: string;
    itemId: string;
    bulletId: string;
  }>({
    mutationFn: async ({ resumeId, sectionId, itemId, bulletId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: item.bullets.filter((b) => b.id !== bulletId),
            };
          }),
        };
      });

      return {
        ...prev,
        [resumeId]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚',
        },
      };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}

// ---------------------------------------------------------------------------
// 保存 / 生成写路径
// ---------------------------------------------------------------------------

export type SaveResumeMutationResult =
  | { saved: true; markdown: string }
  | { saved: false; reason: 'local' };

/**
 * 保存简历草稿。与 legacy `JobCraftContext.saveResume` 行为等价：
 * - `resumeToMarkdown` 序列化 → `Number(resumeId)` 非数字视为本地示例（resolve `{saved:false, reason:'local'}`，
 *   视图 warning toast，等价 legacy 早退）；
 * - 合法 id `await jobApi.updateSubmission(submissionId, { resume_markdown })`，失败抛错（视图 error toast）；
 * - 成功后 cache 更新 `updatedAt='刚刚'`。业务代码不留 console（AGENTS 红线）。
 */
export function useSaveResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<SaveResumeMutationResult, unknown, { resumeId: string }>({
    mutationFn: async ({ resumeId }) => {
      const prev = readResumesMap(queryClient);
      const resume = prev[resumeId];
      if (!resume) throw new Error('未找到对应的简历');

      const markdown = resumeToMarkdown(resume);
      const submissionId = Number(resumeId);
      if (Number.isNaN(submissionId)) {
        return { saved: false, reason: 'local' as const };
      }
      await jobApi.updateSubmission(submissionId, { resume_markdown: markdown });
      return { saved: true, markdown };
    },
    onSuccess: (result, { resumeId }) => {
      if (!result.saved) return;
      const prev = readResumesMap(queryClient);
      const resume = prev[resumeId];
      if (!resume) return;
      writeResumesMap(queryClient, {
        ...prev,
        [resumeId]: { ...resume, updatedAt: '刚刚' },
      });
    },
  });
}

/**
 * 将生成的简历并入 RESUMES cache（JD 生成写路径：`JDReportDetailView` 调 API save-resume 成功后写入）。
 * 纯 cache 写，无 API。
 * @param mutationFn 入参 { resumeId, resume }，以 resumeId = submission id（字符串）键控
 */
export function useUpsertResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, ResumeVersion>, unknown, {
    resumeId: string;
    resume: ResumeVersion;
  }>({
    mutationFn: async ({ resumeId, resume }) => {
      const prev = readResumesMap(queryClient);
      return { ...prev, [resumeId]: resume };
    },
    onSuccess: (next) => writeResumesMap(queryClient, next),
  });
}