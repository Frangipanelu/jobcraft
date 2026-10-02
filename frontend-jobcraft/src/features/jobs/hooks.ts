import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import { Job } from '../../types/jobcraft';
import { JOBS_QUERY_KEY, deriveJobStatus, jobEntityToJob, submissionToJob } from './mappers';


/**
 * 查询当前用户的岗位列表（T-M5-1 双源并存：dashboard submission 主源
 * + job 表中尚无 submission 的 job-only 行合并）。
 * 实体列表失败（如后端未升级）不阻断 dashboard 主源。
 */
export function useJobsQuery() {
  return useQuery({
    queryKey: [...JOBS_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.getDashboard(user.id);
      const fromSubmissions = (data.submissions || []).map(submissionToJob);

      let entities: jobApi.JobEntity[] = [];
      try {
        entities = await jobApi.listJobEntities();
      } catch {
        entities = [];
      }

      // 双源去重：有投递的岗位由 dashboard 派生（job_id 覆盖），只补纯岗位行
      const covered = new Set(
        fromSubmissions.map((j) => j.jobId).filter((v): v is number => v != null),
      );
      const jobOnly = entities
        .filter((e) => e.submission_id == null && !covered.has(e.id))
        .map(jobEntityToJob);
      return [...jobOnly, ...fromSubmissions];
    },
  });
}

/**
 * 创建岗位。T-M5-1 / M5-Q2 Job 先行：只建 job 表行，不再顺带建 submission
 * （创建 ≠ 投递；投递由 useSetDeliveredMutation(true) 首次触发时建）：
 * - 本地乐观 Job（steps 初始 → deriveJobStatus=pending）→ createJobEntity 回填 jobId → cache 前置插入；
 * - 后端失败仅保留本地 Job（fire-and-forget），不抛错；
 * - mutateAsync 返回最终 Job（含回填后的 jobId，供 navigateTo）。
 */
export function useCreateJobMutation() {
  const queryClient = useQueryClient();

  return useMutation<Job, unknown, {
    company: string;
    role: string;
    department?: string;
    salaryRange?: string;
  }>({
    mutationFn: async (jobData) => {
      const steps: Job['steps'] = {
        jdAnalysis: false,
        expMatched: false,
        customResume: false,
        applied: false,
        prepStage: 'pending',
        reviewStage: 'pending'
      };
      const newJob: Job = {
        id: 'job-' + Date.now(),
        company: jobData.company,
        role: jobData.role,
        department: jobData.department || '核心业务线',
        salaryRange: jobData.salaryRange || '面议',
        status: deriveJobStatus(steps),
        matchScore: 0,
        applyDate: new Date().toISOString().split('T')[0],
        lastUpdated: '刚刚',
        currentStage: '待分析 JD',
        nextAction: '开始进行该岗位的 JD 深度解析',
        steps,
        interviewIds: []
      };

      try {
        const entity = await jobApi.createJobEntity({
          company: jobData.company,
          position: jobData.role,
        });
        newJob.id = 'job-' + entity.id;
        // P4-4a：缓存岗位实体 id（后续分析/投递归属同一岗位）
        newJob.jobId = entity.id;
      } catch {
        // 后端不可用时仅保留本地状态
      }

      return newJob;
    },
    onSuccess: (newJob) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = [newJob, ...prev];
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
      // FE-CACHE-01：job 表已建实体时重验——job-only 合并行带回服务端真相；
      // 本地-only 岗位（后端不可用）不触发，避免 refetch 用服务端列表覆盖掉本地行
      if (newJob.jobId != null) {
        queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
      }
    },
  });
}

/**
 * 标记岗位流程已结束（P11-b：持久化到后端 `status=CLOSED`，刷新后不再丢失）。
 * 注意：P0-1 之后 applied（已投递）只能由用户确认，终止流程不再顺带标记投递。
 */
