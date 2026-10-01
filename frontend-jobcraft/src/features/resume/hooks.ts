import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import * as tasksApi from '../../api/tasks';
import type { ResumeSuggestionWire } from '../../api/types';
import { ResumeVersion } from '../../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../../utils/resumeParser';
import {
  buildSuggestionBullets,
  hydrateResumeSuggestions,
  suggestionsToWire,
} from '../../utils/resumeSuggestionMapper';
import { RESUMES_QUERY_KEY } from './mappers';
import { JOBS_QUERY_KEY } from '../jobs/mappers';

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
 * FE-RESUME-02：统一落库出口（PATCH /submission/{id}）。
 * - resume_markdown：正文变更（生成/编辑/增删/应用改写）
 * - resume_suggestions：建议状态变更（生成落库/应用/忽略）
 * 本地示例（resumeId 非数字）跳过 API，返回 synced=false（调用方 toast 提示）。
 * FE-CACHE-01：submission 写入后重验 jobs 镜像（两键同源于 getDashboard，
 * resume_markdown 会翻转 dashboard 的 has_resume，只补 RESUMES 会漂移）。
 * @returns 是否已同步后端；PATCH 失败上抛（调用方 error toast）
 */
async function persistResumePatch(
  queryClient: ReturnType<typeof useQueryClient>,
  resumeId: string,
  patch: {
    resume_markdown?: string;
    resume_suggestions?: ResumeSuggestionWire[];
  },
): Promise<boolean> {
  const submissionId = Number(resumeId);
  if (Number.isNaN(submissionId)) return false;
  await jobApi.updateSubmission(submissionId, patch);
  queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
  return true;
}

/** 按 bullet id 在 sections 中定位 bullet（apply 运行时防错位校验用）。 */
function findBulletById(
  sections: ResumeVersion['sections'],
  bulletId: string,
): { text: string } | null {
  for (const sec of sections) {
    for (const item of sec.items || []) {
      for (const b of item.bullets || []) {
        if (b.id === bulletId) return b;
      }
    }
  }
  return null;
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
            if (!resume) return null;
            // FE-RESUME-02：挂载存量 AI 建议（定位失败的 pending → stale）
            resume.aiSuggestions = hydrateResumeSuggestions(
              resume,
              detail.resume_suggestions,
            );
            return [String(item.id), resume] as const;
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
 * 应用单条 AI 优化建议：命中 `targetBulletId` 时改写 bullet 文本，标记 applied，
 * 并落库 PATCH {resume_markdown, resume_suggestions}（失败上抛 → 视图 error toast）。
 * 运行时防错位：目标要点已删除 / 原文已变更 → 抛错（提示重新生成），不覆盖用户编辑。
 * @param mutationFn 入参 { resumeId, suggestionId }；返回 { synced }（本地示例为 false）
 */
export function useApplyResumeAiSuggestionMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean }, unknown, {
    resumeId: string;
    suggestionId: string;
  }>({
    mutationFn: async ({ resumeId, suggestionId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const sug = (activeResume.aiSuggestions || []).find((s) => s.id === suggestionId);
      if (!sug) throw new Error('未找到该条优化建议');
      if (sug.stale) throw new Error('该建议已失效（对应要点已变更），请重新生成');

      let updatedSections = [...activeResume.sections];
      let textChanged = false;

      if (sug.targetBulletId) {
        const target = findBulletById(activeResume.sections, sug.targetBulletId);
        if (!target) throw new Error('建议对应要点已被删除，请重新生成建议');
        if (target.text.trim() !== sug.originalText.trim()) {
          throw new Error('要点原文已变更，请重新生成建议');
        }
        updatedSections = updatedSections.map((sec) => ({
          ...sec,
          items: sec.items.map((item) => ({
            ...item,
            bullets: item.bullets.map((b) =>
              b.id === sug.targetBulletId ? { ...b, text: sug.suggestedText } : b,
            ),
          })),
        }));
        textChanged = true;
      }

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) =>
        s.id === suggestionId ? { ...s, applied: true, rejected: false, stale: undefined } : s,
      );

      const nextResume = {
        ...activeResume,
        aiSuggestions: updatedSuggestions,
        sections: updatedSections,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        ...(textChanged ? { resume_markdown: resumeToMarkdown(nextResume) } : {}),
        resume_suggestions: suggestionsToWire(updatedSuggestions, nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced };
    },
  });
}

