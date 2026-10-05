import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as experienceApi from '../../api/experience';
import * as interviewApi from '../../api/interview';
import * as tasksApi from '../../api/tasks';
import type {
  FeedbackBatchDecisionItem,
  FeedbackBatchItemResult,
  InterviewReviewCreateResult,
  InterviewReviewDetailResponse,
  InterviewReviewRecord,
  InterviewReviewResult,
  QuestionBankResponse,
} from '../../api/types';
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
  /** 粘贴速记文本（与 file 二选一） */
  transcript?: string;
  /** 转录文档文件（与 transcript 二选一；FE-UPLOAD-01 真实 multipart 路径） */
  file?: File;
}

/**
 * 创建面试复盘。与 legacy `JobCraftContext.createReviewFromTranscript` 行为等价：
 * - 从 INTERVIEWS cache 解析目标 interview（缺则抛错，由视图 toast）；
 * - FE-UPLOAD-01：`file` 走 `uploadInterviewReview`（multipart），`transcript` 走
 *   `createInterviewReview`（JSON），两者皆缺则抛错（不提交空记录）；
 * - 落库 → `runTaskOrSync('interview_review_analyze')` 降级 `analyzeInterviewReview`；
 * - 分析失败容忍（保留 base patch），不抛出；落库硬失败向上抛；
 * - 成功后 INTERVIEWS cache（review + status completed）+ 跨域 JOBS cache（steps done）；
 * - 不内置 toast / activities（toast 归视图层；activities 无消费者）。
 */
export function useCreateInterviewReviewMutation() {
  const queryClient = useQueryClient();


  return useMutation<CreateReviewMutationResult, unknown, CreateReviewArgs>({
    mutationFn: async ({ interviewId, transcript, file }) => {
      const interviews =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const targetInterview = interviews.find((i) => i.id === interviewId);
      if (!targetInterview) {
        throw new Error('未找到对应的面试记录，请返回重试');
      }

      const user = await authApi.getCurrentUser();
      const common = {
        user_id: user.id,
        company: targetInterview.company,
        position: targetInterview.role,
        round_type: targetInterview.roundType,
        // T-M8-7：修回流断点——透传岗位分析/投递/预建场次，题库才能拿到 JD 上下文，
        // 且 record_id 命中时后端走 update 分支复用 planned 行（不重复插行）。
        job_analysis_id: targetInterview.prepSource?.job_analysis_id ?? null,
        submission_id: targetInterview.prepSource?.submission_id ?? null,
        record_id: targetInterview.sessionRecordId ?? null,
      };
      let result: InterviewReviewCreateResult;
      if (file) {
        result = await interviewApi.uploadInterviewReview(file, common);
      } else if (transcript && transcript.trim()) {
        result = await interviewApi.createInterviewReview({
          ...common,
          raw_text: transcript,
        });
      } else {
        throw new Error('请粘贴面试速记文本或上传转录文档');
      }

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
            // T-M8-6：解除 8 题限制后按题量调大轮询上限（基线 180s，30s/题）
            { timeout: Math.max(180_000, sequences.length * 30_000) },
          );
        }
      } catch {
        // 分析失败不阻塞落库，保留 create 阶段的基础数据
      }

      const patch = analysis
        ? buildReviewPatchFromAnalysis(analysis, result.qa_pair_count || 0)
        : {
            // T-M8-8：分析缺失时按域内既有约定记 0（= 未评分）。
            // 原按题数伪造分数（qa_pair_count×10，空时兜底 4）已下线——FE-FAKE-01。
            overallScore: 0,
            totalQACount: result.qa_pair_count || 0,
          };

      const review: InterviewReview = {
        ...buildReviewFromPatch(targetInterview, patch),
        recordId: result.record_id,
      };
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
      // T-M8-2：新 record 落库后重解析详情直读（recordId 已入 cache，下一次 fetch 走快路径）
      queryClient.invalidateQueries({ queryKey: [INTERVIEW_REVIEW_DETAIL_QUERY_KEY] });
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
        // FE-CACHE-01：复盘落库改变 dashboard review_count，定向重验 jobs 镜像
        queryClient.invalidateQueries({ queryKey: [...JOBS_QUERY_KEY] });
      }
    },
  });
}

// ---------------------------------------------------------------------------
// useInterviewReviewDetailQuery（T-M8-2 详情页直读）
// ---------------------------------------------------------------------------

