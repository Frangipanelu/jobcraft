import { describe, it, expect } from 'vitest';
import { InterviewPrepRecord } from '../../types/jobcraft';
import { buildInterviewFromPrep, mapRoundType, prepRecordToInterview, roundTypeToCn } from './mappers';

function buildRecord(overrides: Partial<InterviewPrepRecord> = {}): InterviewPrepRecord {
  return {
    id: 7,
    job_analysis_id: 12,
    company: '字节跳动',
    position: 'AI 产品经理',
    round_type: '技术面',
    duration: '45分钟',
    elevator_pitch: '自我介绍',
    dimension_questions: [
      {
        dimension: '技术深度',
        question: '如何设计 RAG 评测体系？',
        answer_points: ['拆分评测维度', '离线指标 + 线上 A/B'],
        card_ids: [3],
      },
    ],
    full_version: '完整版',
    html_content: 'html',
    created_at: '2026-09-18T08:30:00',
    company_research: {
      basic: { description: '人工智能公司', industry: 'AIGC' },
      business: { main_business: '智能助手', product_names: ['豆包'] },
      news: [{ title: '发布新模型' }],
      ai_hiring: '加大 AI 人才招聘',
    },
    ...overrides,
  };
}

describe('prepRecordToInterview', () => {
  it('映射 id / 公司 / 岗位 / 轮次 / 时间 / 准备题', () => {
    const iv = prepRecordToInterview(buildRecord());

    expect(iv.id).toBe('prep-7');
    expect(iv.jobId).toBe('12');
    expect(iv.company).toBe('字节跳动');
    expect(iv.role).toBe('AI 产品经理');
    expect(iv.roundType).toBe('tech');
    expect(iv.status).toBe('preparing');
    expect(iv.readinessPercent).toBe(40);
    expect(iv.time).toBe('2026-09-18 08:30');
    expect(iv.preparation.highFreqQuestions).toHaveLength(1);
    expect(iv.preparation.highFreqQuestions[0].question).toBe('如何设计 RAG 评测体系？');
    expect(iv.preparation.highFreqQuestions[0].preparedAnswer.logicFlow).toEqual([
      '拆分评测维度',
      '离线指标 + 线上 A/B',
    ]);
    expect(iv.preparation.companyResearch).toEqual({
      background: '人工智能公司',
      coreBusiness: '智能助手',
      keyProducts: ['豆包'],
      relevantBusiness: 'AIGC',
      recentNews: ['发布新模型'],
      aiHiringIntent: '加大 AI 人才招聘',
    });
    expect(iv.preparation.recommendedExperiences[0]).toEqual({
      experienceId: '3',
      recommendScore: 90,
      proves: ['拆分评测维度', '离线指标 + 线上 A/B'],
    });
  });

  it('缺 company_research / dimension_questions 时兜底不抛错', () => {
    const iv = prepRecordToInterview(buildRecord({ company_research: null, dimension_questions: [] }));

    expect(iv.preparation.companyResearch.background).toBe('字节跳动核心业务线');
    expect(iv.preparation.companyResearch.recentNews).toEqual([]);
    expect(iv.preparation.highFreqQuestions).toEqual([]);
    expect(iv.preparation.recommendedExperiences).toEqual([]);
  });
});

describe('buildInterviewFromPrep', () => {
  it('按 meta 与 prep 构建最终 Interview（含自定义元信息覆盖）', () => {
    const iv = buildInterviewFromPrep(
      {
        round_type: 'HR面',
        dimension_questions: [],
        company_research: null,
        created_at: '2026-09-18T08:30:00',
      },
      { id: 'prep-1', jobId: 'job-1', company: '腾讯', role: 'HRBP' }
    );

    expect(iv.roundName).toBe('面试准备 · HR面');
    expect(iv.roundType).toBe('hr');
    expect(iv.company).toBe('腾讯');
    expect(iv.role).toBe('HRBP');
  });

  it('无 round_type 时 roundName 默认面试准备', () => {
    const iv = buildInterviewFromPrep(
      { round_type: '', dimension_questions: [], company_research: null, created_at: null },
      { id: 'prep-x', company: 'X', role: 'Y' }
    );
    expect(iv.roundName).toBe('面试准备');
    expect(iv.time).toBe('');
  });
});

describe('mapRoundType / roundTypeToCn', () => {
  it('mapRoundType：tech / product / hr / comprehensive 关键词语义映射', () => {
    expect(mapRoundType('技术面')).toBe('tech');
    expect(mapRoundType('tech')).toBe('tech');
    // legacy 行为保留：'业务' 先命中 product 分支（product → 业务），business 分支不可达
    expect(mapRoundType('业务面')).toBe('product');
    expect(mapRoundType('HR面')).toBe('hr');
    expect(mapRoundType('总监面')).toBe('comprehensive');
    expect(mapRoundType('综合面')).toBe('comprehensive');
    expect(mapRoundType('其他')).toBe('other');
  });

  it('roundTypeToCn：前端枚举 → 后端中文名', () => {
    expect(roundTypeToCn('tech')).toBe('技术面');
    expect(roundTypeToCn('business')).toBe('业务面');
    expect(roundTypeToCn('hr')).toBe('HR面');
    expect(roundTypeToCn('comprehensive')).toBe('综合面');
  });
});