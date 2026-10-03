import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import * as tasksApi from '../../api/tasks';
import type { JobAnalysisResult } from '../../api/types';
import type { Experience, JDAnalysis, Job } from '../../types/jobcraft';
import {
  JD_ANALYSES_QUERY_KEY,
  analysisDetailToJD,
  analysisToJD,
} from './mappers';
import { JOBS_QUERY_KEY, deriveJobStatus } from '../jobs/mappers';
import { EXPERIENCES_QUERY_KEY } from '../experiences/mappers';


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
    // T-M5-7 / Q4：兜底假文案中性化（自动岗不造「核心业务线」假部门）
    department: '',
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
export function useCreateJdAnalysisMutation() {
  const queryClient = useQueryClient();


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


      const jobs = readJobs(queryClient);
      const nextJobs = jobs.map((j) =>
        j.id === targetJobId
          ? {
              ...j,
              // T-M5-5（jd-byte-1）：后端 job 实体 id 回填，本地合成岗对齐实体行 id
              ...(result.job_id != null
                ? { id: `job-${result.job_id}`, jobId: result.job_id }
                : {}),
              jdAnalysisId: String(result.job_analysis_id),
              matchScore: result.match_score || 0,
              steps: { ...j.steps, jdAnalysis: true, expMatched: true }
            }
          : j
      );
      queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);


      return newAnalysis;
    },
  });
}

/**
 * 创建结构化 JD 分析。T-M4-1：结构化字段注入后端 4 节点工作流（Q2 裁决 C）。
 * find-or-create 岗位 → runTaskOrSync('jd_analyze_structured', fallback=analyzeStructuredJd) →
 * analysisToJD 回填 cache；完成后将岗位 jdAnalysisId 更新为后端真实 job_analysis_id
 * （合成 id 仅作 find-or-create 占位，FE-JD-REPORT-01 双轨 id 根因消除，
 * 报告页降级展示自此仅作兜底）。
 *
 * 区别于 fire-and-forget 的 legacy 实现：本 hook 返回 Promise，完成（或失败）时 resolve/reject。
 */
export function useCreateStructuredJdAnalysisMutation() {
  const queryClient = useQueryClient();


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

      // 与 legacy useCreateJdAnalysisMutation 同语义：评分节点以缓存中的全部经历卡为准
      const cardIds = (queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [])
        .map((e) => parseInt(e.id))
        .filter((id) => !isNaN(id));

      const result = await tasksApi.runTaskOrSync<JobAnalysisResult>(
        'jd_analyze_structured',
        {
          user_id: user.id,
          company: data.company,
          position: data.role,
          duties: data.duties,
          requirements: data.requirements,
          card_ids: cardIds
        },
        () => jobApi.analyzeStructuredJd({
          company: data.company,
          position: data.role,
          duties: data.duties,
          requirements: data.requirements,
          card_ids: cardIds
        }),
        { timeout: 120_000 }
      );

      const newAnalysis = analysisToJD(result, targetJobId);
      queryClient.setQueryData(
        [...JD_ANALYSES_QUERY_KEY],
        (prev: JDAnalysis[] | undefined) => [newAnalysis, ...(prev || [])]
      );


      const jobs = readJobs(queryClient);
      const nextJobs = jobs.map((j) =>
        j.id === targetJobId
          ? {
              ...j,
              // T-M5-5（jd-byte-1）：后端 job 实体 id 回填，本地合成岗对齐实体行 id
              ...(result.job_id != null
                ? { id: `job-${result.job_id}`, jobId: result.job_id }
                : {}),
              jdAnalysisId: String(result.job_analysis_id),
              matchScore: result.match_score || 0,
              steps: { ...j.steps, jdAnalysis: true, expMatched: true }
            }
          : j
      );
      queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);


      return newAnalysis;
    },
  });
}

/**
 * 查询当前用户的 JD 分析历史（单次 listJobAnalyses 返回完整详情，消除逐条 GET 的 N+1）。
 *
 * 与 legacy `JobCraftContext.loadJdAnalyses` 语义保持一致；单条映射失败时跳过该条（不外抛）。
 */
export function useJdAnalysesQuery() {
  return useQuery({
    queryKey: [...JD_ANALYSES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.listJobAnalyses(user.id);
      const entries = data.analyses || [];
      const mapped: JDAnalysis[] = [];
      for (const s of entries) {
        try {
          mapped.push(analysisDetailToJD(s));
        } catch {
          // 单条映射失败跳过，不影响整体列表
        }
      }
      return mapped;
    },
  });
}

export interface SplitJdMutationResult {
  dutiesText: string;
  requirements: { text: string; tag: 'hard' | 'required' | 'preferred' }[];
}

/**
 * JD 原文拆分预填（split-jd 端点）：职责拼为换行文本，任职要求 tag 归一为
 * hard|required|preferred（非法值回退 required），供 JD 创建表单直接落栏。
 * 失败上抛（调用方 error toast）。
 */
export function useSplitJdMutation() {
  return useMutation<SplitJdMutationResult, unknown, { jdText: string }>({
    mutationFn: async ({ jdText }) => {
      const result = await jobApi.splitJd(jdText);
      return {
        dutiesText: (result.duties || []).join('\n'),
        requirements: (result.requirements || []).map((r) => ({
          text: r.text,
          tag:
            r.tag === 'hard' || r.tag === 'required' || r.tag === 'preferred'
              ? r.tag
              : 'required',
        })),
      };
    },
  });
}

/**
 * 删除 JD 分析。与 legacy `JobCraftContext.deleteJDAnalysis` 行为等价：
 * 仅从前端状态移除；id 形如 `sub-{number}` 时尝试删除后端 submission（失败忽略）；
 * 后端无 JD 分析删除端点，故真实分析 id（数字串）不产生网络删除请求。
 */
export function useDeleteJdAnalysisMutation() {
  const queryClient = useQueryClient();


  return useMutation<string, unknown, string>({
    mutationFn: async (id) => {
      const match = id.match(/^sub-(\d+)$/);
      if (match) {
        try {
          await jobApi.deleteSubmission(Number(match[1]));
          // FE-CACHE-01：服务端 submission 已删，定向重验 jobs 镜像（岗位卡片随之移除）
          queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
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

    },
  });
}