export function useTerminateJobMutation() {
  const queryClient = useQueryClient();

  return useMutation<string, unknown, string>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (job?.backendId != null) {
        try {
          await jobApi.updateSubmission(job.backendId, { status: 'CLOSED' });
        } catch {
          // 后端不可用时仅保留本地乐观状态
        }
      }
      return jobId;
    },
    onMutate: (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = prev.map((j) => {
        if (j.id !== jobId) return j;
        const steps = { ...j.steps, terminated: true };
        return { ...j, lastUpdated: '刚刚', steps, status: deriveJobStatus(steps) } as Job;
      });
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
    },
    // FE-CACHE-01：乐观补丁后重验——服务端 effective_status / updated_at 为准
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] }),
  });
}

/**
 * 恢复已结束岗位的处理流程（P11-b：后端 reopen 回投递主线，按 delivered 事实
 * 落 `APPLIED`（已投递）或 `PREPARED`（待投递））。
 */
export function useResumeJobMutation() {
  const queryClient = useQueryClient();

  return useMutation<string, unknown, string>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (job?.backendId != null) {
        try {
          await jobApi.updateSubmission(job.backendId, {
            status: job.steps.applied ? 'APPLIED' : 'PREPARED',
          });
        } catch {
          // 后端不可用时仅保留本地乐观状态
        }
      }
      return jobId;
    },
    onMutate: (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = prev.map((j) => {
        if (j.id !== jobId) return j;
        const steps = { ...j.steps, terminated: false };
        return { ...j, lastUpdated: '刚刚', steps, status: deriveJobStatus(steps) } as Job;
      });
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
    },
    // FE-CACHE-01：乐观补丁后重验——服务端 status（reopen 语义）为准
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] }),
  });
}

/**
 * 用户主动标记/取消「已投递」（P0-1：已投递必须是用户手工确认，禁止自动进入）。
 * T-M5-1 / Q2 Job 先行：
 * - 标记投递 + 岗位尚无 submission（backendId 空、jobId 已有）→ 首次建 submission
 *   （status=APPLIED + delivered=true，后端 find-or-create 自动回挂 job.submission_id），回填 backendId/jobId；
 * - 其余情况（已有 submission 的标记/取消）→ PATCH delivered；
 * - cache 即时更新，前端状态仍由 deriveJobStatus 派生；后端失败仅保留本地乐观状态。
 */
export function useSetDeliveredMutation(delivered: boolean) {
  const queryClient = useQueryClient();

  return useMutation<string, unknown, string>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (delivered && job && job.backendId == null && job.jobId != null) {
        try {
          const sub = await jobApi.createSubmission({
            position: job.role,
            company: job.company,
            job_analysis_id: job.jdAnalysisId ? Number(job.jdAnalysisId) : null,
            status: 'APPLIED',
            delivered: true,
          });
          // 回填：submission.id → backendId，job_id → jobId，后续取消投递走 PATCH
          const cached =
            queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
          queryClient.setQueryData<Job[]>(
            [...JOBS_QUERY_KEY],
            cached.map((j) =>
              j.id === jobId ? { ...j, backendId: sub.id, jobId: sub.job_id ?? j.jobId } : j,
            ),
          );
        } catch {
          // 后端不可用时仅保留本地乐观状态
        }
      } else if (job?.backendId != null) {
        try {
          await jobApi.updateSubmission(job.backendId, { delivered });
        } catch {
          // 后端不可用时仅保留本地乐观状态
        }
      }
      return jobId;
    },
    onMutate: (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = prev.map((j) => {
        if (j.id !== jobId) return j;
        const steps = { ...j.steps, applied: delivered };
        return {
          ...j,
          lastUpdated: '刚刚',
          steps,
          status: deriveJobStatus(steps),
        } as Job;
      });
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
    },
    // FE-CACHE-01：delivered 落库后重验——dashboard delivered 事实为准
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] }),
  });
}