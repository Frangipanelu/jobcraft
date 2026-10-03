import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import { updateJobEntity } from '../../api/jobEntity';
import { useToastActions } from '../../context/JobCraftContext';
import { Job } from '../../types/jobcraft';
import { JOBS_QUERY_KEY, deriveJobStatus, jobRowToJob, submissionToJob } from './mappers';


/**
 * 查询当前用户的岗位列表（T-M5-2 数据源切 job 表）：
 * - 主源 = `GET /job` job 实体（行身份 = 岗位，`jobRowToJob` 生成）；
 * - join = dashboard submission 事实（delivered/has_analysis/has_resume/
 *   prep/review 计数，按 job_id 关联），steps 派生同 submissionToJob 口径；
 * - 存量兼容 = dashboard 中无对应在用 job 行的 submission（job_id 缺失或指向
 *   非在用岗位）按 `submissionToJob` 兜底补行，不丢存量数据；
 * - 实体列表失败（如后端未升级）降级为纯 dashboard 行（行为≈切换前）。
 * T-M6-2：按 analysis 归组取最新简历版本，customResume/resumeId 以版本 id 为准。
 */
export function useJobsQuery() {
  return useQuery({
    queryKey: [...JOBS_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.getDashboard(user.id);
      const dashboards = data.submissions || [];

      let entities: jobApi.JobEntity[] = [];
      try {
        entities = await jobApi.listJobEntities();
      } catch {
        entities = [];
      }

      const versionByAnalysis = new Map<number, number>();
      try {
        const versions = await jobApi.listResumeVersions();
        for (const v of versions) {
          if (v.job_analysis_id != null && !versionByAnalysis.has(v.job_analysis_id)) {
            versionByAnalysis.set(v.job_analysis_id, v.id);
          }
        }
      } catch {
        // 版本接口不可用：退回 dashboard has_resume 判定，不阻断岗位列表
      }

      const dashByJobId = new Map<number, (typeof dashboards)[number]>();
      for (const d of dashboards) {
        if (d.job_id != null) dashByJobId.set(d.job_id, d);
      }

      const fromEntities = entities.map((e) =>
        jobRowToJob(
          e,
          dashByJobId.get(e.id),
          e.job_analysis_id != null ? versionByAnalysis.get(e.job_analysis_id) : undefined,
        ),
      );

      // 存量兼容：未被在用 job 行覆盖的 submission（job_id 缺失/悬空）兜底补行
      const covered = new Set(entities.map((e) => e.id));
      const orphans = dashboards
        .filter((d) => d.job_id == null || !covered.has(d.job_id))
        .map(submissionToJob)
        .map((j) => {
          const aid = j.jdAnalysisId ? Number(j.jdAnalysisId) : null;
          const vid = aid != null ? versionByAnalysis.get(aid) : undefined;
          if (vid == null) return j;
          return { ...j, resumeId: String(vid), steps: { ...j.steps, customResume: true } };
        });

      return [...fromEntities, ...orphans];
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
        // T-M5-7 / Q4：兜底假文案中性化（空部门显示层走 '—'，不造假业务线）
        department: jobData.department || '',
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
 * T-M5-2：job-only 行（尚无 submission）落 `PATCH /job/{id}` status=CLOSED，
 * 不再仅本地态（Q2：job 增删查改不碰 submission）。
 * T-M5-6：后端失败不再静默——乐观更新回滚 + 错误 toast（onError）。
 */
export function useTerminateJobMutation() {
  const queryClient = useQueryClient();
  const { showToast } = useToastActions();

  return useMutation<string, unknown, string, { prev: Job[] }>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (job?.backendId != null) {
        // 失败上抛 → onError 回滚 + toast（T-M5-6，不再吞错）
        await jobApi.updateSubmission(job.backendId, { status: 'CLOSED' });
      } else if (job?.jobId != null) {
        await updateJobEntity(job.jobId, { status: 'CLOSED' });
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
      return { prev };
    },
    onError: (_err, _jobId, ctx) => {
      // T-M5-6：回滚乐观状态，展示明确失败提示
      if (ctx) queryClient.setQueryData([...JOBS_QUERY_KEY], ctx.prev);
      showToast({
        type: 'error',
        title: '标记结束失败',
        message: '未能同步到服务器，已恢复原状态，请稍后重试',
      });
    },
    // FE-CACHE-01：乐观补丁后重验——服务端 effective_status / updated_at 为准
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] }),
  });
}

/**
 * 恢复已结束岗位的处理流程（P11-b：后端 reopen 回投递主线，按 delivered 事实
 * 落 `APPLIED`（已投递）或 `PREPARED`（待投递））。
 * T-M5-6：后端失败不再静默——乐观更新回滚 + 错误 toast（onError）。
 */
export function useResumeJobMutation() {
  const queryClient = useQueryClient();
  const { showToast } = useToastActions();

  return useMutation<string, unknown, string, { prev: Job[] }>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (job?.backendId != null) {
        // 失败上抛 → onError 回滚 + toast（T-M5-6，不再吞错）
        await jobApi.updateSubmission(job.backendId, {
          status: job.steps.applied ? 'APPLIED' : 'PREPARED',
        });
      } else if (job?.jobId != null) {
        // T-M5-2：job-only 行恢复落 job 表（无投递事实，回待投递主线）
        await updateJobEntity(job.jobId, { status: 'PREPARED' });
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
      return { prev };
    },
    onError: (_err, _jobId, ctx) => {
      if (ctx) queryClient.setQueryData([...JOBS_QUERY_KEY], ctx.prev);
      showToast({
        type: 'error',
        title: '恢复处理失败',
        message: '未能同步到服务器，已恢复原状态，请稍后重试',
      });
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