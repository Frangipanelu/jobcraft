import type { JobEntity } from '../../api/job';
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
    // P4-4a：岗位实体 id（缓存到前端 Job，刷新后仍可定位岗位）
    jobId: sub.job_id ?? undefined,
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

/**
 * job 表实体（主源）+ submission 事实（join）→ 前端 Job（T-M5-2 数据源切 job 表）。
 *
 * 行身份 = job 实体（id=`job-${id}`、jobId=entity.id）；steps/阶段事实来自
 * 该岗位关联的 dashboard submission 行（delivered/has_analysis/has_resume/
 * prep/review 计数），无 submission 时按 job-only 行降级（jobId 即分析归属，
 * 其余步骤 pending）。
 *
 * @param entity job 表行（GET /api/jobcraft/job）
 * @param dash 该岗位关联的 dashboard submission 事实（无投递时缺省）
 * @param resumeVersionId 简历版本 id（T-M6-2：customResume/resumeId 以版本为准）
 */
export function jobRowToJob(
  entity: JobEntity,
  dash?: DashboardItem,
  resumeVersionId?: number,
): Job {
  const terminated = dash
    ? dash.status === 'OFFER' || dash.status === 'CLOSED'
    : entity.status === 'OFFER' || entity.status === 'CLOSED';
  const prepCount = dash?.prep_count ?? 0;
  const reviewCount = dash?.review_count ?? 0;
  const hasAnalysis = entity.job_analysis_id != null || dash?.has_analysis === true;
  const steps: Job['steps'] = {
    jdAnalysis: hasAnalysis,
    expMatched: (dash?.card_count ?? 0) > 0,
    customResume: resumeVersionId != null || dash?.has_resume === true,
    applied: dash?.delivered ?? false,
    prepStage: prepCount > reviewCount ? 'in_progress' : prepCount > 0 ? 'done' : 'pending',
    reviewStage: reviewCount > 0 ? 'done' : 'pending',
    terminated,
  };

  const applyDateSource = dash?.created_at || entity.created_at || new Date().toISOString();

  return {
    id: `job-${entity.id}`,
    jobId: entity.id,
    // 有投递时 backendId=submission id（PATCH submission 用）；job-only 行为空
    backendId: entity.submission_id ?? dash?.id ?? undefined,
    company: dash?.company || entity.company,
    role: dash?.position || entity.position,
    salaryRange: '面议',
    status: deriveJobStatus(steps),
    matchScore: 0,
    applyDate: applyDateSource.split('T')[0],
    lastUpdated: dash?.updated_at || entity.updated_at || '刚刚',
    currentStage: dash
      ? SUBMISSION_STATUS_CN[dash.status] || '待处理'
      : SUBMISSION_STATUS_CN[entity.status as keyof typeof SUBMISSION_STATUS_CN] || '待投递',
    nextAction: hasAnalysis ? '基于 JD 生成定制简历' : '开始进行该岗位的 JD 深度解析',
    steps,
    jdAnalysisId: (entity.job_analysis_id ?? dash?.job_analysis_id) != null
      ? String(entity.job_analysis_id ?? dash?.job_analysis_id)
      : undefined,
    resumeId: resumeVersionId != null
      ? String(resumeVersionId)
      : dash
        ? String(dash.id)
        : undefined,
    interviewIds: [],
  };
}

/**
 * job 表实体（无 submission 的 job-only 行）→ 前端 Job（T-M5-1 双源并存的最小合并）。
 *
 * T-M5-2 起列表主路径走 `jobRowToJob`（可带 submission 事实 join）；本函数保留为
 * 纯 job 行的薄封装（dash 缺省），兼容既有调用与测试。
 */
export function jobEntityToJob(entity: JobEntity, resumeVersionId?: number): Job {
  return jobRowToJob(entity, undefined, resumeVersionId);
}