import { describe, it, expect } from 'vitest';
import type { JobAnalysisResult } from '../../api/types';
import { analysisToJD, analysisDetailToJD } from './mappers';

function buildResult(overrides: Partial<JobAnalysisResult> = {}): JobAnalysisResult {
  return {
    job_analysis_id: 42,
    user_id: 1,
    company: '字节跳动',
    position: 'AI 产品经理',
    jd_text: '原始 JD 文本',
    jd_requirements: null,
    ats_profile: null,
    company_context: null,
    match_score: 80,
    match_level: '高匹配',
    customization_needed: false,
    gap_analysis: null,
    gap_items: [],
    per_card_scores: [],
    suggestions: [],
    dimension_requirements: [],
    resume_markdown: null,
    created_at: '2026-02-01',
    ...overrides,
  };
}

describe('analysisToJD', () => {
  it('映射 ats_profile / match_score / suggestions 与 created_at 兜底', () => {
    const result = buildResult({
      ats_profile: {
        job_title: 'AI 产品经理',
        department: null,
        location: null,
        salary: '40K–60K',
        years_of_experience: null,
        education: null,
        required_skills: ['RAG', '评测'],
        preferred_skills: ['英文'],
        responsibilities: ['搭建评测体系'],
        key_metrics: ['召回率'],
        culture_keywords: [],
        dimension_requirements: [],
        raw_summary: '',
      },
      suggestions: [{ card_id: 7, type: 'gap', message: '补充评测经验', priority: 1, optimization: null }],
      match_score: 80,
    });

    const jd = analysisToJD(result, 'job-1');

    expect(jd.id).toBe('42');
    expect(jd.jobId).toBe('job-1');
    expect(jd.company).toBe('字节跳动');
    expect(jd.role).toBe('AI 产品经理');
    expect(jd.salaryRange).toBe('40K–60K');
    expect(jd.matchScore).toBe(80);
    expect(jd.recommendationStars).toBe(4);
    expect(jd.whyMatch).toBe('高匹配');
    expect(jd.resumeAdvice).toEqual(['补充评测经验']);
    expect(jd.coreRequirements).toEqual([
      { category: '核心职责', items: ['搭建评测体系'] },
      { category: '任职资格', items: ['RAG', '评测', '英文'] },
    ]);
    expect(jd.atsKeywords).toEqual({
      hardSkills: ['RAG', '评测'],
      softSkills: ['英文'],
      expKeywords: ['召回率'],
      coveragePercent: 80,
    });
  });

  it('无 ats_profile 时 salaryRange 兜底为面议，skillGaps 由 jd_requirements 与 per_card_scores 判定', () => {
    const result = buildResult({
      match_score: null,
      created_at: null,
      jd_requirements: {
        position_title: 'AI 产品经理',
        hard_skills: ['RAG'],
        soft_skills: ['沟通'],
        keywords: ['端侧'],
        nice_to_have: [],
        responsibilities: [],
        dimension_requirements: [],
        salary_range: null,
        work_mode: null,
        location: null,
      },
      per_card_scores: [{ card_id: 7, score: 88, matched: ['RAG'], missing: ['端侧'] }],
    });

    const jd = analysisToJD(result);

    expect(jd.salaryRange).toBe('面议');
    expect(jd.matchScore).toBe(0);
    expect(jd.recommendationStars).toBe(0);
    expect(jd.verdictSummary).toBe('分析完成');
    expect(jd.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(jd.skillGaps.map((s) => [s.capability, s.gap])).toEqual([
      ['RAG', '已匹配'],
      ['沟通', '待补充'],
      ['端侧', '待补充'],
    ]);
    expect(jd.recommendedExperiences[0]).toEqual({
      experienceId: '7',
      matchScore: 88,
      matchingJDReq: 'RAG',
      reason: '端侧',
    });
  });
});

describe('analysisDetailToJD', () => {
  it('由 dimension_requirements 构建 skillGaps / goal，jd_requirements 构建关键词', () => {
    const detail = buildResult({
      jd_requirements: {
        position_title: 'AI 产品经理',
        hard_skills: ['RAG', '评测'],
        soft_skills: ['沟通'],
        keywords: ['端侧'],
        nice_to_have: [],
        responsibilities: ['搭建评测体系'],
        dimension_requirements: [],
        salary_range: null,
        work_mode: null,
        location: null,
      },
      dimension_requirements: [{ dimension: '技术深度', level: 3, evidence: '掌握 RAG 检索增强' }],
    });

    const jd = analysisDetailToJD(detail);

    expect(jd.id).toBe('42');
    expect(jd.salaryRange).toBe('');
    expect(jd.coreRequirements).toEqual([
      { category: '核心职责', items: ['搭建评测体系'] },
      { category: '任职资格', items: ['RAG', '评测', '沟通'] },
    ]);
    expect(jd.atsKeywords).toEqual({
      hardSkills: ['RAG', '评测'],
      softSkills: ['沟通'],
      expKeywords: ['端侧'],
      coveragePercent: 80,
    });
    expect(jd.skillGaps).toEqual([
      { id: 'skill-0', capability: 'RAG', userEvidence: '掌握 RAG 检索增强', requirement: 'RAG', gap: '已匹配', recommendation: '' },
      { id: 'skill-1', capability: '评测', userEvidence: '', requirement: '评测', gap: '待补充', recommendation: '' },
      { id: 'skill-2', capability: '沟通', userEvidence: '', requirement: '沟通', gap: '待补充', recommendation: '' },
    ]);
    expect(jd.goal).toBe('掌握 RAG 检索增强');
    expect(jd.jobId).toBeUndefined();
  });

  it('无 dimension_requirements 时 goal 回退 gap_analysis，空详情不抛错', () => {
    const jd = analysisDetailToJD(buildResult({ gap_analysis: '整体匹配良好' }));
    expect(jd.goal).toBe('整体匹配良好');
    expect(jd.skillGaps).toEqual([]);
    expect(jd.coreRequirements).toEqual([
      { category: '核心职责', items: [] },
      { category: '任职资格', items: [] },
    ]);
  });
});
