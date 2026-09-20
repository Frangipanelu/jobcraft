import { SUBMISSION_STATUS_CN, DashboardItem } from '../../api/types';
import { Job, JobStatus } from '../../types/jobcraft';

/** Jobs 查询缓存 key（react-query 唯读源）。 */
export const JOBS_QUERY_KEY = ['jobs'] as const;

/**
 * 将后端 Submission/DashboardItem 转换为前端 Job。
 *
 * 自 JobCraftContext 移出，作为映射唯一实现（context 与 hooks 共享，杜绝双份漂移）。
 */
export function submissionToJob(sub: DashboardItem): Job {
  const terminated = sub.status === 'OFFER' || sub.status === 'CLOSED'
  const steps: Job['steps'] = {
    jdAnalysis: sub.has_analysis,
    expMatched: sub.card_count > 0,
    customResume: sub.has_resume,
    applied: sub.delivered ?? false,
    prepStage:
      sub.prep_count > sub.review_count ? 'in_progress' : sub.prep_count > 0 ? 'done' : 'pending',
    reviewStage: sub.review_count > 0 ? 'done' : 'pending',
    terminated,
  }

  return {
    id: String(sub.id),
    backendId: sub.id,
    company: sub.company,
    role: sub.position,
    salaryRange: '面议',
    status: deriveJobStatus(steps),
    matchScore: 0,
    applyDate: sub.created_at?.split('T')[0] || new Date().toISOString().split('T')[0],
    lastUpdated: sub.updated_at || '刚刚',
    currentStage: SUBMISSION_STATUS_CN[sub.status] || '待处理',
    nextAction: '',
    steps,
    jdAnalysisId: sub.job_analysis_id ? String(sub.job_analysis_id) : undefined,
    resumeId: String(sub.id),
    interviewIds: []
  }
}

/**
 * 由 steps 派生岗位状态（单一事实源，流程只更新 steps，不手动写 status）。
 *
 * 优先级从高到低：
 * 已结束(terminated) → 待面试(prepStage=in_progress) → 已复盘(reviewStage=done)
 * → 已投递(applied，用户手动确认) → 待投递(jdAnalysis 自动) → 待处理。
 */
export function deriveJobStatus(steps: Job['steps']): JobStatus {
  if (steps.terminated) return 'finished';
  if (steps.prepStage === 'in_progress') return 'interviewing';
  if (steps.reviewStage === 'done') return 'reviewed';
  if (steps.applied) return 'submitted';
  if (steps.jdAnalysis) return 'delivered';
  return 'pending';
}