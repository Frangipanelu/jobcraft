import { describe, it, expect } from 'vitest';
import type { InterviewReviewResult } from '../../api/types';
import type { Experience } from '../../types/jobcraft';
import {
  buildReviewPatchFromAnalysis,
  buildReviewFromPatch,
  nextExperienceVersion,
  applyProposedChanges,
  applyFeedbackSuggestions,
  buildVersionRecord,
} from './mappers';

const ANALYSIS: InterviewReviewResult = {
  record_id: 101,
  user_id: 1,
  title: '字节跳动 AI 产品经理技术面复盘',
  company: '字节跳动',
  position: 'AI 产品经理',
  round_type: '技术面',
  overall_score: 85,
  summary: '整体表现良好，指标拆解清晰',
  strengths: ['指标拆解清晰'],
  weaknesses: ['商业闭环考虑不足'],
  action_items: ['补充选型对比'],
  questions: [
    {
      sequence: 1,
      start_time: '0.1',
      speaker: '面试官',
      question_text: '如何设计 RAG 评测体系？',
      dimension: '技术深度',
      level: '深挖',
      intent: '考察评测体系设计',
      expected_answer: '拆分维度与指标',
      my_answer: '拆分评测维度，离线指标 + 线上 A/B',
      score: 85,
      feedback: ['缺商业闭环量化'],
      suggestions: ['补充选型对比'],
      related_card_id: null,
      related_card_title: null,
    },
  ],
  created_at: '2026-09-19',
};

const INTERVIEW = {
  id: 'prep-7',
  jobId: '12',
  company: '字节跳动',
  role: 'AI 产品经理',
  roundNumber: 1,
  roundName: '面试准备 · 技术面',
  roundType: 'tech',
  time: '2026-09-20 10:00',
  format: 'video',
  readinessPercent: 80,
  status: 'preparing',
} as const;

describe('buildReviewPatchFromAnalysis', () => {
  it('score 一律来自真实数据：competencies / metricCards / 星级由 overall / per-question score 派生', () => {
    const patch = buildReviewPatchFromAnalysis(ANALYSIS, 1);

    expect(patch.overallScore).toBe(85);
    expect(patch.totalQACount).toBe(1);
    expect(patch.highlights).toEqual(['指标拆解清晰']);
    expect(patch.drawbacks).toEqual(['商业闭环考虑不足']);
    expect(patch.aiDiagnosis).toBe('整体表现良好，指标拆解清晰');

    expect(patch.competencies).toHaveLength(4);
    expect(patch.competencies!.every((c) => c.score === 85)).toBe(true);

    const qa = patch.qaList![0];
    expect(qa.question).toBe('如何设计 RAG 评测体系？');
    expect(qa.identifiedIssues).toEqual(['缺商业闭环量化']);
    expect(qa.suggestionAdvice).toBe('补充选型对比');
    expect(qa.metricCards!.clarityScore).toBe(85);
    expect(qa.interviewerIntent.importanceStars).toBe(4);
  });

  it('无题目时不派生 competencies，qaList 为空数组', () => {
    const noQuestions = { ...ANALYSIS, questions: [] };
    const patch = buildReviewPatchFromAnalysis(noQuestions, 0);

    expect(patch.competencies).toBeUndefined();
    expect(patch.qaList).toEqual([]);
    expect(patch.totalQACount).toBe(0);
  });

  it('问题字段缺失时使用兜底文案且星级收敛在 [3,5]', () => {
    const bare = {
      ...ANALYSIS,
      overall_score: 30,
      questions: [
        {
          sequence: 1,
          start_time: '0.1',
          speaker: '面试官',
          question_text: '',
          dimension: '',
          level: '',
          intent: '',
          expected_answer: '',
          my_answer: '',
          score: 30,
          feedback: [],
          suggestions: [],
          related_card_id: null,
          related_card_title: null,
        },
      ],
    };
    const patch = buildReviewPatchFromAnalysis(bare, 1);

    const qa = patch.qaList![0];
    expect(qa.question).toBe('未记录题目');
    expect(qa.interviewerIntent.importanceStars).toBe(3);
    expect(qa.suggestionAdvice).toBe('');
  });
});