export const INTERVIEW_REVIEW_DETAIL_QUERY_KEY = 'interview-review-detail';

/** T-M8-3：聚合题库 query key 前缀（后缀为 job_analysis_id 或 null=全量） */
export const QUESTION_BANK_QUERY_KEY = ['interview-review', 'qa-pairs'] as const;

/**
 * 定位 interview 对应的 interview_records 行：
 * 1) job_analysis_id 精确匹配（T-M8-7 FE 透传后的稳态路径）；
 * 2) 回退 company + position + round_type（与 create payload 同源字段）；
 * 3) 仍无则回退 company + position（列表按创建时间倒序，取最新一场）。
 * 均未命中返回 null（详情页回退内存 review / 空态）。
 */
function pickReviewRecordId(
  records: InterviewReviewRecord[],
  interview: Interview,
): number | null {
  let candidates = records;
  const linked = interview.prepSource?.job_analysis_id;
  if (linked != null && linked !== 0) {
    const byJob = records.filter((r) => r.job_analysis_id === linked);
    if (byJob.length > 0) candidates = byJob;
  }
  const exact = candidates.find(
    (r) =>
      r.company === interview.company &&
      r.position === interview.role &&
      r.round_type === interview.roundType,
  );
  if (exact) return exact.id;
  const loose = candidates.find(
    (r) => r.company === interview.company && r.position === interview.role,
  );
  return loose?.id ?? null;
}

/**
 * T-M8-2：详情页直读 query —— 拉取 record + interview_qa_pairs。
 * record 定位：内存 review.recordId 快路径（创建当次会话）→ records 列表匹配（跨会话刷新）。
 * 返回 null 表示服务端无对应 record（组件回退内存 review / 空态）。
 */
export function useInterviewReviewDetailQuery(interview?: Interview) {
  return useQuery<InterviewReviewDetailResponse | null>({
    queryKey: [INTERVIEW_REVIEW_DETAIL_QUERY_KEY, interview?.id],
    enabled: !!interview,
    staleTime: 60_000,
    queryFn: async () => {
      if (!interview) return null;
      const cachedRecordId = interview.review?.recordId;
      if (cachedRecordId) {
        return interviewApi.getInterviewReviewDetail(cachedRecordId);
      }
      const { records } = await interviewApi.listInterviewReviewRecords();
      const recordId = pickReviewRecordId(records, interview);
      return recordId != null
        ? interviewApi.getInterviewReviewDetail(recordId)
        : null;
    },
  });
}

// ---------------------------------------------------------------------------
// useQuestionBankQuery（T-M8-3 聚合题库，只读）
// ---------------------------------------------------------------------------

/**
 * 跨场次聚合题库：jobAnalysisId 省略/空 = 本人全部（端点单 JOIN 聚合，免 N+1）。
 * 只读消费（浏览 / 检索 / 复制题目），不写 prep 数据；变更侧为复盘分析本身。
 */
