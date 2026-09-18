import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import * as tasksApi from '../../api/tasks';
import type { JobAnalysisResult, ATSProfile } from '../../api/types';
import type { Experience, JDAnalysis, Job } from '../../types/jobcraft';
import {
  JD_ANALYSES_QUERY_KEY,
  analysisDetailToJD,
  analysisToJD,
  dutiesText,
  requirementsText,
  structuredResultToJD,
} from './mappers';
import { JOBS_QUERY_KEY, deriveJobStatus } from '../jobs/mappers';
import { EXPERIENCES_QUERY_KEY } from '../experiences/mappers';

type StructuredJdResult = Awaited<ReturnType<typeof jobApi.analyzeStructuredJd>>;

interface JDMutationOptions {
  /** context 镜像写入（过渡期）：cache 更新后同步回 context.jdAnalyses，供未迁移视图读取。 */
  onSync?: (analyses: JDAnalysis[]) => void;
  /** 跨域镜像写入（过渡期）：JD 创建会补写 jobs 缓存，同步回 context.jobs。 */
  onSyncJobs?: (jobs: Job[]) => void;
}

function readJdAnalyses(client: QueryClient): JDAnalysis[] {
  return client.getQueryData<JDAnalysis[]>([...JD_ANALYSES_QUERY_KEY]) || [];
}

function readJobs(client: QueryClient): Job[] {
  return client.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
}

interface ResolveTargetJobParams {
  company: string;
  role: string;
  jobId?: string;
  jdAnalysisId: string;
  currentStage: string;
  nextAction: string;
}

/**
 * 解析/创建目标岗位：显式 jobId 直接复用；否则按「公司+岗位」查找，未命中则创建自动岗位。
 *
 * 与 legacy `createJDAnalysis`/`createStructuredJDAnalysis` 行为一致：自动岗位仅写入本地
 * jobs 缓存（不产生后端提交），并将 `jdAnalysisId` 预置为合成 id。
 */
function resolveTargetJob(client: QueryClient, params: ResolveTargetJobParams): string {
  if (params.jobId) return params.jobId;

  const jobs = readJobs(client);
  const existing = jobs.find((j) => j.company === params.company && j.role === params.role);
  if (existing) return existing.id;

  const jobId = 'job-' + Date.now();
  const steps: Job['steps'] = {
    jdAnalysis: true,
    expMatched: true,
    customResume: false,
    applied: false,
    prepStage: 'pending',
    reviewStage: 'pending'
  };
  const autoJob: Job = {
    id: jobId,
    company: params.company,
    role: params.role,
    department: '核心业务线',
    salaryRange: '面议',
    status: deriveJobStatus(steps),
    matchScore: 0,
    applyDate: new Date().toISOString().split('T')[0],
    lastUpdated: '刚刚',
    currentStage: params.currentStage,
    nextAction: params.nextAction,
    steps,
    jdAnalysisId: params.jdAnalysisId,
    interviewIds: []
  };
  client.setQueryData([...JOBS_QUERY_KEY], [autoJob, ...jobs]);
  return jobId;
}

/**
 * 创建 JD 分析（原始文本路径）。与 legacy `JobCraftContext.createJDAnalysis` 行为等价：
 * find-or-create 岗位 → runTaskOrSync('resume_generate', fallback=analyzeJob) → analysisToJD 回填 cache，
 * 完成后将岗位 jdAnalysisId 更新为后端真实 job_analysis_id。
 *
 * 区别于 fire-and-forget 的 legacy 实现：本 hook 返回 Promise，完成（或失败）时 resolve/reject。
 */
export function useCreateJdAnalysisMutation(options: JDMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync, onSyncJobs } = options;

  return useMutation({
    mutationFn: async (data: { company: string; role: string; rawText: string; jobId?: string }) => {
      const user = await authApi.getCurrentUser();
      const newId = 'jd-' + Date.now();
      const targetJobId = resolveTargetJob(queryClient, {
        company: data.company,
        role: data.role,
        jobId: data.jobId,
        jdAnalysisId: newId,
        currentStage: '已完成 JD 分析 · 待投递',
        nextAction: '已完成 JD 深度分析，可开始定制简历并投递'
      });
      onSyncJobs?.(readJobs(queryClient));

      const cardIds = (queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [])
        .map((e) => parseInt(e.id))
        .filter((id) => !isNaN(id));

      const result = await tasksApi.runTaskOrSync<JobAnalysisResult>(
        'resume_generate',
        {
          user_id: user.id,
          company: data.company,
          position: data.role,
          jd_text: data.rawText,
          card_ids: cardIds
        },
        () => jobApi.analyzeJob({ position: data.role, company: data.company, jd_text: data.rawText, card_ids: cardIds }),
        { timeout: 180_000 }
      );

      const newAnalysis = analysisToJD(result, targetJobId);
      queryClient.setQueryData(
        [...JD_ANALYSES_QUERY_KEY],
        (prev: JDAnalysis[] | undefined) => [newAnalysis, ...(prev || [])]
      );
      onSync?.(readJdAnalyses(queryClient));

      const jobs = readJobs(queryClient);
      const nextJobs = jobs.map((j) =>
        j.id === targetJobId
          ? {
              ...j,
              jdAnalysisId: String(result.job_analysis_id),
              matchScore: result.match_score || 0,
              steps: { ...j.steps, jdAnalysis: true, expMatched: true }
            }
          : j
      );
      queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);
      onSyncJobs?.(nextJobs);

      return newAnalysis;
    },
  });
}