describe('buildReviewFromPatch', () => {
  it('合并 interview 与 patch，含默认值；无 patch 时 overallScore 为 0', () => {
    const review = buildReviewFromPatch({ ...INTERVIEW } as never, undefined);

    expect(review.id).toMatch(/^rev-/);
    expect(review.interviewId).toBe('prep-7');
    expect(review.company).toBe('字节跳动');
    expect(review.overallScore).toBe(0);
    expect(review.qaList).toEqual([]);
    expect(review.experienceFeedback).toEqual([]);
  });

  it('totalQACount 缺失时回退 qaBreakdown.length', () => {
    const review = buildReviewFromPatch(
      { ...INTERVIEW } as never,
      { overallScore: 85, qaBreakdown: [{ id: 'a', question: 'q' } as never] } as never,
    );
    expect(review.overallScore).toBe(85);
    expect(review.totalQACount).toBe(1);
  });
});

describe('nextExperienceVersion', () => {
  it('V1 → V1.1，且沉淀动作带 [实战高光沉淀] 前缀', () => {
    const exp = { currentVersion: 'V1' } as Experience;
    const { version, newAction } = nextExperienceVersion(exp, '补充选型对比');
    expect(version).toBe('V1.1');
    expect(newAction).toBe('[实战高光沉淀] 补充选型对比');
  });

  it('小数版本 +0.1', () => {
    const exp = { currentVersion: 'V2.5' } as Experience;
    expect(nextExperienceVersion(exp, 'x').version).toBe('V2.6');
  });
});

describe('applyProposedChanges', () => {
  const exp: Experience = {
    id: 'exp-7',
    title: '端侧大模型量化评测',
    company: '未来智能实验室',
    role: 'AI 产品经理',
    period: '2025.01 - 2025.08',
    background: '背景',
    problem: '旧职责',
    actions: ['旧动作A', '旧动作B', '旧动作C'],
    results: [],
    tags: [],
    currentVersion: 'V1',
    versionHistory: [],
    isConfirmed: true,
  };

  it('按 field 字段法应用 problem / actions（前置替换第二位开始）/ background', () => {
    const next = applyProposedChanges(exp, [
      { field: 'problem', from: '旧职责', to: '新职责（含选型对比）' },
      { field: 'actions', from: '旧动作A', to: '新动作A' },
      { field: 'background', from: '', to: '新增背景补充' },
    ]);

    expect(next.problem).toBe('新职责（含选型对比）');
    expect(next.actions).toEqual(['新动作A', '旧动作B', '旧动作C']);
    expect(next.background).toBe('新增背景补充');
  });

  it('兼容旧字段名 responsibility（历史复盘版本记录）', () => {
    const next = applyProposedChanges(exp, [
      { field: 'responsibility', from: '旧职责', to: '旧字段兼容职责' },
    ]);

    expect(next.problem).toBe('旧字段兼容职责');
  });
});

describe('applyFeedbackSuggestions', () => {
  it('suggestions 非空时前置 [面试复盘升级] 动作', () => {
    const exp = { actions: ['旧动作A'] } as Experience;
    const next = applyFeedbackSuggestions(exp, ['补充量化选型对比']);
    expect(next.actions[0]).toBe('[面试复盘升级] 补充量化选型对比');
    expect(next.actions[1]).toBe('旧动作A');
  });

  it('suggestions 为空时原样返回', () => {
    const exp = { actions: ['旧动作A'] } as Experience;
    expect(applyFeedbackSuggestions(exp, [])).toBe(exp);
  });
});

describe('buildVersionRecord', () => {
  it('生成 interview_review 来源的版本记录', () => {
    const record = buildVersionRecord(
      'V2',
      [{ field: 'problem', from: 'a', to: 'b' }],
      '基于面试真实复盘与面试官深挖问题进行证据增强',
      'interview_review',
    );
    expect(record.version).toBe('V2');
    expect(record.source).toBe('interview_review');
    expect(record.changes).toEqual([{ field: 'problem', from: 'a', to: 'b' }]);
    expect(record.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});