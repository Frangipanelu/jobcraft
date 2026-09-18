import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as interviewApi from '../../api/interview';
import * as tasksApi from '../../api/tasks';
import type { InterviewPrepResult } from '../../api/types';
import { Interview, Job } from '../../types/jobcraft';
import { JOBS_QUERY_KEY } from '../jobs/mappers';
import { INTERVIEWS_QUERY_KEY, buildInterviewFromPrep, prepRecordToInterview, roundTypeToCn } from './mappers';

export interface InterviewMutationOptions {
  /** context 镜像写入（过渡期）：cache 更新后同步回 context.interviews，供未迁移视图读取。 */
  onSync?: (interviews: Interview[]) => void;
  /** 跨域镜像写入（过渡期）：interviews 变更会补写 jobs 域，同步回 context.jobs。 */
  onSyncJobs?: (jobs: Job[]) => void;
}

export interface CreateInterviewArgs {
  jobId?: string;
  company: string;
  role: string;
  roundNumber: number;
  roundName: string;
  roundType: Interview['roundType'];
  time: string;
  format: Interview['format'];
  interviewer?: string;
  supplementNotes?: string;
}

/**
 * 查询当前用户的面试准备列表（listInterviewPreps → prepRecordToInterview）。
 * 数据源：interviewApi.listInterviewPreps；userId 取自已认证用户的 auth profile。
 * 注意：后端拉取不含内嵌复盘，复盘字段仅在写路径（createInterviewReview 等）于内存构建。
 */
export function useInterviewsQuery() {
  return useQuery({
    queryKey: [...INTERVIEWS_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await interviewApi.listInterviewPreps(user.id);
      return (data.records || []).map(prepRecordToInterview);
    },
  });
}

/**
 * 创建面试准备。与 legacy `JobCraftContext.createInterview` 行为等价：
 * - 从 JOBS cache 解析 job.jdAnalysisId（无则抛错），首选异步任务提交+轮询，
 *   任务服务不可用时降级为同步 generateInterviewPrep；
 * - 成功后 cache 前置插入面试 + 同步 context.interviews（onSync）；
 * - 跨域补写 JOBS cache（interviewIds / steps.prepStage）+ 同步 context.jobs（onSyncJobs）。
 * - 不内置 toast / nextActions（nextActions 无消费方，toast 归视图层）。
 * - mutateAsync 返回创建后的 Interview（含 id，供 navigateTo）。
 */
export function useCreateInterviewMutation(options: InterviewMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync, onSyncJobs } = options;

  return useMutation<Interview, unknown, CreateInterviewArgs>({
    mutationFn: async (data) => {
      // 解析岗位分析 id（job_analysis_id），这是后端真实生成的前提
      let jobAnalysisId: number | null = null;
      if (data.jobId) {
        const jobs = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
        const job = jobs.find((j) => j.id === data.jobId);
        if (job?.jdAnalysisId) {
          const parsed = Number(job.jdAnalysisId);
          if (!Number.isNaN(parsed)) jobAnalysisId = parsed;
        }
      }
      if (!jobAnalysisId) {
        throw new Error('该岗位尚未完成 AI 岗位分析，请先到「岗位分析」页生成分析之后再准备面试。');
      }

      const user = await authApi.getCurrentUser();
      const taskParams = {
        user_id: user.id,
        job_analysis_id: jobAnalysisId,
        round_type: roundTypeToCn(data.roundType),
        card_ids: [],
      };

      const result = await tasksApi.runTaskOrSync<InterviewPrepResult>(
        'interview_prep',
        { ...taskParams },
        () => interviewApi.generateInterviewPrep(jobAnalysisId, {
          round_type: roundTypeToCn(data.roundType),
          card_ids: [],
        }),
        { timeout: 180_000 }
      );

      const newId = result.id ? `prep-${result.id}` : 'prep-' + Date.now();
      const baseInterview = buildInterviewFromPrep(
        {
          round_type: result.round_type,
          dimension_questions: result.dimension_questions || [],
          company_research: result.company_research,
          created_at: result.created_at
        },
        {
          id: newId,
          jobId: data.jobId,
          company: data.company,
          role: data.role,
          prepSource: {
            id: result.id || -Date.now(),
            job_analysis_id: jobAnalysisId,
            company: data.company,
            position: data.role,
            submission_id: null,
            round_type: result.round_type,
            duration: result.duration,
            elevator_pitch: result.elevator_pitch || '',
            dimension_questions: result.dimension_questions || [],
            full_version: result.full_version || '',
            html_content: result.html_content || '',
            created_at: result.created_at,
            company_research: result.company_research
          }
        }
      );
      return {
        ...baseInterview,
        roundNumber: data.roundNumber,
        roundName: data.roundName || baseInterview.roundName,
        roundType: data.roundType,
        time: data.time || baseInterview.time,
        format: data.format,
        interviewer: data.interviewer || '面试官',
        supplementNotes: data.supplementNotes
      };
    },
    onSuccess: (newInterview, variables) => {
      const prev = queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const next = [newInterview, ...prev];
      queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], next);
      onSync?.(next);

      if (variables.jobId) {
        const jobs = queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
        const nextJobs = jobs.map((j) =>
          j.id === variables.jobId
            ? {
                ...j,
                interviewIds: [...j.interviewIds, newInterview.id],
                currentStage: newInterview.roundName,
                nextAction: `准备${newInterview.roundName}（${newInterview.time}）`,
                steps: { ...j.steps, prepStage: 'in_progress' } as Job['steps']
              }
            : j
        );
        queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);
        onSyncJobs?.(nextJobs);
      }
    },
  });
}