/**
 * 忽略单条 AI 优化建议（标记 rejected，正文不变），落库 PATCH {resume_suggestions}。
 * @param mutationFn 入参 { resumeId, suggestionId }；返回 { synced }
 */
export function useRejectResumeAiSuggestionMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean }, unknown, {
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

      const nextResume = {
        ...activeResume,
        aiSuggestions: updatedSuggestions,
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_suggestions: suggestionsToWire(updatedSuggestions, nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced };
    },
  });
}

/**
 * 全部应用 AI 优化建议：逐个改写 target bullet 文本（已 reject / stale 跳过，
 * 目标已删或原文已变的条目标记 stale 并跳过），全部标记 applied，
 * 落库 PATCH {resume_markdown, resume_suggestions}。
 * @param mutationFn 入参 { resumeId }；返回 { synced, appliedCount }
 */
export function useApplyAllResumeAiSuggestionsMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean; appliedCount: number }, unknown, { resumeId: string }>({
    mutationFn: async ({ resumeId }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      let updatedSections = [...activeResume.sections];
      let textChanged = false;
      let appliedCount = 0;

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((sug) => {
        if (sug.rejected || sug.applied || sug.stale) return sug;

        const target = sug.targetBulletId
          ? findBulletById(activeResume.sections, sug.targetBulletId)
          : null;
        if (sug.targetBulletId && (!target || target.text.trim() !== sug.originalText.trim())) {
          // 目标失效：标记 stale，跳过改写（不阻断其余建议）
          return { ...sug, stale: true };
        }
        if (sug.targetBulletId && target) {
          const bulletId = sug.targetBulletId;
          updatedSections = updatedSections.map((sec) => ({
            ...sec,
            items: sec.items.map((item) => ({
              ...item,
              bullets: item.bullets.map((b) =>
                b.id === bulletId ? { ...b, text: sug.suggestedText } : b,
              ),
            })),
          }));
          textChanged = true;
          appliedCount += 1;
          return { ...sug, applied: true, rejected: false, stale: undefined };
        }
        // 无 targetBulletId（历史数据）：仅标记 applied，不改写正文
        appliedCount += 1;
        return { ...sug, applied: true };
      });

      const nextResume = {
        ...activeResume,
        aiSuggestions: updatedSuggestions,
        ...(textChanged ? { sections: updatedSections, updatedAt: '刚刚' } : {}),
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        ...(textChanged ? { resume_markdown: resumeToMarkdown(nextResume) } : {}),
        resume_suggestions: suggestionsToWire(updatedSuggestions, nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced, appliedCount };
    },
  });
}

/**
 * 更新指定 bullet 的文本（section/item/bullet 逐层定位）。
 * 落库 PATCH {resume_markdown}（FE-RESUME-02：编辑即落库，修「假 toast」）；
 * 命中该要点的 pending 建议同步标记 stale（原文已变，防止误覆盖）。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, bulletId, newText }；返回 { synced }
 */
export function useUpdateResumeBulletTextMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean }, unknown, {
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

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) =>
        s.targetBulletId === bulletId && !s.applied && !s.rejected
          ? { ...s, stale: true }
          : s,
      );

      const nextResume = {
        ...activeResume,
        sections: updatedSections,
        aiSuggestions: updatedSuggestions,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_markdown: resumeToMarkdown(nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced };
    },
  });
}

