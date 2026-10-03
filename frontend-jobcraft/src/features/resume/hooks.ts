import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as jobApi from '../../api/job';
import type { ResumePersonalInfo, ResumeSuggestionWire } from '../../api/types';
import { ResumeVersion } from '../../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../../utils/resumeParser';
import { suggestionsToWire } from '../../utils/resumeSuggestionMapper';
import { RESUMES_QUERY_KEY } from './mappers';
import { JOBS_QUERY_KEY } from '../jobs/mappers';

/**
 * 读取当前 RESUMES cache。
 * 简历 map 为 `Record<versionId, ResumeVersion>`（versionId 为字符串，T-M6-2 起
 * 以 resume_version id 为身份；此前为 submission id），缺失时回退空对象。
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
 * FE-RESUME-02：统一落库出口（PATCH /resume-version/{id}，T-M6-2 起版本维度）。
 * - resume_markdown：正文变更（生成/编辑/增删/应用改写）
 * - resume_suggestions：版本表无此列（V0021 Q1-B），切换后暂不持久化——建议域
 *   仍挂 submission，M6-3（矩阵：下线/重构 aiSuggestions mutation）统一接回
 * - 本地示例（resumeId 非数字）跳过 API，返回 false（调用方 toast 提示）
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
  const versionId = Number(resumeId);
  if (Number.isNaN(versionId)) return false;
  const versionPatch = { ...patch };
  delete versionPatch.resume_suggestions;
  if (!Object.keys(versionPatch).length) return false;
  await jobApi.updateResumeVersion(versionId, versionPatch);
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
 * 查询简历编辑 map（T-M6-2：读源切换为 resume_version，不再经 dashboard/getSubmission）。
 * - `GET /api/jobcraft/resume-version` 全量（后端已按 version_no DESC 排序）→
 *   按岗位归组取最新一条；
 * - 归组键：job_analysis_id（存量版本可能无 job 行，FE 地图以 jdAnalysisId 关联），
 *   缺失回退 job_id，再回退版本 id（单行组）；
 * - 键 = 版本 id（字符串），resumeId 语义随之从 submission id 切换；
 * - resume_suggestions 挂 submission（V0021 无此列），存量 AI 建议暂不水合（M6-3 债）。
 * @returns 以版本 id（字符串）为键的简历 map
 */
