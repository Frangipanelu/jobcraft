import { describe, expect, it } from 'vitest';
import { DashboardItem } from '../../api/types';
import { deriveJobStatus, submissionToJob } from './mappers';

function makeItem(overrides: Partial<DashboardItem> = {}): DashboardItem {
  return {
    id: 5,
    position: 'AI 产品经理',
    company: '字节跳动',
    status: 'APPLIED',
    job_analysis_id: null,
    has_analysis: false,
    card_version_count: 0,
    card_count: 0,
    has_resume: false,
    is_manual: false,
    prep_count: 0,
    review_count: 0,
    created_at: '2026-09-10T10:00:00',
    updated_at: '2026-09-11T08:00:00',
    ...overrides,
  };
}

describe('submissionToJob 映射', () => {
  it('基础 APPLIED 项 → pending / 已投递 / 相关字段归一', () => {
    const job = submissionToJob(makeItem());
    expect(job.id).toBe('5');
    expect(job.company).toBe('字节跳动');
    expect(job.role).toBe('AI 产品经理');
    expect(job.status).toBe('pending');
    expect(job.currentStage).toBe('已投递');
    expect(job.applyDate).toBe('2026-09-10');
    expect(job.lastUpdated).toBe('2026-09-11T08:00:00');
    expect(job.steps).toMatchObject({
      applied: true,
      jdAnalysis: false,
      expMatched: false,
      customResume: false,
      terminated: false,
    });
    expect(job.jdAnalysisId).toBeUndefined();
    expect(job.resumeId).toBe('5');
    expect(job.interviewIds).toEqual([]);
  });

  it('有 JD 分析 → delivered，jdAnalysisId 归一为字符串', () => {
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
  it('terminated > prepStage > reviewStage > jdAnalysis > pending', () => {
    const base = {
      jdAnalysis: false,
      expMatched: false,
      customResume: false,
      applied: true,
      prepStage: 'pending' as const,
      reviewStage: 'pending' as const,
    };
    expect(deriveJobStatus({ ...base, terminated: true })).toBe('finished');
    expect(deriveJobStatus({ ...base, prepStage: 'in_progress' as const })).toBe('interviewing');
    expect(deriveJobStatus({ ...base, reviewStage: 'done' as const })).toBe('reviewed');
    expect(deriveJobStatus({ ...base, jdAnalysis: true })).toBe('delivered');
    expect(deriveJobStatus(base)).toBe('pending');
  });
});