import type { JobAnalysisResult, CapabilityGapWire, WireJdClassification } from '../../api/types';
import type { JobAnalysisDetail } from '../../api/job';
import type { CapabilityGap, JDAnalysis, JDClassificationInfo } from '../../types/jobcraft';

/** analysisDetailToJD 的输入结构：JobAnalysisResult（创建路径）与 JobAnalysisDetail（列表路径）均满足。 */
type JDDetailInput = Pick<
  JobAnalysisDetail,
  | 'job_analysis_id'
  | 'job_id'
  | 'company'
  | 'position'
  | 'jd_text'
  | 'jd_requirements'
  | 'match_score'
  | 'gap_analysis'
  | 'dimension_requirements'
  | 'capability_gaps'
  | 'jd_classification'
  | 'created_at'
>;

/** wire 改写任务清单 → 领域模型（T-M4-2；缺省/非数组一律归空，报告页回退渲染）。 */
function wireToCapabilityGaps(list: CapabilityGapWire[] | undefined): CapabilityGap[] {
  if (!Array.isArray(list)) return [];
  return list.map((g, i) => ({
    id: g.id != null ? String(g.id) : `gap-${i}`,
    dimension: g.dimension || 'EXT',
    kind: g.kind === 'rewrite' ? 'rewrite' : 'evidence',
    status: g.status === 'weak' ? 'weak' : 'missing',
    severity: g.severity === 'high' || g.severity === 'low' ? g.severity : 'medium',
    jdEvidence: g.jd_evidence || '',
    current: g.current || '',
    rewriteHint: g.rewrite_hint || '',
    cardId: g.card_id != null ? String(g.card_id) : null,
    note: g.note || '',
  }));
}

/** wire 六维方向分类 → 领域模型（T-M4-4；缺省/非对象一律 undefined，渲染侧走空态）。 */
function wireToClassification(
  wire: WireJdClassification | null | undefined,
): JDClassificationInfo | undefined {
  if (!wire || typeof wire !== 'object') return undefined;
  return {
    id: wire.id,
    directionId: wire.direction_id ?? null,
    directionName: wire.direction_name ?? null,
    directionCode: wire.direction_code ?? null,
    jobFunction: wire.job_function || '',
    primaryRole: wire.primary_role || '',
    industry: wire.industry || '',
    product: wire.product || '',
    scenario: wire.scenario || '',
    skills: wire.skills || '',
    confidence: wire.confidence || '',
    source: wire.source || 'manual',
    status: wire.status || 'proposed',
  };
}

/** JD 分析查询缓存 key（react-query 唯读源）。 */
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
    // T-M5-5：后端 job 实体 id 优先（权威），缺省回退调用方传入的本地目标岗 id
    jobId: result.job_id != null ? `job-${result.job_id}` : jobId,
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
    capabilityGaps: wireToCapabilityGaps(result.capability_gaps),
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
    capabilityGaps: wireToCapabilityGaps(detail.capability_gaps),
    // T-M4-4：方向分类 additive 透传（无分类 → undefined，表格/详情走诚实空态）
    jdClassification: wireToClassification(detail.jd_classification),
    goal: goalText,
    recommendedExperiences: [],
    createdAt: detail.created_at || '',
    // T-M5-5：列表路径按 job_analysis.job_id 关联岗位（P4-4a），缺省 undefined 由报告页走空态
    jobId: detail.job_id != null ? `job-${detail.job_id}` : undefined
  };
}