/**
 * 创建结构化 JD 分析。与 legacy `JobCraftContext.createStructuredJDAnalysis` 行为等价：
 * find-or-create 岗位 → runTaskOrSync('jd_analyze_structured', fallback=analyzeStructuredJd) →
 * structuredResultToJD 构建本地分析记录（合成 id + matchScore 0）并前置 cache。
 *
 * 区别于 fire-and-forget 的 legacy 实现：本 hook 返回 Promise，完成（或失败）时 resolve/reject。
 */
export function useCreateStructuredJdAnalysisMutation(options: JDMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync, onSyncJobs } = options;

  return useMutation({
    mutationFn: async (data: {
      company: string;
      role: string;
      duties: string[];
      requirements: { text: string; tag: 'hard' | 'required' | 'preferred' }[];
      jobId?: string;
    }) => {
      const user = await authApi.getCurrentUser();
      const newId = 'jd-' + Date.now();
      const targetJobId = resolveTargetJob(queryClient, {
        company: data.company,
        role: data.role,
        jobId: data.jobId,
        jdAnalysisId: newId,
        currentStage: '已完成结构化 JD 分析 · 待投递',
        nextAction: '已完成结构化 JD 分析，可开始定制简历并投递'
      });
      onSyncJobs?.(readJobs(queryClient));

      const result = await tasksApi.runTaskOrSync<StructuredJdResult>(
        'jd_analyze_structured',
        {
          user_id: user.id,
          company: data.company,
          position: data.role,
          duties: data.duties,
          requirements: data.requirements
        },
        () => jobApi.analyzeStructuredJd({
          company: data.company,
          position: data.role,
          duties: data.duties,
          requirements: data.requirements
        }),
        { timeout: 120_000 }
      );

      const newAnalysis = structuredResultToJD(result as { ats_profile?: ATSProfile | null }, {
        id: newId,
        jobId: targetJobId,
        company: data.company,
        role: data.role,
        rawText: [dutiesText(data.duties), requirementsText(data.requirements)].join('\n')
      });
      queryClient.setQueryData(
        [...JD_ANALYSES_QUERY_KEY],
        (prev: JDAnalysis[] | undefined) => [newAnalysis, ...(prev || [])]
      );
      onSync?.(readJdAnalyses(queryClient));

      const jobs = readJobs(queryClient);
      const nextJobs = jobs.map((j) =>
        j.id === targetJobId
          ? { ...j, jdAnalysisId: newId, steps: { ...j.steps, jdAnalysis: true } }
          : j
      );
      queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);
      onSyncJobs?.(nextJobs);

      return newAnalysis;
    },
  });
}

/**
 * 查询当前用户的 JD 分析历史（listJobAnalyses → 逐条 getJobAnalysis → analysisDetailToJD）。
 *
 * 与 legacy `JobCraftContext.loadJdAnalyses` 语义一致：先取摘要列表，再并发拉取每条完整详情；
 * 单条详情失败时跳过该条（不外抛），userId 取自已认证用户的 auth profile。
 */
export function useJdAnalysesQuery() {
  return useQuery({
    queryKey: [...JD_ANALYSES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.listJobAnalyses(user.id);
      const summaries = data.analyses || [];
      const fullAnalyses = await Promise.all(
        summaries.map(async (s) => {
          try {
            const summary = s as { id?: number; job_analysis_id?: number };
            const detail = await jobApi.getJobAnalysis(Number(summary.id || summary.job_analysis_id));
            return analysisDetailToJD(detail);
          } catch {
            return null;
          }
        }),
      );
      return fullAnalyses.filter(Boolean) as JDAnalysis[];
    },
  });
}

/**
 * 删除 JD 分析。与 legacy `JobCraftContext.deleteJDAnalysis` 行为等价：
 * 仅从前端状态移除；id 形如 `sub-{number}` 时尝试删除后端 submission（失败忽略）；
 * 后端无 JD 分析删除端点，故真实分析 id（数字串）不产生网络删除请求。
 */
export function useDeleteJdAnalysisMutation(options: JDMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync } = options;

  return useMutation<string, unknown, string>({
    mutationFn: async (id) => {
      const match = id.match(/^sub-(\d+)$/);
      if (match) {
        try {
          await jobApi.deleteSubmission(Number(match[1]));
        } catch {
          /* ignore */
        }
      }
      return id;
    },
    onSuccess: (id) => {
      const prev = queryClient.getQueryData<JDAnalysis[]>([...JD_ANALYSES_QUERY_KEY]) || [];
      const next = prev.filter((a) => a.id !== id);
      queryClient.setQueryData([...JD_ANALYSES_QUERY_KEY], next);
      onSync?.(next);
    },
  });
}
