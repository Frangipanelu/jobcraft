import { describe, expect, it } from 'vitest';
import type { JobEntity } from '../../api/job';
import { DashboardItem } from '../../api/types';
import { deriveJobStatus, jobEntityToJob, jobRowToJob, stageLabel, submissionToJob } from './mappers';

function makeEntity(overrides: Partial<JobEntity> = {}): JobEntity {
  return {
    id: 42,
    user_id: 1,
    company: '快手',
    position: 'AI 策略产品',
    raw_jd_id: null,
    job_analysis_id: null,
    submission_id: null,
    status: 'PREPARED',
    is_active: true,
    created_at: '2026-09-08T10:00:00',
    updated_at: null,
    ...overrides,
  };
}

function makeItem(overrides: Partial<DashboardItem> = {}): DashboardItem {
  return {
    id: 5,
    position: 'AI 产品经理',
    company: '字节跳动',
    status: 'PREPARED',
    job_analysis_id: null,
    has_analysis: false,
    card_version_count: 0,
    card_count: 0,
    has_resume: false,
    is_manual: false,
    delivered: false,
    prep_count: 0,
    review_count: 0,
    created_at: '2026-09-10T10:00:00',
    updated_at: '2026-09-11T08:00:00',
    ...overrides,
  }
}

describe('submissionToJob 映射', () => {
  it('基础 PREPARED 项 → pending / 待投递 / 相关字段归一', () => {
    const job = submissionToJob(makeItem());
    expect(job.id).toBe('5');
    expect(job.company).toBe('字节跳动');
    expect(job.role).toBe('AI 产品经理');
    expect(job.status).toBe('pending');
    expect(job.currentStage).toBe('待投递');
    expect(job.applyDate).toBe('2026-09-10');
    expect(job.lastUpdated).toBe('2026-09-11T08:00:00');
    expect(job.steps).toMatchObject({
      applied: false,
      jdAnalysis: false,
      expMatched: false,
      customResume: false,
      terminated: false,
    });
    expect(job.jdAnalysisId).toBeUndefined();
    expect(job.resumeId).toBe('5');
    expect(job.interviewIds).toEqual([]);
  });

  it('用户确认已投递（delivered）→ applied=true，状态降为 submitted', () => {
    const job = submissionToJob(makeItem({ delivered: true, status: 'APPLIED' }));
    expect(job.steps.applied).toBe(true);
    expect(job.status).toBe('submitted');
    expect(job.currentStage).toBe('已投递');
    expect(job.backendId).toBe(5);
  });

  it('有 JD 分析且未确认投递 → delivered，jdAnalysisId 归一为字符串', () => {
    const job = submissionToJob(makeItem({ has_analysis: true, job_analysis_id: 42 }));
    expect(job.status).toBe('delivered');
    expect(job.jdAnalysisId).toBe('42');
  });

  it('prep_count > review_count → interviewing；有复盘 → reviewed', () => {
    expect(submissionToJob(makeItem({ prep_count: 1 })).status).toBe('interviewing');
    expect(submissionToJob(makeItem({ review_count: 1 })).status).toBe('reviewed');
  });

  it('CLOSED → finished 且 terminated 置位', () => {
    const job = submissionToJob(makeItem({ status: 'CLOSED' }));
    expect(job.status).toBe('finished');
    expect(job.steps.terminated).toBe(true);
    expect(job.currentStage).toBe('已关闭');
  });
});

describe('deriveJobStatus 优先级', () => {
  const base = {
    jdAnalysis: false,
    expMatched: false,
    customResume: false,
    applied: false,
    prepStage: 'pending' as const,
    reviewStage: 'pending' as const,
  };

  it('terminated > prepStage > reviewStage > applied > jdAnalysis > pending', () => {
    expect(deriveJobStatus({ ...base, terminated: true })).toBe('finished');
    expect(deriveJobStatus({ ...base, prepStage: 'in_progress' as const })).toBe('interviewing');
    expect(deriveJobStatus({ ...base, reviewStage: 'done' as const })).toBe('reviewed');
    expect(deriveJobStatus({ ...base, applied: true })).toBe('submitted');
    expect(deriveJobStatus({ ...base, jdAnalysis: true })).toBe('delivered');
    expect(deriveJobStatus(base)).toBe('pending');
  });

  it('已投递优先级高于待投递（applied 优先于 jdAnalysis）', () => {
    expect(deriveJobStatus({ ...base, jdAnalysis: true, applied: true })).toBe('submitted');
  });
});

