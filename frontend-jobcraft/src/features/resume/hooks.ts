import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as jobApi from '../../api/job';
import type { ResumePersonalInfo } from '../../api/types';
import { ResumeVersion } from '../../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../../utils/resumeParser';
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
 * - resume_markdown：正文变更（生成/编辑/增删/AI 改写）
 * - 本地示例（resumeId 非数字）跳过 API，返回 false（调用方 toast 提示）
 * @returns 是否已同步后端；PATCH 失败上抛（调用方 error toast）
 */
async function persistResumePatch(
  queryClient: ReturnType<typeof useQueryClient>,
  resumeId: string,
  patch: { resume_markdown?: string },
): Promise<boolean> {
  const versionId = Number(resumeId);
  if (Number.isNaN(versionId)) return false;
  if (!patch.resume_markdown) return false;
  await jobApi.updateResumeVersion(versionId, patch);
  queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
  return true;
}

/**
 * 查询简历编辑 map（T-M6-2：读源切换为 resume_version，不再经 dashboard/getSubmission）。
 * - `GET /api/jobcraft/resume-version` 全量（后端已按 version_no DESC 排序）→
 *   按岗位归组取最新一条；
 * - 归组键：job_analysis_id（存量版本可能无 job 行，FE 地图以 jdAnalysisId 关联），
 *   缺失回退 job_id，再回退版本 id（单行组）；
 * - 键 = 版本 id（字符串），resumeId 语义随之从 submission id 切换；
 * - jobAnalysisId 挂到简历上（T-M6-3 缺口任务列取数键）。
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
        if (resume) {
          next[String(v.id)] =
            v.job_analysis_id != null
              ? { ...resume, jobAnalysisId: String(v.job_analysis_id) }
              : resume;
        }
      }
      return next;
    },
  });
}

// ---------------------------------------------------------------------------
// 纯编辑 mutation（cache 内函数式更新，无 API）
// ---------------------------------------------------------------------------

/**
 * FE-RESUME-02：更新指定 bullet 的文本（section/item/bullet 逐层定位）。
 * 落库 PATCH {resume_markdown}（FE-RESUME-02：编辑即落库，修「假 toast」）。
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
 * 落库 PATCH {resume_markdown}。
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
 * 删除指定 bullet。落库 PATCH {resume_markdown}。
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
      return {
        resumeId: String(result.resume_version_id),
        resume: { ...resume, jobAnalysisId: String(jobAnalysisId) },
      };
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

export interface RewriteResumeBulletGap {
  /** 能力维度（D1-D8 / EXT） */
  dimension: string;
  /** 缺口现状 */
  current: string;
  /** JD 原文证据 */
  jdEvidence: string;
  /** 改写方向 */
  rewriteHint: string;
}

/**
 * T-M6-3：按能力缺口 AI 改写选中要点（POST /resume-version/{id}/rewrite，1 次 LLM）。
 * - 先调 rewrite 端点拿 rewritten_text（失败上抛 → 视图 error toast）；
 * - 缓存内替换 bullet 文本后 PATCH {resume_markdown} 落库；
 * - 本地示例（resumeId 非数字）/ 要点已不存在 → 抛错，不覆盖用户数据。
 * @param mutationFn 入参 { resumeId, bulletId, gap }；返回 { synced, rewrittenText }
 */
export function useRewriteResumeBulletMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ synced: boolean; rewrittenText: string }, unknown, {
    resumeId: string;
    bulletId: string;
    gap: RewriteResumeBulletGap;
  }>({
    mutationFn: async ({ resumeId, bulletId, gap }) => {
      const versionId = Number(resumeId);
      if (Number.isNaN(versionId)) throw new Error('本地示例不支持 AI 改写');

      const prev = readResumesMap(queryClient);
      const activeResume = prev[resumeId];
      if (!activeResume) throw new Error('未找到对应的简历');

      const originalText = activeResume.sections
        .flatMap((sec) => sec.items || [])
        .flatMap((item) => item.bullets || [])
        .find((b) => b.id === bulletId)?.text;
      if (!originalText) throw new Error('选中要点已不存在，请重新点选');

      const { rewritten_text } = await jobApi.rewriteResumeBullet(versionId, {
        original_text: originalText,
        dimension: gap.dimension,
        gap_current: gap.current,
        jd_evidence: gap.jdEvidence,
        rewrite_hint: gap.rewriteHint,
      });

      const updatedSections = activeResume.sections.map((sec) => ({
        ...sec,
        items: (sec.items || []).map((item) => ({
          ...item,
          bullets: (item.bullets || []).map((b) =>
            b.id === bulletId ? { ...b, text: rewritten_text } : b,
          ),
        })),
      }));
      const nextResume = {
        ...activeResume,
        sections: updatedSections,
        updatedAt: '刚刚',
      };
      const synced = await persistResumePatch(queryClient, resumeId, {
        resume_markdown: resumeToMarkdown(nextResume),
      });
      writeResumesMap(queryClient, { ...prev, [resumeId]: nextResume });
      return { synced, rewrittenText: rewritten_text };
    },
  });
}