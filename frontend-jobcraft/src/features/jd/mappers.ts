import type { JobAnalysisResult, ATSProfile } from '../../api/types';
import type { JobAnalysisDetail } from '../../api/job';
import type { JDAnalysis } from '../../types/jobcraft';

/** analysisDetailToJD 的输入结构：JobAnalysisResult（创建路径）与 JobAnalysisDetail（列表路径）均满足。 */
type JDDetailInput = Pick<
  JobAnalysisDetail,
  | 'job_analysis_id'
  | 'company'
  | 'position'
  | 'jd_text'
  | 'jd_requirements'
  | 'match_score'
  | 'gap_analysis'
  | 'dimension_requirements'
  | 'created_at'
>;

/** JD 分析查询缓存 key（react-query 唯读源）。 */
export const JD_ANALYSES_QUERY_KEY = ['jdAnalyses'] as const;

/** 将职责列表拼接为 JD 文本块（结构化分析新增路径用）。自 JobCraftContext 移出。 */
export function dutiesText(duties: string[]): string {
  return duties.map((d, i) => `${i + 1}. ${d}`).join('\n');
}

/** 将带标签的任职要求拼接为 JD 文本块（结构化分析新增路径用）。自 JobCraftContext 移出。 */
export function requirementsText(requirements: { text: string; tag: string }[]): string {
  return requirements.map((r, i) => {
    const label = { hard: '（硬性门槛）', required: '（必选）', preferred: '（加分项）' }[r.tag] || '';
    return `${i + 1}. ${label}${r.text}`;
  }).join('\n');
}

/** 结构化 JD 分析映射的元信息（id/关联岗位/原文等由调用方提供）。 */
export interface StructuredJDAnalysisMeta {
  id: string;
  jobId?: string;
  company: string;
  role: string;
  rawText: string;
}

/**
 * 将后端结构化 JD 分析结果（analyze-ats-structured）转换为前端 JDAnalysis。
 *
 * 自 JobCraftContext.createStructuredJDAnalysis 内联映射移出，作为唯一实现。
 * 与无结构化文本路径一致地以 cache 前置方式新增记录。
 */
export function structuredResultToJD(
  result: { ats_profile?: ATSProfile | null },
  meta: StructuredJDAnalysisMeta,
): JDAnalysis {
  const ats = result.ats_profile;
  const subtext = (ats as unknown as { subtext_decoded?: Array<{
    surface_requirement?: string;
    hidden_meaning?: string;
    key_ability?: string;
  }> })?.subtext_decoded || [];

  return {
    id: meta.id,
    jobId: meta.jobId,
    company: meta.company,
    role: meta.role,
    salaryRange: ats?.salary || '面议',
    rawText: meta.rawText,
    createdAt: new Date().toISOString().split('T')[0],
    matchScore: 0,
    recommendationStars: 0,
    verdictSummary: '结构化分析完成',
    whyMatch: '',
    keyRisks: '',
    resumeAdvice: ats?.key_metrics || [],
    coreRequirements: [
      {
        category: '核心职责',
        items: ats?.responsibilities || []
      },
      {
        category: '任职资格',
        items: [...(ats?.required_skills || []), ...(ats?.preferred_skills || [])]
      }
    ],
    atsKeywords: {
      hardSkills: ats?.required_skills || [],
      softSkills: ats?.preferred_skills || [],
      expKeywords: ats?.key_metrics || [],
      coveragePercent: 0
    },
    subtextAnalysis: subtext.map((s, idx) => ({
      id: `sub-${idx}`,
      rawJD: s.surface_requirement || '',
      literalMeaning: s.hidden_meaning || '',
      realEvaluation: s.key_ability || ''
    })),
    skillGaps: [],
    recommendedExperiences: []
  };
}

/**
 * 将后端 JobAnalysisResult 转换为前端 JDAnalysis（创建/分析回填路径）。
 *
 * 自 JobCraftContext 移出，作为映射唯一实现（context 与 hooks 共享，杜绝双份漂移）。
 */
