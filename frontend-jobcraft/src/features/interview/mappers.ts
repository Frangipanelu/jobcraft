import { CompanyResearchAspects, CompanyResearchShape, ResearchItemShape } from '../../api/types';
import { Interview, InterviewPrepRecord, InterviewPreparation } from '../../types/jobcraft';

/** Interviews 查询缓存 key（react-query 唯读源）。 */
export const INTERVIEWS_QUERY_KEY = ['interviews'] as const;

/**
 * 将后端 round_type 字符串映射为前端 InterviewRoundType。
 * 自 JobCraftContext 移出，作为映射唯一实现（context 与 hooks 共享，杜绝双份漂移）。
 */
export function mapRoundType(t: string): Interview['roundType'] {
  const r = (t || '').toLowerCase()
  if (r.includes('技术') || r.includes('tech')) return 'tech'
  if (r.includes('业务') || r.includes('product')) return 'product'
  if (r.includes('hr')) return 'hr'
  if (r.includes('总监') || r.includes('终') || r.includes('综合')) return 'comprehensive'
  if (r.includes('业务')) return 'business'
  return 'other'
}

/**
 * 将前端 InterviewRoundType 转为后端轮次中文名（提交 interview_prep 任务用）。
 * 自 JobCraftContext 移出；默认回退'技术面'（保持 legacy 行为）。
 */
export function roundTypeToCn(roundType: Interview['roundType']): string {
  switch (roundType) {
    case 'tech': return '技术面'
    case 'product': return '产品面'
    case 'business': return '业务面'
    case 'hr': return 'HR面'
    case 'comprehensive': return '综合面'
    default: return '技术面'
  }
}

/**
 * 将后端 InterviewPrepRecord 映射为前端 Interview。
 * 自 JobCraftContext 移出，作为映射唯一实现。
 */
export function prepRecordToInterview(rec: InterviewPrepRecord): Interview {
  return buildInterviewFromPrep(
    {
      round_type: rec.round_type,
      dimension_questions: rec.dimension_questions || [],
      company_research: rec.company_research,
      created_at: rec.created_at
    },
    {
      id: `prep-${rec.id}`,
      jobId: rec.job_analysis_id ? String(rec.job_analysis_id) : undefined,
      company: rec.company || '',
      role: rec.position || '',
      prepSource: rec
    }
  )
}

/**
 * 旧结构（aspects 缺失的历史缓存）→ companyResearch 映射。
 * T-P7-1 前的原逻辑保留，作为旧缓存读兜底。
 */
function legacyCompanyResearch(cr: CompanyResearchShape): InterviewPreparation['companyResearch'] {
  return {
    background: cr?.basic?.description || '',
    coreBusiness: cr?.business?.main_business || '',
    keyProducts: cr?.business?.product_names || [],
    relevantBusiness: cr?.basic?.industry || '',
    recentNews: (cr?.news || []).slice(0, 3).map((n) => (typeof n === 'string' ? n : (n?.title ?? ''))).filter(Boolean),
    aiHiringIntent: cr?.ai_hiring || ''
  };
}

/** aspect 条目列表 → 非空 content 列表（空 content 条目丢弃）。 */
function aspectContents(items?: ResearchItemShape[]): string[] {
  return (items || []).map((it) => (it?.content ? it.content : '')).filter(Boolean);
}

/**
 * 新结构 aspects（6 维逐条）→ companyResearch 推导（T-P7-1）：
 * background=overview 各条连接、coreBusiness=business 首条、
 * keyProducts=business 前 3 条、relevantBusiness=ecosystem 首条、
 * recentNews=recent 前 3 条（带 date 前缀）、aiHiringIntent 新结构无对应走旧字段。
 * 派生值为空的字段回退旧字段映射（同一记录理论上不会双形并存，纯防御）。
 */
