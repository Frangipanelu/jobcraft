import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as interviewApi from '../../api/interview';
import * as tasksApi from '../../api/tasks';
import type { InterviewPrepResult, InterviewReviewCreateResult } from '../../api/types';
import { Interview, Job } from '../../types/jobcraft';
import { JOBS_QUERY_KEY } from '../jobs/mappers';
import { INTERVIEWS_QUERY_KEY, buildInterviewFromPrep, prepRecordToInterview, roundTypeToCn } from './mappers';


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
 * - T-M7-4：prep 成功后预建 interview_records 场次行（record+1，status=planned），
 *   向导字段全透传，成功后落 Interview.sessionRecordId；失败向上抛不伪造；
 * - 成功后 cache 前置插入面试 + 跨域补写 JOBS cache（interviewIds / steps.prepStage）。
 * - 不内置 toast / nextActions（nextActions 无消费方，toast 归视图层）。
 * - mutateAsync 返回创建后的 Interview（含 id，供 navigateTo）。
 */
export function useCreateInterviewMutation() {
  const queryClient = useQueryClient();


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

      // T-M7-4：预建面试场次行（record+1，status=planned），向导字段全透传。
      // 放在 prep 成功之后：prep 失败不落 planned 孤儿行；本步失败向上抛，不伪造 sessionRecordId。
      const session = await interviewApi.createInterviewSession({
        job_analysis_id: jobAnalysisId,
        company: data.company,
        position: data.role,
        round_type: data.roundType,
        round_seq: data.roundNumber,
        occurred_at: data.time || undefined,
        interviewer: data.interviewer,
        format: data.format,
      });

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
        supplementNotes: data.supplementNotes,
        sessionRecordId: session.record_id
      };
    },
    onSuccess: (newInterview, variables) => {
      const prev = queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const next = [newInterview, ...prev];
      queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], next);


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
  
      }
    },
  });
}

export interface SavePrepDraftsArgs {
  prepId: number;
  drafts: Record<string, string>;
}

/**
 * 保存备战应答草稿（FE-PREP-01）：
 * - PATCH /api/jobcraft/interview-prep/{id} 整体覆盖 interview_preps.drafts；
 * - 成功后就地更新 INTERVIEWS cache 的 prepSource.drafts（与 useCreateInterviewMutation 同 setQueryData 模式）；
 * - 失败原样抛出由视图层弹错误 toast，不上报假成功。
 */
export function useSavePrepDraftsMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ id: number; drafts: Record<string, string> }, unknown, SavePrepDraftsArgs>({
    mutationFn: ({ prepId, drafts }) => interviewApi.saveInterviewPrepDrafts(prepId, drafts),
    onSuccess: ({ id, drafts }) => {
      const prev = queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      queryClient.setQueryData(
        [...INTERVIEWS_QUERY_KEY],
        prev.map((iv) =>
          iv.prepSource?.id === id
            ? { ...iv, prepSource: { ...iv.prepSource, drafts } }
            : iv
        )
      );
    },
  });
}

/**
 * 公司调研「重新调研」（T-M7-6）：
 * - POST /api/jobcraft/interview-prep/{id}/company-research（force 绕 7 天缓存）；
 * - 成功后失效 INTERVIEWS 列表重新拉取（prepSource.company_research 服务端已回写）；
 * - 失败原样抛出由视图层弹错误 toast，不上报假成功。
 */
export function useRefreshCompanyResearchMutation() {
  const queryClient = useQueryClient();

  return useMutation<{ id: number; company_research: unknown }, unknown, number>({
    mutationFn: (prepId) => interviewApi.refreshInterviewPrepResearch(prepId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...INTERVIEWS_QUERY_KEY] });
    },
  });
}

export interface MockChatArgs {
  messages: { role: string; content: string }[];
  company?: string;
  position?: string;
  round_type?: string;
  experience_context?: string;
}

/**
 * 模拟面试对话（FE-LAYER-01）：会话内 AI 回复调用收敛至特征层，
 * 组件层不再直连 api（无缓存副作用；toast/错误态归视图）。
 */
export function useMockChatMutation() {
  return useMutation<interviewApi.MockChatReply, unknown, MockChatArgs>({
    mutationFn: (args) => interviewApi.mockChat(args),
  });
}

export interface SaveMockReviewArgs {
  title?: string;
  company?: string;
  position?: string;
  round_type?: string;
  raw_text: string;
}

/**
 * 模拟面试完成 → 保存为复盘（FE-LAYER-01 缓存失效）：
 * 落库后失效 INTERVIEWS 列表（复盘中心与详情页同源），
 * 跳转后重新拉取即可看到新复盘，不再出现「保存成功但列表没有」。
 */
export function useSaveMockInterviewReviewMutation() {
  const queryClient = useQueryClient();

  return useMutation<InterviewReviewCreateResult, unknown, SaveMockReviewArgs>({
    mutationFn: (payload) => interviewApi.createInterviewReview(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...INTERVIEWS_QUERY_KEY] });
    },
  });
}