describe('jobEntityToJob 映射（T-M5-1 job-only 行）', () => {
  it('无分析 job-only 行 → pending / jobId 归一 / submission 派生态全 pending', () => {
    const job = jobEntityToJob(makeEntity());
    expect(job.id).toBe('job-42');
    expect(job.jobId).toBe(42);
    expect(job.backendId).toBeUndefined();
    expect(job.company).toBe('快手');
    expect(job.role).toBe('AI 策略产品');
    expect(job.status).toBe('pending');
    expect(job.currentStage).toBe('待投递');
    expect(job.applyDate).toBe('2026-09-08');
    expect(job.jdAnalysisId).toBeUndefined();
    expect(job.steps).toMatchObject({
      jdAnalysis: false,
      applied: false,
      prepStage: 'pending',
      reviewStage: 'pending',
    });
    expect(job.interviewIds).toEqual([]);
  });

  it('已挂分析 → delivered + jdAnalysisId 归一为字符串，nextAction 切到简历', () => {
    const job = jobEntityToJob(makeEntity({ job_analysis_id: 7 }));
    expect(job.status).toBe('delivered');
    expect(job.jdAnalysisId).toBe('7');
    expect(job.steps.jdAnalysis).toBe(true);
    expect(job.nextAction).toBe('基于 JD 生成定制简历');
  });

  it('created_at 为空回退今天（YYYY-MM-DD）', () => {
    const job = jobEntityToJob(makeEntity({ created_at: null }));
    expect(job.applyDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe('jobRowToJob 映射（T-M5-2 数据源切 job 表）', () => {
  it('job 实体 + submission 事实 join：行身份=job、steps 由 dash 派生', () => {
    const job = jobRowToJob(
      makeEntity({ submission_id: 5, job_analysis_id: 42 }),
      makeItem({ id: 5, has_analysis: true, job_analysis_id: 42, delivered: true, status: 'APPLIED' }),
      77,
    );
    // 行身份 = job 实体
    expect(job.id).toBe('job-42');
    expect(job.jobId).toBe(42);
    expect(job.backendId).toBe(5);
    // steps 事实来自 join 的 submission 行
    expect(job.steps).toMatchObject({
      jdAnalysis: true,
      applied: true,
      terminated: false,
    });
    expect(job.status).toBe('submitted');
    expect(job.currentStage).toBe('已投递');
    // T-M6-2：简历版本 id 优先
    expect(job.resumeId).toBe('77');
    expect(job.steps.customResume).toBe(true);
  });

  it('无 submission（job-only 降级）：分析事实取 entity，其余步骤 pending', () => {
    const job = jobRowToJob(makeEntity({ job_analysis_id: 7 }));
    expect(job.id).toBe('job-42');
    expect(job.backendId).toBeUndefined();
    expect(job.status).toBe('delivered');
    expect(job.steps).toMatchObject({
      jdAnalysis: true,
      applied: false,
      prepStage: 'pending',
      reviewStage: 'pending',
      terminated: false,
    });
    expect(job.jdAnalysisId).toBe('7');
  });

  it('dash 缺岗位匹配（悬空 submission 不误挂）：prep/review 计数按 dash 派生', () => {
    const job = jobRowToJob(
      makeEntity(),
      makeItem({ prep_count: 2, review_count: 1, status: 'ROUND_1' }),
    );
    expect(job.steps.prepStage).toBe('in_progress');
    expect(job.status).toBe('interviewing');
    // T-M5-4：INVITED/ROUND_x 读时归一为六态词表「面试中」
    expect(job.currentStage).toBe('面试中');
  });

  it('dash status=CLOSED/OFFER → finished（读时投影优先于 entity.status）', () => {
    const job = jobRowToJob(makeEntity(), makeItem({ status: 'CLOSED' }));
    expect(job.status).toBe('finished');
    expect(job.steps.terminated).toBe(true);
    expect(job.currentStage).toBe('已关闭');
  });
});

describe('stageLabel 读时归一（T-M5-4 去轮次化）', () => {
  it('INVITED/ROUND_1/ROUND_2 归一为「面试中」（Q1 六态对外唯一词表）', () => {
    expect(stageLabel('INVITED')).toBe('面试中');
    expect(stageLabel('ROUND_1')).toBe('面试中');
    expect(stageLabel('ROUND_2')).toBe('面试中');
  });

  it('非轮次状态保持既有中文词表；未知值回退「待处理」', () => {
    expect(stageLabel('PREPARED')).toBe('待投递');
    expect(stageLabel('APPLIED')).toBe('已投递');
    expect(stageLabel('OFFER')).toBe('Offer');
    expect(stageLabel('CLOSED')).toBe('已关闭');
    expect(stageLabel('WHAT')).toBe('待处理');
  });
});