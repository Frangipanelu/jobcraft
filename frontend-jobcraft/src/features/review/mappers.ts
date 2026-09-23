import type { InterviewReviewResult } from '../../api/types';
import {
  Experience,
  ExperienceVersionRecord,
  ExperienceProposedChange,
  Interview,
  InterviewQA,
  InterviewReview,
} from '../../types/jobcraft';

/**
 * 把后端面试复盘分析结果映射为前端消费的 `InterviewReview` 部分字段。
 * 自 JobCraftContext.buildReviewPatchFromAnalysis 移出，作为唯一实现。
 */
export function buildReviewPatchFromAnalysis(
  analysis: InterviewReviewResult,
  qaCount: number
): Partial<InterviewReview> {
  // 每个 ReviewedQuestion 只有单个 score（无四维拆分），故四维诊断沿用真实 score 派生，
  // 而非随机/硬编码；无题目时不下发 competencies，由详情页兜底渲染文案。
  let competencies: { name: string; score: number; benchmark: number }[] | undefined;
  if (analysis.questions && analysis.questions.length > 0) {
    competencies = [
      { name: '岗位匹配度', score: analysis.overall_score, benchmark: 80 },
      { name: '回答结构性', score: analysis.overall_score, benchmark: 78 },
      { name: '专业技术深度', score: analysis.overall_score, benchmark: 82 },
      { name: '表达清晰度', score: analysis.overall_score, benchmark: 75 }
    ];
  }

  const qaList: InterviewQA[] = (analysis.questions || []).map((q, idx) => {
    const score = q.score;
    const derived = {
      clarity: score,
      impact: score,
      decision: score,
      fluency: score
    };
    return {
      id: `qa-${q.sequence || idx + 1}`,
      qIndex: idx + 1,
      question: q.question_text || '未记录题目',
      score,
      candidateAnswer: q.my_answer || '',
      transcript: q.my_answer || undefined,
      metricCards: {
        clarityScore: score,
        clarityDesc: 'AI 综合评估',
        impactScore: score,
        impactDesc: 'AI 综合评估',
        decisionScore: score,
        decisionDesc: 'AI 综合评估',
        fluencyScore: score,
        fluencyDesc: 'AI 综合评估'
      },
      interviewerIntent: {
        mainPoints: [q.intent || q.dimension || ''],
        importanceStars: Math.max(3, Math.min(5, Math.round(score / 20))),
        productAbilityStars: Math.max(3, Math.min(5, Math.round(score / 20))),
        techDepthStars: Math.max(3, Math.min(5, Math.round(score / 20)))
      },
      answerAnalysis: {
        completeness: score,
        structure: score,
        persuasiveness: score,
        jobRelevance: score,
        clarity: derived.clarity,
        impact: derived.impact,
        decision: derived.decision,
        fluency: derived.fluency
      },
      identifiedIssues: q.feedback || [],
      suggestionAdvice: (q.suggestions || []).join(' ') || ''
    };
  });

  return {
    overallScore: analysis.overall_score,
    passProbability: analysis.overall_score >= 80 ? '通过概率较高' : '存在差距，建议针对性补强',
    totalQACount: qaCount,
    highlights: analysis.strengths || [],
    drawbacks: analysis.weaknesses || [],
    competencies,
    coreProblems: analysis.weaknesses || [],
    aiDiagnosis: analysis.summary || '',
    qaList
  };
}

/**
 * 根据面试对象 + 部分 patch 构建完整的 InterviewReview。
 * 自 JobCraftContext.addInterviewReview 构建逻辑移出，作为唯一实现。
 */
export function buildReviewFromPatch(
  interview: Interview,
  patch?: Partial<InterviewReview>
): InterviewReview {
  return {
    id: 'rev-' + Date.now(),
    interviewId: interview.id,
    company: interview.company,
    role: interview.role,
    roundName: interview.roundName,
    reviewDate: new Date().toISOString().split('T')[0],
    overallScore: patch?.overallScore ?? 0,
    passProbability: patch?.passProbability || '',
    totalQACount: patch?.totalQACount || patch?.qaBreakdown?.length || 0,
    highlights: patch?.highlights || [],
    drawbacks: patch?.drawbacks || [],
    competencies: patch?.competencies || [],
    coreProblems: patch?.coreProblems || [],
    preparationVsActual: patch?.preparationVsActual || [],
    aiDiagnosis: patch?.aiDiagnosis || '',
    qaBreakdown: patch?.qaBreakdown || [],
    qaList: patch?.qaList || [],
    experienceFeedback: patch?.experienceFeedback || [],
    experienceFeedbacks: patch?.experienceFeedbacks || []
  };
}

/**
 * 递增经历版本号（Vn → Vn+0.1）并生成沉淀动作文本。
 * 自 JobCraftContext.syncReviewToExperience 移出，作为唯一实现。
 */
export function nextExperienceVersion(
  exp: Experience,
  feedbackText: string
): { version: string; newAction: string } {
  const nextVerNum = (parseFloat(exp.currentVersion.replace('V', '')) + 0.1).toFixed(1);
  const version = `V${nextVerNum}`;
  const newAction = `[实战高光沉淀] ${feedbackText}`;
  return { version, newAction };
}

/**
 * 按 proposedChanges 的 field 字段法应用变更到经历对象。
 * 字段：problem（兼容旧名 responsibility）/ actions（前置） / background。
 * 自 JobCraftContext.applyReviewFeedback + commitExperienceDiff 移出，作为唯一实现。
 */
export function applyProposedChanges(
  exp: Experience,
  changes: ExperienceProposedChange[]
): Experience {
  const updatedExp = { ...exp };
  changes.forEach((change) => {
    if (change.field.includes('problem') || change.field.includes('responsibility')) {
      updatedExp.problem = change.to;
    } else if (change.field.includes('actions')) {
      updatedExp.actions = [change.to, ...exp.actions.slice(1)];
    } else if (change.field.includes('background')) {
      updatedExp.background = change.to;
    }
  });
  return updatedExp;
}

/**
 * 当 proposedChanges 为空时，将 suggestions[0] 作为动作前置。
 * 自 JobCraftContext.applyReviewFeedback 兜底逻辑移出，作为唯一实现。
 */
export function applyFeedbackSuggestions(
  exp: Experience,
  suggestions: string[]
): Experience {
  if (suggestions.length === 0) return exp;
  return {
    ...exp,
    actions: [`[面试复盘升级] ${suggestions[0]}`, ...exp.actions]
  };
}

/**
 * 构建经历版本记录。
 * 自 JobCraftContext.commitExperienceDiff / syncReviewToExperience / applyReviewFeedback 共用逻辑移出。
 */
export function buildVersionRecord(
  version: string,
  changes: ExperienceProposedChange[],
  reason: string,
  source: ExperienceVersionRecord['source']
): ExperienceVersionRecord {
  return {
    version,
    date: new Date().toISOString().split('T')[0],
    reason,
    source,
    changes
  };
}