export function analysisToJD(result: JobAnalysisResult, jobId?: string): JDAnalysis {
  const ats = result.ats_profile;

  return {
    id: String(result.job_analysis_id),
    jobId: jobId,
    company: result.company,
    role: result.position,
    salaryRange: ats?.salary || '面议',
    rawText: result.jd_text,
    createdAt: result.created_at || new Date().toISOString().split('T')[0],
    matchScore: result.match_score || 0,
    recommendationStars: Math.round((result.match_score || 0) / 20),
    verdictSummary: result.gap_analysis || '分析完成',
    whyMatch: result.match_level || '',
    keyRisks: '',
    resumeAdvice: result.suggestions?.map(s => s.message) || [],
    coreRequirements: [
      {
        category: '核心职责',
        items: ats?.responsibilities || []
      },
      {
        category: '任职资格',
        items: [...(ats?.required_skills || []), ...(ats?.preferred_skills || [])]
      }
    ],
    atsKeywords: {
      hardSkills: ats?.required_skills || [],
      softSkills: ats?.preferred_skills || [],
      expKeywords: ats?.key_metrics || [],
      coveragePercent: Math.round(result.match_score || 0)
    },
    subtextAnalysis: [],
    skillGaps: (() => {
      // 从 jd_requirements 获取所有技能要求
      const allSkills = [
        ...(result.jd_requirements?.hard_skills || []),
        ...(result.jd_requirements?.soft_skills || []),
        ...(result.jd_requirements?.keywords || [])
      ];
      // 从 per_card_scores 获取已匹配的技能
      const matchedSkills = new Set<string>();
      (result.per_card_scores || []).forEach(ps => {
        (ps.matched || []).forEach(s => matchedSkills.add(s));
      });
      // 构建能力匹配列表
      return allSkills.map((skill, idx) => {
        const isMatched = matchedSkills.has(skill);
        return {
          id: `skill-${idx}`,
          capability: skill,
          userEvidence: isMatched ? '经历卡已覆盖' : '',
          requirement: skill,
          gap: isMatched ? '已匹配' : '待补充',
          recommendation: isMatched ? '' : '建议补充相关经历或调整表述'
        };
      });
    })(),
    recommendedExperiences: result.per_card_scores?.map(ps => ({
      experienceId: String(ps.card_id),
      matchScore: ps.score,
      matchingJDReq: ps.matched?.join(', ') || '',
      reason: ps.missing?.join(', ') || ''
    })) || []
  }
}

/**
 * 将后端分析详情（GET /job/analyze/{id} 或 /job/analyses 列表条目）转换为前端 JDAnalysis。
 *
 * 自 JobCraftContext.loadJdAnalyses 内联映射提取，作为唯一实现：
 * 依据 dimension_requirements 构建 skillGaps 与 goal，jd_requirements 构建 coreRequirements / atsKeywords。
 */
export function analysisDetailToJD(detail: JDDetailInput): JDAnalysis {
  const jdReq = (detail.jd_requirements || {}) as Record<string, unknown>;
  const hardSkills = (jdReq.hard_skills as string[]) || [];
  const softSkills = (jdReq.soft_skills as string[]) || [];
  const responsibilities = (jdReq.responsibilities as string[]) || [];
  const dimReqs = (detail.dimension_requirements || []) as Array<{ dimension: string; level: number; evidence: string }>;

  // 从 dimension_requirements 构建能力匹配数据
  const allSkills = [...hardSkills, ...softSkills];
  const skillGaps = allSkills.map((skill: string, idx: number) => {
    // 尝试从 dimension_requirements 匹配证据
    const matchedDim = dimReqs.find(d => d.evidence && d.evidence.includes(skill));
    return {
      id: `skill-${idx}`,
      capability: skill,
      userEvidence: matchedDim?.evidence || '',
      requirement: skill,
      gap: matchedDim && matchedDim.level >= 3 ? '已匹配' : '待补充',
      recommendation: ''
    };
  });

  // 从 dimension_requirements 构建岗位目标
  const goalText = dimReqs.length > 0
    ? dimReqs.map(d => d.evidence).filter(Boolean).join('；')
    : (detail.gap_analysis as string) || '待分析';

  const gapAnalysis = detail.gap_analysis as unknown;
  const gapText = Array.isArray(gapAnalysis)
    ? (gapAnalysis as string[]).join(' ')
    : String(detail.gap_analysis || '');

  return {
    id: String(detail.job_analysis_id),
    company: detail.company || '',
    role: detail.position || '',
    salaryRange: '',
    rawText: detail.jd_text || '',
    matchScore: detail.match_score || 0,
    recommendationStars: Math.round((detail.match_score || 0) / 20),
    verdictSummary: gapText,
    whyMatch: '',
    keyRisks: '',
    resumeAdvice: [],
    coreRequirements: [
      { category: '核心职责', items: responsibilities },
      { category: '任职资格', items: allSkills }
    ],
    atsKeywords: {
      hardSkills,
      softSkills,
      expKeywords: (jdReq.keywords as string[]) || [],
      coveragePercent: Math.round(detail.match_score || 0)
    },
    subtextAnalysis: [],
    skillGaps,
    goal: goalText,
    recommendedExperiences: [],
    createdAt: detail.created_at || '',
    jobId: undefined
  };
}
