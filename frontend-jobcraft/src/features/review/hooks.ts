import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as experienceApi from '../../api/experience';
import * as interviewApi from '../../api/interview';
import * as tasksApi from '../../api/tasks';
import type { InterviewReviewResult } from '../../api/types';
import { Experience, Interview, InterviewReview, Job } from '../../types/jobcraft';
import { EXPERIENCES_QUERY_KEY, versionsToHistory } from '../experiences/mappers';
import { JOBS_QUERY_KEY } from '../jobs/mappers';
import { INTERVIEWS_QUERY_KEY } from '../interview/mappers';
import {
  buildReviewFromPatch,
  buildReviewPatchFromAnalysis,
  applyProposedChanges,
  applyFeedbackSuggestions,
} from './mappers';


// ---------------------------------------------------------------------------
// useCreateInterviewReviewMutation
// ---------------------------------------------------------------------------

export interface CreateReviewMutationResult {
  interviewId: string;
  review: InterviewReview;
}

export interface CreateReviewArgs {
  interviewId: string;
  transcript: string;
}

/**
 * 创建面试复盘。与 legacy `JobCraftContext.createReviewFromTranscript` 行为等价：
 * - 从 INTERVIEWS cache 解析目标 interview（缺则抛错，由视图 toast）；
 * - `createInterviewReview` 落库 → `runTaskOrSync('interview_review_analyze')` 降级 `analyzeInterviewReview`；
 * - 分析失败容忍（保留 base patch），不抛出；`createInterviewReview` 硬失败向上抛；
 * - 成功后 INTERVIEWS cache（review + status completed）+ 跨域 JOBS cache（steps done）；
 * - 不内置 toast / activities（toast 归视图层；activities 无消费者）。
 */
export function useCreateInterviewReviewMutation() {
  const queryClient = useQueryClient();


  return useMutation<CreateReviewMutationResult, unknown, CreateReviewArgs>({
    mutationFn: async ({ interviewId, transcript }) => {
      const interviews =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const targetInterview = interviews.find((i) => i.id === interviewId);
      if (!targetInterview) {
        throw new Error('未找到对应的面试记录，请返回重试');
      }

      const user = await authApi.getCurrentUser();
      const result = await interviewApi.createInterviewReview({
        user_id: user.id,
        company: targetInterview.company,
        position: targetInterview.role,
        round_type: targetInterview.roundType,
        raw_text: transcript,
      });

      let analysis: InterviewReviewResult | null = null;
      try {
        const sequences = (result.qa_pairs || []).map((p) => p.sequence);
        if (result.record_id && sequences.length > 0) {
          analysis = await tasksApi.runTaskOrSync<InterviewReviewResult>(
            'interview_review_analyze',
            {
              user_id: user.id,
              record_id: result.record_id,
              selected_sequences: sequences,
            },
            () =>
              interviewApi.analyzeInterviewReview(
                result.record_id,
                sequences,
                user.id,
              ),
            { timeout: 180_000 },
          );
        }
      } catch {
        // 分析失败不阻塞落库，保留 create 阶段的基础数据
      }

      const patch = analysis
        ? buildReviewPatchFromAnalysis(analysis, result.qa_pair_count || 0)
        : {
            overallScore: Math.round((result.qa_pair_count || 4) * 10),
            totalQACount: result.qa_pair_count || 0,
          };

      const review = buildReviewFromPatch(targetInterview, patch);
      return { interviewId, review };
    },
    onSuccess: ({ interviewId, review }) => {
      const prev =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const next = prev.map((i): Interview =>
        i.id === interviewId ? { ...i, status: 'completed', review } : i,
      );
      queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], next);


      const target = prev.find((i) => i.id === interviewId);
      if (target?.jobId) {
        const jobs =
          queryClient.getQueryData<Job[]>([...JOBS_QUERY_KEY]) || [];
const nextJobs: Job[] = jobs.map((j) =>
        j.id === target.jobId
          ? {
              ...j,
              steps: { ...j.steps, reviewStage: 'done', prepStage: 'done' },
            }
          : j,
      );
        queryClient.setQueryData([...JOBS_QUERY_KEY], nextJobs);
  
      }
    },
  });
}

