import { describe, it, expect } from 'vitest';
import { CompanyResearchAspects } from '../../api/types';
import { InterviewPrepRecord } from '../../types/jobcraft';
import { buildInterviewFromPrep, mapRoundType, prepRecordToInterview, roundTypeToCn } from './mappers';
import researchFixture from '../../../../tests/fixtures/company_research_payload.json';

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
    expect(iv.readinessPercent).toBeUndefined();
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
      proves: ['拆分评测维度', '离线指标 + 线上 A/B'],
    });
  });

  it('缺 company_research / dimension_questions 时兜底不抛错', () => {
    const iv = prepRecordToInterview(buildRecord({ company_research: null, dimension_questions: [] }));

    expect(iv.preparation.companyResearch.background).toBe('');
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

describe('buildInterviewFromPrep · 公司调研双形消费（T-P7-1）', () => {
  // 共享契约 fixture：与 BE tests/test_company_research_schema_unit.py 同一份
  // （tests/fixtures/company_research_payload.json），封死「单测绿但契约断」。
  const aspects = researchFixture.aspects as CompanyResearchAspects;

  it('aspects 存在时新结构推导（共享契约 fixture）：overview 连接 / business 首条与前 3 / recent 带日期', () => {
    const iv = buildInterviewFromPrep(
      {
        round_type: '技术面',
        dimension_questions: [],
        company_research: { aspects },
        created_at: null,
      },
      { id: 'prep-a', company: '字节跳动', role: 'AI 产品经理' }
    );

    expect(iv.preparation.companyResearch).toEqual({
      background:
        '字节跳动 2012 年成立于北京，团队规模 10 万+，处于 Pre-IPO 阶段；总部位于北京，在上海、深圳、杭州设有办公地',
      coreBusiness:
        '主营抖音、今日头条等内容产品，广告与电商为主要盈利方式，核心推荐算法自研',
      keyProducts: [
        '主营抖音、今日头条等内容产品，广告与电商为主要盈利方式，核心推荐算法自研',
        '飞书面向企业提供协同办公套件，走 to B 订阅收费',
      ],
      relevantBusiness:
        '位于短视频与内容分发赛道头部，海外 TikTok 面临多国监管不确定性（推断）',
      recentNews: [
        '2026-01-15 发布新一代 AI 编程助手，加码 to B 场景',
        '2026-02-02 秋招提前批已开放投递，技术岗占多数',
      ],
      aiHiringIntent: '',
    });
  });

  it('business 超过 3 条时 keyProducts 只取前 3（截断规则钉住）', () => {
    const longBusiness = Array.from({ length: 5 }, (_, i) => ({
      content: `业务线 ${i + 1}`,
      source_type: '官方' as const,
      sufficiency: 'partial' as const,
    }));
    const iv = buildInterviewFromPrep(
      {
        round_type: '技术面',
        dimension_questions: [],
        company_research: { aspects: { ...aspects, business: longBusiness } },
        created_at: null,
      },
      { id: 'prep-e', company: 'X', role: 'Y' }
    );

    expect(iv.preparation.companyResearch.keyProducts).toEqual([
      '业务线 1',
      '业务线 2',
      '业务线 3',
    ]);
  });

  it('aspects 存在但维级缺据（空列表）时该字段回退旧字段映射，无旧字段则为空', () => {
    const iv = buildInterviewFromPrep(
      {
        round_type: '技术面',
        dimension_questions: [],
        company_research: {
          aspects: { overview: [], business: [], ecosystem: [], team: [], recent: [], reputation: [] },
          basic: { description: '旧缓存描述', industry: 'AIGC' },
          business: { main_business: '旧缓存主营', product_names: ['旧产品'] },
          news: [{ title: '旧新闻' }],
          ai_hiring: '旧招聘意图',
        },
        created_at: null,
      },
      { id: 'prep-b', company: 'X', role: 'Y' }
    );

    expect(iv.preparation.companyResearch.background).toBe('旧缓存描述');
    expect(iv.preparation.companyResearch.coreBusiness).toBe('旧缓存主营');
    expect(iv.preparation.companyResearch.keyProducts).toEqual(['旧产品']);
    expect(iv.preparation.companyResearch.relevantBusiness).toBe('AIGC');
    expect(iv.preparation.companyResearch.recentNews).toEqual(['旧新闻']);
    expect(iv.preparation.companyResearch.aiHiringIntent).toBe('旧招聘意图');
  });

  it('aspects 缺失（旧缓存）走旧字段映射：news 对象/字符串混合', () => {
    const iv = buildInterviewFromPrep(
      {
        round_type: '技术面',
        dimension_questions: [],
        company_research: {
          basic: { description: '人工智能公司', industry: 'AIGC' },
          business: { main_business: '智能助手', product_names: ['豆包'] },
          news: [{ title: '发布新模型' }, '字符串新闻', { title: '' }],
          ai_hiring: '加大 AI 人才招聘',
        },
        created_at: null,
      },
      { id: 'prep-c', company: '字节跳动', role: 'AI 产品经理' }
    );

    expect(iv.preparation.companyResearch).toEqual({
      background: '人工智能公司',
      coreBusiness: '智能助手',
      keyProducts: ['豆包'],
      relevantBusiness: 'AIGC',
      recentNews: ['发布新模型', '字符串新闻'],
      aiHiringIntent: '加大 AI 人才招聘',
    });
  });

  it('aspects 与旧字段皆缺（{}）不抛，产出全空壳', () => {
    const iv = buildInterviewFromPrep(
      { round_type: '技术面', dimension_questions: [], company_research: {}, created_at: null },
      { id: 'prep-d', company: 'X', role: 'Y' }
    );

    expect(iv.preparation.companyResearch).toEqual({
      background: '',
      coreBusiness: '',
      keyProducts: [],
      relevantBusiness: '',
      recentNews: [],
      aiHiringIntent: '',
    });
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