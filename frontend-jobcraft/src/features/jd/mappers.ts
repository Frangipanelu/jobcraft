import type { JobAnalysisResult } from '../../api/types';
import type { JDAnalysis } from '../../types/jobcraft';

/** JD 分析查询缓存 key（迁移视图 + context 镜像双写共用）。 */
export const JD_ANALYSES_QUERY_KEY = ['jdAnalyses'] as const;

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
 * 将后端分析详情（getJobAnalysis 返回）转换为前端 JDAnalysis（历史列表加载路径）。
 *
 * 自 JobCraftContext.loadJdAnalyses 内联映射提取，作为唯一实现：
 * 依据 dimension_requirements 构建 skillGaps 与 goal，jd_requirements 构建 coreRequirements / atsKeywords。
 */
export function analysisDetailToJD(detail: JobAnalysisResult): JDAnalysis {
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

  return {
    id: String(detail.job_analysis_id),
    company: detail.company || '',
    role: detail.position || '',
    salaryRange: '',
    rawText: detail.jd_text || '',
    matchScore: detail.match_score || 0,
    recommendationStars: Math.round((detail.match_score || 0) / 20),
    verdictSummary: Array.isArray(gapAnalysis)
      ? (gapAnalysis as string[]).join(' ')
      : (detail.gap_analysis || ''),
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