export function useQuestionBankQuery(jobAnalysisId?: number | null) {
  return useQuery<QuestionBankResponse>({
    queryKey: [...QUESTION_BANK_QUERY_KEY, jobAnalysisId ?? null],
    staleTime: 60_000,
    queryFn: () => interviewApi.listQuestionBankQaPairs(jobAnalysisId),
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
 * EXP-P1-06b §34.6 + T-M8-1 反馈闸门：
 * - 四槽位变更在本地合成后交给**后端 accept 端点**落卡（服务端 update_card 自动
 *   版本化：card_versions 快照 + version+1），决策同时写入 feedback_candidates 台账；
 * - 服务端对同一候选幂等（唯一键），重复确认不会二次写卡；
 * - 再从 listCardVersions 回流真实版本历史；currentVersion/versionHistory 以后端为准，
 *   版本服务不可用时保留升级内容、逐级回退原有版本信息。
 * - 成功后 EXPERIENCES cache（内容 + 后端版本）+ INTERVIEWS cache（applied 标记）。
 * P10-b-lite 轻闸门：反哺「只追加新版本、不强制定稿」（后端不传 is_confirmed），
 * 写回确认由 UI 层二段确认承担（InterviewReviewDetailView）。
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
      // T-M8-1：闸门以 interview_records.id 为定位键（T-M8-2 起随复盘写入）
      const recordId = interview.review.recordId;
      if (recordId === undefined || recordId === null) {
        throw new Error('该复盘缺少记录 ID，无法确认沉淀（请重新创建复盘）');
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

      // EXP-P1-06b：内容变更交后端落盘（服务端版本化，§28）；T-M8-1：闸门决策同事务记台账
      const cardId = parseInt(feedback.experienceId);
      if (isNaN(cardId)) {
        throw new Error('复盘反馈未关联有效的经历卡 ID，无法沉淀');
      }
      const decision = await interviewApi.acceptFeedbackCandidate(recordId, {
        target_ref: feedback.experienceId,
        target_type: 'experience',
        background: base.background,
        problem: base.problem,
        actions: base.actions,
        results: base.results,
      });

      // 版本历史回流：以后端快照为准；失败则保留 accept 返回的版本号与原版本信息
      let currentVersion =
        decision.card_version !== null && decision.card_version !== undefined
          ? `V${decision.card_version}`
          : proposedVersion;
      let versionHistory = exp.versionHistory || [];
      try {
        const res = await experienceApi.listCardVersions(cardId);
        currentVersion = `V${res.current_version}`;
        versionHistory = versionsToHistory(res.versions, res.current_version);
      } catch {
        // 版本服务不可用：不阻塞反哺落地（版本号以 accept 响应为准）
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
      // FE-CACHE-01：服务端 updateCard 已写入（usage/tags 派生字段以后端为准）
      queryClient.invalidateQueries({ queryKey: [...EXPERIENCES_QUERY_KEY] });


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
      // T-M8-1：决策已落台账，刷新闸门查询让「已确认/已忽略」以后端为准
      const recordId = (
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || []
      ).find((i) => i.id === interviewId)?.review?.recordId;
      if (recordId !== undefined && recordId !== null) {
        queryClient.invalidateQueries({ queryKey: feedbackGateKey(recordId) });
      }
    },
  });
}

// ---------------------------------------------------------------------------
// 反馈闸门（T-M8-1）
// ---------------------------------------------------------------------------

export const FEEDBACK_GATE_QUERY_KEY = 'review-feedback-gate';

/** 闸门查询 key：按 record 维度（决策以服务端台账为准） */
export function feedbackGateKey(recordId: number): [string, number] {
  return [FEEDBACK_GATE_QUERY_KEY, recordId];
}

/**
 * T-M8-1：读取反馈闸门（候选建议 + 决策状态 + gate_status）。
 * recordId 缺失时 enabled=false，不发请求（不伪造空候选）。
 */
export function useFeedbackGateQuery(recordId?: number | null) {
  return useQuery({
    queryKey: feedbackGateKey(recordId ?? -1),
    queryFn: () => interviewApi.listFeedbackCandidates(recordId as number),
    enabled: recordId !== undefined && recordId !== null,
  });
}

/**
 * T-M8-1：忽略候选（不写卡，仅记台账；可反悔重确认）。
 * 成功后刷新闸门查询 + 同步 INTERVIEWS cache 的 applied 标记为 false。
 */
export function useRejectFeedbackCandidateMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    { recordId: number; targetRef: string },
    unknown,
    { interviewId: string; recordId: number; targetRef: string }
  >({
    mutationFn: async ({ recordId, targetRef }) => {
      const result = await interviewApi.rejectFeedbackCandidate(recordId, {
        target_ref: targetRef,
        target_type: 'experience',
      });
      return { recordId, targetRef: result.target_ref };
    },
    onSuccess: ({ recordId }, { interviewId, targetRef }) => {
      queryClient.invalidateQueries({ queryKey: feedbackGateKey(recordId) });
      const prevInt =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      queryClient.setQueryData(
        [...INTERVIEWS_QUERY_KEY],
        prevInt.map((int): Interview => {
          if (int.id !== interviewId || !int.review) return int;
          return {
            ...int,
            review: {
              ...int.review,
              experienceFeedbacks: (int.review.experienceFeedbacks || []).map((fb) =>
                fb.experienceId === targetRef ? { ...fb, applied: false } : fb,
              ),
            },
          };
        }),
      );
    },
  });
}

// ---------------------------------------------------------------------------
// 汇总一次确认（T-M8-9 遗留 C，SPEC §24.2）
// ---------------------------------------------------------------------------