function deriveCompanyResearch(cr: CompanyResearchShape): InterviewPreparation['companyResearch'] {
  const aspects: CompanyResearchAspects = cr.aspects || {};
  const legacy = legacyCompanyResearch(cr);
  const business = aspectContents(aspects.business);
  const keyProducts = business.slice(0, 3);
  const recentNews = (aspects.recent || [])
    .slice(0, 3)
    .map((it) => (!it?.content ? '' : it.date ? `${it.date} ${it.content}` : it.content))
    .filter(Boolean);
  const background = aspectContents(aspects.overview).join('；');
  return {
    background: background || legacy.background,
    coreBusiness: business[0] || legacy.coreBusiness,
    keyProducts: keyProducts.length ? keyProducts : legacy.keyProducts,
    relevantBusiness: aspectContents(aspects.ecosystem)[0] || legacy.relevantBusiness,
    recentNews: recentNews.length ? recentNews : legacy.recentNews,
    aiHiringIntent: legacy.aiHiringIntent
  };
}

/**
 * 公司调研双形消费入口（T-P7-1）：aspects 存在优先新结构推导，
 * 缺失（旧缓存）走旧字段映射，两者皆缺返回全空壳不抛。
 */
function buildCompanyResearch(cr: CompanyResearchShape): InterviewPreparation['companyResearch'] {
  return cr.aspects ? deriveCompanyResearch(cr) : legacyCompanyResearch(cr);
}

/**
 * 由后端面试准备结果（维度题 + 公司调研摘要）构建前端 Interview 全量模型。
 * 自 JobCraftContext 移出；语义原样搬移（status 'preparing'、逐题构建 preparedAnswer）。
 * 不再伪造 readinessPercent/星级/推荐分等假指标（FE-FAKE-01），缺值由消费方按真实数据显示。
 */
export function buildInterviewFromPrep(
  prep: {
    round_type: string
    dimension_questions: {
      dimension: string
      question: string
      answer_points: string[]
      card_ids: number[]
    }[]
    company_research?: CompanyResearchShape | null
    created_at?: string | null
  },
  meta: { id: string; jobId?: string; company: string; role: string; prepSource?: InterviewPrepRecord }
): Interview {
  const roundName = prep.round_type ? `面试准备 · ${prep.round_type}` : '面试准备'
  const cr = prep.company_research || {}
  const highFreqQuestions: InterviewPreparation['highFreqQuestions'] = (
    prep.dimension_questions || []
  ).map((dq, idx) => ({
    id: `${meta.id}-q-${idx}`,
    question: dq.question,
    evaluationFocus: dq.dimension || '',
    recommendedExperienceId: (dq.card_ids && dq.card_ids[0]) ? String(dq.card_ids[0]) : '',
    isPrepared: false,
    preparedAnswer: {
      mode: 'logic',
      logicFlow: dq.answer_points || [],
      keywords: dq.answer_points && dq.answer_points[0] ? [dq.answer_points[0]] : [],
      aiReference: dq.answer_points?.join('\n') || '',
      inScript: false
    }
  }))
  return {
    id: meta.id,
    jobId: meta.jobId,
    company: meta.company,
    role: meta.role,
    roundNumber: 1,
    roundName: roundName,
    roundType: mapRoundType(prep.round_type),
    time: prep.created_at ? prep.created_at.split('T')[0] + ' ' + (prep.created_at.split('T')[1]?.slice(0, 5) || '') : '',
    format: 'video',
    status: 'preparing',
    preparation: {
      companyResearch: buildCompanyResearch(cr),
      aiStrategy: {
        roundTypeDesc: prep.round_type ? `${prep.round_type}面试准备` : '面试准备',
        keyFocusAreas: (prep.dimension_questions || []).map((dq) => ({
          name: dq.dimension,
          desc: dq.question
        }))
      },
      recommendedExperiences: (prep.dimension_questions || [])
        .filter((dq) => dq.card_ids && dq.card_ids.length > 0)
        .map((dq) => ({
          experienceId: String(dq.card_ids[0]),
          proves: dq.answer_points ? dq.answer_points.slice(0, 2) : []
        })),
      highFreqQuestions
    },
    prepSource: meta.prepSource
  }
}