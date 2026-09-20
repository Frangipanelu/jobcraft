import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import { Job } from '../../types/jobcraft';
import { JOBS_QUERY_KEY, deriveJobStatus, submissionToJob } from './mappers';

interface JobMutationOptions {
  /** context 镜像写入（过渡期）：cache 更新后同步回 context.jobs，供未迁移视图读取。 */
  onSync?: (jobs: Job[]) => void;
}

/**
 * 查询当前用户的岗位列表（dashboard → submissionToJob）。
 * 数据源：jobApi.getDashboard；userId 取自已认证用户的 auth profile。
 */
export function useJobsQuery() {
  return useQuery({
    queryKey: [...JOBS_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.getDashboard(user.id);
      return (data.submissions || []).map(submissionToJob);
    },
  });
}

/**
 * 创建岗位。与 legacy `JobCraftContext.createJob` 行为等价：
 * - 本地乐观 Job（steps 初始 → deriveJobStatus=pending）→ createSubmission 回填 id/backendId → cache 前置插入；
 * - 后端失败仅保留本地 Job（fire-and-forget），不抛错；
 * - mutateAsync 返回最终 Job（含回填后的 id，供 navigateTo）。
 */
export function useCreateJobMutation(options: JobMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync } = options;

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
        const sub = await jobApi.createSubmission({
          position: jobData.role,
          company: jobData.company,
        });
        newJob.id = 'job-' + sub.id;
        newJob.backendId = sub.id;
      } catch {
        // 后端不可用时仅保留本地状态
      }

      return newJob;
    },
    onSuccess: (newJob) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = [newJob, ...prev];
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
      onSync?.(next);
    },
  });
}

interface TerminateArgs {
  jobId: string;
  steps: Job['steps'];
  lastUpdated: string;
}

/**
 * 纯本地状态变更基类：把 cache 中目标 Job 的 steps/lastUpdated 替换为传入值，并同步镜像。
 */
function useLocalJobPatchMutation(patch: (j: Job) => TerminateArgs, options: JobMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync } = options;

  return useMutation<string, unknown, string>({
    mutationFn: async (jobId) => jobId,
    onMutate: (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const next = prev.map((j) => {
        if (j.id !== jobId) return j;
        const applied = patch(j);
        const steps = applied.steps;
        return { ...j, lastUpdated: applied.lastUpdated, steps, status: deriveJobStatus(steps) } as Job;
      });
      queryClient.setQueryData([...JOBS_QUERY_KEY], next);
      onSync?.(next);
    },
  });
}

/**
 * 标记岗位流程已结束（纯本地状态更新，无后端调用）。
 * 注意：P0-1 之后 applied（已投递）只能由用户确认，终止流程不再顺带标记投递。
 */
export function useTerminateJobMutation(options: JobMutationOptions = {}) {
  return useLocalJobPatchMutation(
    (j) => ({ jobId: j.id, lastUpdated: '刚刚', steps: { ...j.steps, terminated: true } }),
    options
  );
}

/**
 * 恢复已结束岗位的处理流程（纯本地状态更新，无后端调用）。
 */
export function useResumeJobMutation(options: JobMutationOptions = {}) {
  return useLocalJobPatchMutation(
    (j) => ({ jobId: j.id, lastUpdated: '刚刚', steps: { ...j.steps, terminated: false } }),
    options
  );
}

/**
 * 用户主动标记/取消「已投递」（P0-1：已投递必须是用户手工确认，禁止自动进入）。
 * - 优先调用后端 PATCH delivered（有 backendId 时持久化），失败仅保留本地乐观状态；
 * - cache 与 context 镜像即时同步，前端状态仍由 deriveJobStatus 派生。
 */
export function useSetDeliveredMutation(delivered: boolean, options: JobMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync } = options;

  return useMutation<string, unknown, string>({
    mutationFn: async (jobId) => {
      const prev = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
      const job = prev.find((j) => j.id === jobId);
      if (job?.backendId != null) {
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
      onSync?.(next);
    },
  });
}