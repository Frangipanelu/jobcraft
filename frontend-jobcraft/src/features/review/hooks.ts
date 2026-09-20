import { useMutation, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as interviewApi from '../../api/interview';
import * as tasksApi from '../../api/tasks';
import type { InterviewReviewResult } from '../../api/types';
import { Experience, ExperienceProposedChange, Interview, InterviewReview, Job } from '../../types/jobcraft';
import { EXPERIENCES_QUERY_KEY } from '../experiences/mappers';
import { JOBS_QUERY_KEY } from '../jobs/mappers';
import { INTERVIEWS_QUERY_KEY } from '../interview/mappers';
import {
  buildReviewFromPatch,
  buildReviewPatchFromAnalysis,
  applyProposedChanges,
  applyFeedbackSuggestions,
  buildVersionRecord,
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
 * 与 legacy `JobCraftContext.applyReviewFeedback` 行为等价，额外修复漂移 bug：
 * - legacy 仅 setExperiences 不写 EXPERIENCES cache → 新实现同步写 cache；
 * - legacy 写 activities（零消费者）→ 本 hook 不写。
 * - 成功后 EXPERIENCES cache（版本升级 + 变更记录）+ INTERVIEWS cache（applied 标记）。
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

      const versionChanges: ExperienceProposedChange[] =
        proposedChanges.length > 0
          ? proposedChanges
          : [
              {
                field: 'actions',
                from: exp.actions[0] || '',
                to: base.actions[0] || '',
              },
            ];

      const finalExp: Experience = {
        ...base,
        currentVersion: proposedVersion,
        versionHistory: [
          buildVersionRecord(
            proposedVersion,
            versionChanges,
            '基于面试真实复盘与面试官深挖问题进行证据增强',
            'interview_review',
          ),
          ...(exp.versionHistory || []),
        ],
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