// ---------------------------------------------------------------------------
// useApplyReviewFeedbackMutation
// ---------------------------------------------------------------------------

export interface ApplyReviewFeedbackResult {
  experienceId: string;
  finalExp: Experience;
}

export interface ApplyReviewFeedbackArgs {
  interviewId: string;
  feedbackIndex: number;
}

/**
 * 将复盘反馈中的经历升级提案落地到经历资产库。
 * EXP-P1-06b §34.6：不再本地拼接假版本记录——
 * - mutationFn 先 updateCard 持久化四槽位变更（服务端写 card_versions 快照 + version+1），
 * - 再从 listCardVersions 回流真实版本历史；currentVersion/versionHistory 以后端为准，
 * - 版本服务不可用时保留升级内容、逐级回退原有版本信息。
 * - 成功后 EXPERIENCES cache（内容 + 后端版本）+ INTERVIEWS cache（applied 标记）。
 */
export function useApplyReviewFeedbackMutation() {
  const queryClient = useQueryClient();


  return useMutation<ApplyReviewFeedbackResult, unknown, ApplyReviewFeedbackArgs>({
    mutationFn: async ({ interviewId, feedbackIndex }) => {
      const interviews =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const interview = interviews.find((i) => i.id === interviewId);
      if (!interview?.review) {
        throw new Error('未找到对应的复盘报告');
      }

      const feedbacks = interview.review.experienceFeedbacks || [];
      const feedback = feedbacks[feedbackIndex];
      if (!feedback) {
        throw new Error('未找到该条复盘反馈');
      }

      const experiences =
        queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const exp = experiences.find((e) => e.id === feedback.experienceId);
      if (!exp) {
        throw new Error('未找到对应的经历资产');
      }

      const proposedVersion = feedback.proposedVersion || 'V2';
      const proposedChanges = feedback.proposedChanges || [];

      const base =
        proposedChanges.length > 0
          ? applyProposedChanges(exp, proposedChanges)
          : applyFeedbackSuggestions(exp, feedback.suggestions || []);

      // EXP-P1-06b：内容变更持久化到后端（updateCard 自动版本化，§28）
      const cardId = parseInt(feedback.experienceId);
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, {
          background: base.background,
          problem: base.problem,
          actions: base.actions,
          results: base.results,
          // EXP-P1-03：复盘反哺亦视为定稿保存
          is_confirmed: true,
        });
      }

      // 版本历史回流：以后端快照为准；失败则保留升级内容、回退原有版本信息
      let currentVersion = proposedVersion;
      let versionHistory = exp.versionHistory || [];
      try {
        const res = await experienceApi.listCardVersions(cardId);
        currentVersion = `V${res.current_version}`;
        versionHistory = versionsToHistory(res.versions, res.current_version);
      } catch {
        // 版本服务不可用：不阻塞反哺落地
      }

      const finalExp: Experience = {
        ...base,
        currentVersion,
        versionHistory,
      };

      return { experienceId: feedback.experienceId, finalExp };
    },
    onSuccess: ({ experienceId, finalExp }, { interviewId, feedbackIndex }) => {
      // EXPERIENCES cache + mirror
      const prevExp =
        queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];
      const nextExp = prevExp.map((e) =>
        e.id === experienceId ? finalExp : e,
      );
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], nextExp);


      // INTERVIEWS cache + mirror
      const prevInt =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const nextInt = prevInt.map((int): Interview => {
        if (int.id !== interviewId || !int.review) return int;
        const updatedFeedbacks = (
          int.review.experienceFeedbacks || []
        ).map((fb, idx) =>
          idx === feedbackIndex ? { ...fb, applied: true } : fb,
        );
        return {
          ...int,
          review: { ...int.review, experienceFeedbacks: updatedFeedbacks },
        };
      });
      queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], nextInt);

    },
  });
}