/**
 * 向指定 item 追加一条 bullet（legacy `addResumeBullet`，当前无 UI 消费，保留域能力）。
 * 落库 PATCH {resume_markdown}；存量建议靠 original_text 全文兜底重定位（索引后移不判 stale）。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, text, experienceId? }；返回 { synced }
 */
export function useAddResumeBulletMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean }, unknown, {
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

      const nextResume = {
        ...activeResume,
        sections: updatedSections,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_markdown: resumeToMarkdown(nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced };
    },
  });
}

/**
 * 删除指定 bullet。落库 PATCH {resume_markdown}；
 * 指向该要点的 pending 建议标记 stale（防止 dangling 应用）。
 * @param mutationFn 入参 { resumeId, sectionId, itemId, bulletId }；返回 { synced }
 */
export function useDeleteResumeBulletMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean }, unknown, {
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

      const updatedSuggestions = (activeResume.aiSuggestions || []).map((s) =>
        s.targetBulletId === bulletId && !s.applied && !s.rejected
          ? { ...s, stale: true }
          : s,
      );

      const nextResume = {
        ...activeResume,
        sections: updatedSections,
        aiSuggestions: updatedSuggestions,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_markdown: resumeToMarkdown(nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced };
    },
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
      // FE-CACHE-01：submission.resume_markdown 落库翻转 dashboard has_resume，
      // 定向重验 jobs 镜像，避免岗位卡片仍显示「无简历」
      queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
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

export interface GenerateSuggestionsResult {
  /** 是否完成生成（本地示例/无要点为 false） */
  generated: boolean;
  /** 本次生成的建议条数 */
  count: number;
  reason?: 'local' | 'empty';
  /** 新建议是否已落库（PATCH resume_suggestions） */
  synced: boolean;
}

/**
 * FE-RESUME-02：生成简历 AI 优化建议（方案 B 触发点：JD 生成简历后自动 fire + 编辑器按钮）。
 *
 * - 输入：结构化 bullets（sections→items→bullets 展平，与水合共用索引契约）；
 *   岗位上下文由服务端自取（JD 分析产物），前端不传 JD 数据；
 * - 任务系统可用走 `resume_suggest` 任务，不可用降级同步端点 `suggestResume`；
 * - 生成结果替换 pending 建议、保留 applied/rejected 历史，并 PATCH 落库；
 * - 失败上抛（调用方 error toast）；本地示例返回 {generated:false, reason:'local'}。
 * @param mutationFn 入参 { resumeId }
 */
export function useGenerateResumeSuggestionsMutation() {
  const queryClient = useQueryClient();

  return useMutation<GenerateSuggestionsResult, unknown, { resumeId: string }>({
    mutationFn: async ({ resumeId }) => {
      const prev = readResumesMap(queryClient);
      const resume = prev[resumeId];
      if (!resume) throw new Error('未找到对应的简历');

      const submissionId = Number(resumeId);
      if (Number.isNaN(submissionId)) {
        return { generated: false, count: 0, reason: 'local', synced: false };
      }
      const bullets = buildSuggestionBullets(resume);
      if (!bullets.length) {
        return { generated: false, count: 0, reason: 'empty', synced: false };
      }

      const user = await authApi.getCurrentUser();
      const result = await tasksApi.runTaskOrSync<{ suggestions?: ResumeSuggestionWire[] }>(
        'resume_suggest',
        { submission_id: submissionId, user_id: user.id, bullets },
        () => jobApi.suggestResume(submissionId, bullets),
        { timeout: 120_000 },
      );
      const wires = result?.suggestions || [];

      const history = (resume.aiSuggestions || []).filter((s) => s.applied || s.rejected);
      const updatedSuggestions = [
        ...history,
        ...hydrateResumeSuggestions(resume, wires),
      ];
      const nextResume = {
        ...resume,
        aiSuggestions: updatedSuggestions,
        updatedAt: '刚刚',
      };

      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_suggestions: suggestionsToWire(updatedSuggestions, nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { generated: true, count: wires.length, synced };
    },
  });
}