export interface ConfirmFeedbackDecisionsArgs {
  interviewId: string;
  /** 需要沉淀的经历卡 ID（experienceId 字符串）；四槽位由前端按单条确认的同款逻辑合成 */
  acceptIds: string[];
  /** 需要忽略的经历卡 ID */
  rejectIds: string[];
}

export interface ConfirmFeedbackDecisionsResult {
  recordId: number;
  acceptedIds: string[];
  rejectedIds: string[];
  results: FeedbackBatchItemResult[];
}

/**
 * 复盘结束「汇总一次确认」：把多条候选合并为**一次**批量请求。
 *
 * - 服务端先整批校验、再单事务写入（DATA_MODEL §31），故不做逐条重试；
 * - accept 条目复用与单条确认完全相同的槽位合成（proposedChanges 优先，
 *   缺失时 suggestions 回退），保证两种入口产物一致；
 * - 成功后：INTERVIEWS cache 标记 applied、EXPERIENCES 与闸门查询失效刷新。
 */
export function useConfirmFeedbackDecisionsMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    ConfirmFeedbackDecisionsResult,
    unknown,
    ConfirmFeedbackDecisionsArgs
  >({
    mutationFn: async ({ interviewId, acceptIds, rejectIds }) => {
      const interviews =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      const interview = interviews.find((i) => i.id === interviewId);
      if (!interview?.review) {
        throw new Error('未找到对应的复盘报告');
      }
      const recordId = interview.review.recordId;
      if (recordId === undefined || recordId === null) {
        throw new Error('该复盘缺少记录 ID，无法确认沉淀（请重新创建复盘）');
      }
      const feedbacks = interview.review.experienceFeedbacks || [];
      const experiences =
        queryClient.getQueryData<Experience[]>([...EXPERIENCES_QUERY_KEY]) || [];

      const decisions: FeedbackBatchDecisionItem[] = [];
      for (const experienceId of acceptIds) {
        const feedback = feedbacks.find((f) => f.experienceId === experienceId);
        if (!feedback) {
          throw new Error(`未找到该条复盘反馈: ${experienceId}`);
        }
        const exp = experiences.find((e) => e.id === experienceId);
        if (!exp) {
          throw new Error('未找到对应的经历资产');
        }
        if (isNaN(parseInt(experienceId, 10))) {
          throw new Error('复盘反馈未关联有效的经历卡 ID，无法沉淀');
        }
        const proposedChanges = feedback.proposedChanges || [];
        const base =
          proposedChanges.length > 0
            ? applyProposedChanges(exp, proposedChanges)
            : applyFeedbackSuggestions(exp, feedback.suggestions || []);
        decisions.push({
          target_type: 'experience',
          target_ref: experienceId,
          decision: 'accepted',
          background: base.background,
          problem: base.problem,
          actions: base.actions,
          results: base.results,
        });
      }
      for (const experienceId of rejectIds) {
        decisions.push({
          target_type: 'experience',
          target_ref: experienceId,
          decision: 'rejected',
        });
      }
      if (decisions.length === 0) {
        throw new Error('未选择任何候选决策');
      }

      const result = await interviewApi.confirmFeedbackCandidates(recordId, {
        decisions,
      });
      return {
        recordId,
        acceptedIds: acceptIds,
        rejectedIds: rejectIds,
        results: result.results,
      };
    },
    onSuccess: ({ recordId, acceptedIds, rejectedIds }, { interviewId }) => {
      queryClient.invalidateQueries({ queryKey: feedbackGateKey(recordId) });
      queryClient.invalidateQueries({ queryKey: [...EXPERIENCES_QUERY_KEY] });
      const prevInt =
        queryClient.getQueryData<Interview[]>([...INTERVIEWS_QUERY_KEY]) || [];
      queryClient.setQueryData(
        [...INTERVIEWS_QUERY_KEY],
        prevInt.map((int): Interview => {
          if (int.id !== interviewId || !int.review) return int;
          return {
            ...int,
            review: {
              ...int.review,
              experienceFeedbacks: (int.review.experienceFeedbacks || []).map((fb) => {
                if (acceptedIds.includes(fb.experienceId)) {
                  return { ...fb, applied: true };
                }
                if (rejectedIds.includes(fb.experienceId)) {
                  return { ...fb, applied: false };
                }
                return fb;
              }),
            },
          };
        }),
      );
    },
  });
}