export function useResumesQuery() {
  return useQuery({
    queryKey: [...RESUMES_QUERY_KEY],
    queryFn: async () => {
      const versions = await jobApi.listResumeVersions();
      const latestByJob = new Map<string, (typeof versions)[number]>();
      for (const v of versions) {
        const group = String(v.job_analysis_id ?? v.job_id ?? v.id);
        if (!latestByJob.has(group)) latestByJob.set(group, v);
      }
      const next: Record<string, ResumeVersion> = {};
      for (const v of latestByJob.values()) {
        const resume = markdownToResume(v.resume_markdown, {
          position: v.position ?? '',
          company: v.company ?? '',
          id: String(v.id),
        });
        if (resume) next[String(v.id)] = resume;
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
 * FE-RESUME-03：从个人资料同步简历头部个人信息。
 * - 仅覆盖 profile 侧非空字段（profile 空白不冲掉简历上已手动微调的值，保留手动编辑）；
 * - 落库 PATCH {resume_markdown}（头部变更走与正文一致的持久化路径）；
 * - 无任何字段可覆盖时返回 {synced:false, applied:[]}（调用方提示，不视为错误）。
 * @param mutationFn 入参 { resumeId, personalInfo }（视图层已完成 profile→personalInfo 字段映射）；返回 { synced, applied }
 */
export function useSyncResumePersonalInfoMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean; applied: string[] }, unknown, {
    resumeId: string;
    personalInfo: Partial<ResumeVersion['personalInfo']>;
  }>({
    mutationFn: async ({ resumeId, personalInfo }) => {
      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const merged = { ...activeResume.personalInfo };
      const applied: string[] = [];
      for (const key of Object.keys(personalInfo) as (keyof ResumeVersion['personalInfo'])[]) {
        const value = personalInfo[key];
        if (typeof value === 'string' && value.trim()) {
          merged[key] = value.trim();
          applied.push(key);
        }
      }
      if (!applied.length) return { synced: false, applied };

      const nextResume = {
        ...activeResume,
        personalInfo: merged,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_markdown: resumeToMarkdown(nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced, applied };
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
 * 保存简历草稿（T-M6-2：落库 PATCH /resume-version/{id}，版本维度）。
 * - `resumeToMarkdown` 序列化 → `Number(resumeId)` 非数字视为本地示例（resolve `{saved:false, reason:'local'}`，
 *   视图 warning toast，等价 legacy 早退）；
 * - 合法 id `await jobApi.updateResumeVersion(versionId, { resume_markdown })`，失败抛错（视图 error toast）；
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
      const versionId = Number(resumeId);
      if (Number.isNaN(versionId)) {
        return { saved: false, reason: 'local' as const };
      }
      await jobApi.updateResumeVersion(versionId, { resume_markdown: markdown });
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
      // FE-CACHE-01：岗位卡片 customResume 步骤按版本存在性判定（T-M6-2 起
      // 不再依赖 dashboard has_resume），版本落库后重验 jobs 镜像
      queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
    },
  });
}

export interface GenerateResumeFromJdArgs {
  jobAnalysisId: number;
  selectedCardIds: number[];
  personalInfo?: Partial<ResumePersonalInfo>;
  /** markdownToResume 的兜底元数据（JD 分析的岗位/公司） */
  position: string;
  company: string;
}

/**
 * JD 报告页「生成简历」（save-resume 端点）：生成简历并把 markdown 解析为 ResumeVersion。
 * 返回 { resumeId, resume }（T-M6-2：resumeId = resume_version id 字符串），由调用方接
 * useUpsertResumeMutation 并入 RESUMES cache；端点未回 markdown/id 或解析失败
 * 返回 null（不视为错误，调用方跳过缓存写入）；失败上抛（调用方 error toast）。
 */
export function useGenerateResumeFromJdMutation() {
  return useMutation<
    { resumeId: string; resume: ResumeVersion } | null,
    unknown,
    GenerateResumeFromJdArgs
  >({
    mutationFn: async ({ jobAnalysisId, selectedCardIds, personalInfo, position, company }) => {
      const result = await jobApi.saveResume({
        job_analysis_id: jobAnalysisId,
        selected_card_ids: selectedCardIds,
        personal_info: personalInfo,
      });
      if (!result.resume_markdown || !result.resume_version_id) return null;
      const resume = markdownToResume(result.resume_markdown, {
        position,
        company,
        id: String(result.resume_version_id),
      });
      if (!resume) return null;
      return { resumeId: String(result.resume_version_id), resume };
    },
  });
}

/**
 * 将生成的简历并入 RESUMES cache（JD 生成写路径：`JDReportDetailView` 经
 * useGenerateResumeFromJdMutation 生成成功后写入）。
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
  /** 是否完成生成（本地示例/无要点/暂不可用为 false） */
  generated: boolean;
  /** 本次生成的建议条数 */
  count: number;
  reason?: 'local' | 'empty' | 'unavailable';
  /** 新建议是否已落库（PATCH resume_suggestions） */
  synced: boolean;
}

/**
 * FE-RESUME-02：生成简历 AI 优化建议。
 *
 * T-M6-2 暂停：服务端建议链（`suggestResume` 端点 / `resume_suggest` 任务）仍以
 * submission id 取数，而 resumeId 已切换为 resume_version id——继续调用会以错误
 * id 打到 submission。简历读写身份迁移期间固定返回 `{reason:'unavailable'}`，
 * 待 M6-3（矩阵：下线/重构 aiSuggestions 空壳 mutation）以版本维度接回。
 * @param mutationFn 入参 { resumeId }
 */
export function useGenerateResumeSuggestionsMutation() {
  return useMutation<GenerateSuggestionsResult, unknown, { resumeId: string }>({
    mutationFn: async () => ({
      generated: false,
      count: 0,
      reason: 'unavailable' as const,
      synced: false,
    }),
  });
}