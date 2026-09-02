import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  ArrowLeft,
  ArrowRight,
  RotateCw,
  Edit,
  MoreHorizontal,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Star,
  ExternalLink,
  BookOpen,
  Check,
  Briefcase,
  FileText,
  Sparkles
} from 'lucide-react';

interface JDReportDetailViewProps {
  analysisId?: string;
  onNavigateToResume?: () => void;
  onNavigateToInterview?: () => void;
  embedded?: boolean;
}

// Default structured high-fidelity mock data matching Image 1
const FALLBACK_DATA = {
  company: '字节跳动',
  position: 'AI 产品经理（搜索与生成方向）',
  location: '上海',
  date: '2026.08.30',
  tags: ['AI 产品经理', '搜索 / 推荐', '大模型', '0-1 产品'],
  verdict: {
    label: '值得投递',
    score: 92,
    stars: 5,
    matchLabel: 'MATCH',
    why: '你的 AI 产品、搜索和数据分析经验与岗位核心要求高度重合，从 0 到 1 的经历和数据驱动决策能力尤其匹配。',
    advantagesCount: 3,
    gapsCount: 2,
    weaknessCount: 1,
    risk: '缺少大型 AI 产品商业化变现经验，以及 B2B 方向的规模化落地案例。',
    suggestions: [
      '简历重点突出 AI 搜索与评测体系建设从 0 到 1 过程',
      '补充 Prompt 工程与大模型微调相关的评测指标描述',
      '强化业务数据闭环（如 nDCG、MRR、留存率等具体量化指标）'
    ]
  },
  goal: '通过 AI 技术提升搜索体验与效率，构建智能化产品能力，驱动业务增长。',
  responsibilities: [
    { num: '01', title: '产品规划与设计' },
    { num: '02', 用户需求: '用户需求分析与产品策略', title: '用户需求分析与产品策略' },
    { num: '03', title: '跨团队协作与项目推进' },
    { num: '04', title: '数据驱动产品优化' }
  ],
  competencyMatch: [
    {
      ability: 'AI 产品设计',
      requirement: '精通 AI 产品从 0 到 1 全流程',
      evidence: 'AI 搜索评测体系、MVP 项目',
      score: 5,
      level: 'high'
    },
    {
      ability: '搜索 / 推荐',
      requirement: '搜索相关产品经验',
      evidence: 'AI 搜索优化项目',
      score: 5,
      level: 'high'
    },
    {
      ability: '数据分析',
      requirement: '数据驱动，能通过数据发现问题',
      evidence: 'NDCG / MRR / AB 实验',
      score: 5,
      level: 'high'
    },
    {
      ability: '商业化',
      requirement: '了解商业模式与变现',
      evidence: '部分项目有付费探索经验',
      score: 3,
      level: 'medium'
    },
    {
      ability: 'B2B SaaS',
      requirement: 'B2B 产品经验',
      evidence: '暂无相关经验',
      score: 1,
      level: 'low'
    }
  ],
  atsGrouped: {
    high: ['AI 产品', '搜索', '大模型', '数据分析', '用户体验', '产品设计'],
    partial: ['Prompt', '商业化', '用户增长'],
    unmatched: ['B2B', 'SaaS 销售']
  },
  subtext: [
    {
      num: '01',
      original: '“大模型 / AIGC 产品经验优先”',
      literal: '候选人需要有 LLM / AIGC 相关产品经验',
      actual:
        '这是核心门槛之一，非加分项。没有 AI 产品经验很可能直接被简历过滤。建议你将 AI 搜索评测与大模型 MVP 项目置于简历最前面。'
    },
    {
      num: '02',
      original: '“推动跨团队协作、高效落地”',
      literal: '有跨部门协作推进项目上线的经验',
      actual:
        '团队内部跨算法、工程、业务协同链条长。这里实际考察的是你在资源受限或多方阻力下如何强力推进行动，需准备真实冲突解决案例。'
    },
    {
      num: '03',
      original: '“对 AI 和搜索产品有深度思考”',
      literal: '对行业有认知和见解',
      actual:
        '面试中大概率会有开放题考察产品哲学与技术边界判断，例如“你觉得 AI 搜索的核心体验瓶颈是什么”。建议提前准备独立观点。'
    }
  ],
  recommended: [
    {
      id: '1',
      num: '#1',
      title: 'AI 搜索优化项目',
      type: '项目经历',
      year: '2026',
      matchScore: 95,
      tags: ['AI 产品能力', '数据分析', '搜索评测'],
      reason:
        '直接命中岗位核心要求，具备 AI + 搜索 + 数据分析三大核心关键词，建议作为简历与面试首选主打项目。'
    },
    {
      id: '2',
      num: '#2',
      title: 'AI 产品 MVP 项目',
      type: '项目经历',
      year: '2025',
      matchScore: 88,
      tags: ['0-1产品经历', '用户研究', '敏捷落地'],
      reason:
        '具备完整产品闭环，展现从需求发现到上线的推动力，有效印证你的产品感与用户洞察能力。'
    },
    {
      id: '3',
      num: '#3',
      title: '数据平台产品经理',
      type: '工作经历',
      year: '2023–2025',
      matchScore: 62,
      tags: ['跨团队协作', '指标体系'],
      reason:
        '跨团队推进经验可作为协作能力的佐证，重点突出可迁移的数据驱动能力。'
    }
  ]
};

// Section Header matching Image 1: 01 岗位理解  这个岗位需要解决什么问题
function SectionHeaderImageStyle({
  num,
  title,
  subtitle
}: {
  num: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex items-baseline gap-3 mb-4 pb-2">
      <span className="text-[16px] font-black text-[#111814] tracking-tight">{num}</span>
      <h2 className="text-[16px] font-black text-[#111814] tracking-tight">{title}</h2>
      <span className="text-xs text-[#737873] font-normal">{subtitle}</span>
    </div>
  );
}

// 5-dot score indicator
function ScoreDots({ score, level }: { score: number; level: 'high' | 'medium' | 'low' }) {
  const dotColor =
    level === 'high'
      ? 'bg-sage'
      : level === 'medium'
      ? 'bg-warning'
      : 'bg-warning';

  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`w-2.5 h-2.5 rounded-full ${
            i < score ? dotColor : 'bg-[#E4E7E3]'
          }`}
        />
      ))}
    </div>
  );
}

export const JDReportDetailView: React.FC<JDReportDetailViewProps> = ({
  analysisId,
  onNavigateToResume,
  onNavigateToInterview,
  embedded = false
}) => {
  const {
    jdAnalyses,
    jobs,
    setSelectedJobId,
    setSelectedJDId,
    jdAnalysisReturnTarget,
    setJdAnalysisReturnTarget,
    navigateTo,
    showToast
  } = useJobCraft();

  const [isReanalyzing, setIsReanalyzing] = useState(false);

  const currentAnalysis = jdAnalyses.find((a) => a.id === analysisId) || jdAnalyses[0];

  const data = {
    company: currentAnalysis?.company || FALLBACK_DATA.company,
    position: currentAnalysis?.role || FALLBACK_DATA.position,
    location: currentAnalysis?.location || FALLBACK_DATA.location,
    date: currentAnalysis?.createdAt ? currentAnalysis.createdAt.replace(/-/g, '.') : FALLBACK_DATA.date,
    tags: FALLBACK_DATA.tags,
    verdict: {
      label: currentAnalysis?.matchScore && currentAnalysis.matchScore >= 85 ? '值得投递' : '值得投递',
      score: currentAnalysis?.matchScore || FALLBACK_DATA.verdict.score,
      stars: 5,
      matchLabel: 'MATCH',
      why: currentAnalysis?.keyInsights?.[0] || FALLBACK_DATA.verdict.why,
      advantagesCount: 3,
      gapsCount: 2,
      weaknessCount: 1,
      risk: currentAnalysis?.keyRisks?.[0] || FALLBACK_DATA.verdict.risk,
      suggestions: currentAnalysis?.strategicAdvice || FALLBACK_DATA.verdict.suggestions
    },
    goal: FALLBACK_DATA.goal,
    responsibilities: FALLBACK_DATA.responsibilities,
    competencyMatch: FALLBACK_DATA.competencyMatch,
    atsGrouped: FALLBACK_DATA.atsGrouped,
    subtext: FALLBACK_DATA.subtext,
    recommended: FALLBACK_DATA.recommended
  };

  const matchedJob = currentAnalysis
    ? jobs.find(
        (j) =>
          j.id === currentAnalysis.jobId ||
          (j.company === currentAnalysis.company && j.role === currentAnalysis.role)
      ) || jobs[0]
    : undefined;

  const handleReturnToWizard = () => {
    if (matchedJob) {
      setSelectedJobId(matchedJob.id);
    }
    if (currentAnalysis) {
      setSelectedJDId(currentAnalysis.id);
    }
    const target = jdAnalysisReturnTarget;
    setJdAnalysisReturnTarget(null);

    if (target === 'create_interview') {
      showToast({
        type: 'success',
        title: '已带入岗位并返回',
        message: `已自动关联「${data.company} · ${data.position}」进入新建面试。`
      });
      navigateTo('create_interview');
    } else if (target === 'create_review') {
      showToast({
        type: 'success',
        title: '已带入岗位并返回',
        message: `已自动关联「${data.company} · ${data.position}」进入新建复盘。`
      });
      navigateTo('create_review');
    } else {
      navigateTo('jd_analysis_center');
    }
  };

  const handleGoToResume = () => {
    if (onNavigateToResume) {
      onNavigateToResume();
    } else if (matchedJob) {
      setSelectedJobId(matchedJob.id);
      navigateTo('resume_editor', { jobId: matchedJob.id });
    } else {
      navigateTo('resume_editor');
    }
  };

  const handleReanalyze = () => {
    setIsReanalyzing(true);
    setTimeout(() => {
      setIsReanalyzing(false);
      showToast({
        type: 'success',
        title: '重新研判完成',
        message: '已结合最新经历库重新校验 ATS 关键词与胜任力匹配度。'
      });
    }, 600);
  };

  return (
    <div className={`min-h-full bg-white pb-24 ${embedded ? 'pt-4 sm:pt-6' : 'pt-6 sm:pt-8'}`}>
      <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-6 sm:px-8 lg:px-10 animate-in fade-in duration-300">
        
        {/* ── Standalone Mode Header (Only shown when NOT embedded in JobWorkspaceView) ── */}
        {!embedded && (
          <div className="mb-6">
            {/* Title & Re-analyze Button */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-2.5">
              <h1 className="text-2xl sm:text-[26px] font-extrabold text-[#111814] tracking-tight">
                {data.position}
              </h1>

              <button
                type="button"
                onClick={handleReanalyze}
                disabled={isReanalyzing}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1E4D3C] hover:bg-[#153B2E] text-white text-xs sm:text-sm font-bold shadow-xs hover:shadow transition cursor-pointer shrink-0"
              >
                <RotateCw className={`w-4 h-4 text-white ${isReanalyzing ? 'animate-spin' : ''}`} />
                <span>重新分析</span>
              </button>
            </div>

            {/* Subtitle Info */}
            <div className="text-xs sm:text-[13px] text-[#737873] font-normal mb-3">
              <span>{data.company}</span>
              <span className="mx-1.5">·</span>
              <span>{data.location}</span>
              <span className="mx-1.5">·</span>
              <span>分析于 {data.date}</span>
            </div>

            {/* Tags (Image 1 Style) */}
            <div className="flex flex-wrap gap-2 mb-6">
              {data.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2.5 py-1 bg-[#F2F4F1] text-[#526058] rounded-md font-medium"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* ── AI 岗位匹配结论 Card (Exact Match with Image 1) ── */}
        <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-2xl p-6 sm:p-7 mb-8 shadow-2xs relative">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
            
            {/* Left Column: Verdict, text, 3 indicators */}
            <div className="flex-1 space-y-3.5">
              {/* Category Pill Tag */}
              <div className="inline-block text-[11px] font-bold text-[#526058] bg-[#EEF2EE] px-2.5 py-0.5 rounded">
                AI 岗位匹配结论
              </div>

              {/* Big Title */}
              <div className="text-[28px] sm:text-[32px] font-black text-[#111814] tracking-tight">
                {data.verdict.label}
              </div>

              {/* Description */}
              <p className="text-xs sm:text-[13.5px] text-[#526058] leading-relaxed max-w-2xl font-normal m-0">
                {data.verdict.why}
              </p>

              {/* 3 Indicators Row (Matching Image 1) */}
              <div className="flex flex-wrap items-center gap-4 sm:gap-6 pt-2">
                {/* 1. Core Advantages */}
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="w-4.5 h-4.5 rounded-full bg-sage text-white flex items-center justify-center text-[10px] font-bold shrink-0">
                    ✓
                  </span>
                  <span className="font-bold text-[#111814]">
                    {data.verdict.advantagesCount} 项核心优势
                  </span>
                  <span className="text-[#737873]">高度匹配</span>
                </div>

                {/* 2. Capability Gaps */}
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-warning text-[13px] font-bold shrink-0">
                    ⚠️
                  </span>
                  <span className="font-bold text-[#111814]">
                    {data.verdict.gapsCount} 项能力缺口
                  </span>
                  <span className="text-[#737873]">需要补强</span>
                </div>

                {/* 3. Experience Shortage */}
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="w-4.5 h-4.5 rounded-full bg-error text-white flex items-center justify-center text-[10px] font-bold shrink-0">
                    ✕
                  </span>
                  <span className="font-bold text-[#111814]">
                    {data.verdict.weaknessCount} 项经验不足
                  </span>
                  <span className="text-[#737873]">建议积累</span>
                </div>
              </div>
            </div>

            {/* Right Column: Score, MATCH, Stars, 匹配度 (Exact match with Image 1) */}
            <div className="flex flex-col items-center justify-center shrink-0 self-center md:self-auto px-6 py-2">
              <div className="text-[46px] sm:text-[52px] font-black text-[#1E3A2F] leading-none tracking-tight">
                {data.verdict.score}%
              </div>
              <div className="text-[11px] font-bold text-[#737873] tracking-widest mt-1 mb-1.5 uppercase">
                {data.verdict.matchLabel}
              </div>
              <div className="flex items-center gap-1 text-warning text-sm mb-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <span key={i}>★</span>
                ))}
              </div>
              <div className="text-[11px] text-[#737873] font-medium">
                匹配度
              </div>
            </div>

          </div>
        </div>

        {/* ── 01 岗位理解 (Exact Match with Image 1) ── */}
        <div className="mb-9">
          <SectionHeaderImageStyle
            num="01"
            title="岗位理解"
            subtitle="这个岗位需要解决什么问题"
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left Card: 岗位目标 */}
            <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-5 shadow-2xs">
              <div className="text-[13px] font-bold text-[#111814] mb-2.5">
                岗位目标
              </div>
              <p className="text-xs sm:text-[13px] text-[#526058] leading-relaxed font-normal m-0">
                {data.goal}
              </p>
            </div>

            {/* Right Card: 核心职责 */}
            <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-5 shadow-2xs">
              <div className="text-[13px] font-bold text-[#111814] mb-3">
                核心职责
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2.5 text-xs text-[#526058]">
                {data.responsibilities.map((r) => (
                  <div key={r.num} className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-[#737873]">
                      {r.num}
                    </span>
                    <span className="text-[#2B3830] font-medium">
                      {r.title}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── 02 能力匹配 (Exact Match with Image 1 Table) ── */}
        <div className="mb-9">
          <SectionHeaderImageStyle
            num="02"
            title="能力匹配"
            subtitle="你的能力与岗位要求的匹配情况"
          />

          <div className="bg-white border border-[#E2E6E2] rounded-xl overflow-hidden shadow-2xs">
            {/* Table Header */}
            <div className="grid grid-cols-[140px_1fr_1fr_110px] bg-[#FAFBF9] px-5 py-3 border-b border-[#E2E6E2] text-xs font-bold text-[#737873]">
              <span>能力项</span>
              <span>岗位要求</span>
              <span>你的佐证</span>
              <span>匹配度</span>
            </div>

            {/* Table Body */}
            <div className="divide-y divide-[#EFEFEA]">
              {data.competencyMatch.map((item, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[140px_1fr_1fr_110px] px-5 py-3.5 items-center text-xs sm:text-[13px] bg-white hover:bg-[#FAFBF9] transition"
                >
                  <span className="font-bold text-[#111814]">{item.ability}</span>
                  <span className="text-[#526058] pr-3 leading-relaxed">{item.requirement}</span>
                  <span className="text-[#2B3830] pr-3 font-medium leading-relaxed">{item.evidence}</span>
                  <div className="flex items-center">
                    <ScoreDots score={item.score} level={item.level as any} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── 03 关键词匹配 (ATS) (Exact Match with Image 1) ── */}
        <div className="mb-9">
          <SectionHeaderImageStyle
            num="03"
            title="关键词匹配 (ATS)"
            subtitle="关键词覆盖率与匹配情况"
          />

          <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-5 sm:p-6 shadow-2xs">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* 高匹配 */}
              <div>
                <div className="text-xs font-bold text-[#737873] mb-3">
                  高匹配
                </div>
                <div className="flex flex-wrap gap-2">
                  {data.atsGrouped.high.map((kw) => (
                    <span
                      key={kw}
                      className="text-xs px-2.5 py-1 bg-sage-soft text-sage rounded-md font-medium flex items-center gap-1 border border-sage/20"
                    >
                      <span>✓</span>
                      <span>{kw}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* 部分匹配 */}
              <div>
                <div className="text-xs font-bold text-[#737873] mb-3">
                  部分匹配
                </div>
                <div className="flex flex-wrap gap-2">
                  {data.atsGrouped.partial.map((kw) => (
                    <span
                      key={kw}
                      className="text-xs px-2.5 py-1 bg-warning-bg text-warning rounded-md font-medium flex items-center gap-1 border border-warning/20"
                    >
                      <span>✓</span>
                      <span>{kw}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* 未匹配 */}
              <div>
                <div className="text-xs font-bold text-[#737873] mb-3">
                  未匹配
                </div>
                <div className="flex flex-wrap gap-2">
                  {data.atsGrouped.unmatched.map((kw) => (
                    <span
                      key={kw}
                      className="text-xs px-2.5 py-1 bg-error-bg text-error rounded-md font-medium flex items-center gap-1 border border-error/20"
                    >
                      <span>✕</span>
                      <span>{kw}</span>
                    </span>
                  ))}
                </div>
              </div>

            </div>
          </div>
        </div>

        {/* ── 04 隐含要求解析 (Exact Match with Image 1) ── */}
        <div className="mb-9">
          <SectionHeaderImageStyle
            num="04"
            title="隐含要求解析"
            subtitle="从 JD 中识别出隐含的关键要求"
          />

          <div className="space-y-3.5">
            {data.subtext.map((item) => (
              <div
                key={item.num}
                className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-4.5 sm:p-5 shadow-2xs space-y-2.5"
              >
                <div className="flex items-center gap-2.5">
                  <span className="text-xs font-bold text-[#737873]">
                    {item.num}
                  </span>
                  <span className="text-xs sm:text-[13px] font-bold text-[#111814]">
                    {item.original}
                  </span>
                </div>

                <div className="bg-white p-3.5 rounded-lg border border-[#EAECE8] pl-4">
                  <div className="text-[11px] font-bold text-[#737873] mb-1">
                    你的解读
                  </div>
                  <p className="text-xs sm:text-[12.5px] text-[#4A5A52] leading-relaxed m-0 font-normal">
                    {item.actual}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── 05 推荐经历 ── */}
        <div className="mb-9">
          <SectionHeaderImageStyle
            num="05"
            title="推荐经历"
            subtitle="根据岗位要求精选出的最佳经历素材"
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data.recommended.map((exp) => (
              <div
                key={exp.id}
                className="bg-white rounded-xl border border-[#E2E6E2] hover:border-[#1E4D3C] p-5 shadow-2xs flex flex-col justify-between space-y-3 transition"
              >
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-[11px] font-medium text-[#737873] bg-[#F2F4F1] px-2 py-0.5 rounded">
                      {exp.type} · {exp.year}
                    </span>
                    <span className="text-xs font-bold text-[#1E4D3C] bg-[#E4ECE7] px-2 py-0.5 rounded">
                      {exp.matchScore}% 匹配
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-[#111814] mb-2">
                    {exp.title}
                  </h3>

                  <div className="flex flex-wrap gap-1.5 mb-2.5">
                    {exp.tags.map((t) => (
                      <span
                        key={t}
                        className="text-[11px] px-2 py-0.5 bg-[#F2F4F1] text-[#526058] rounded font-normal"
                      >
                        {t}
                      </span>
                    ))}
                  </div>

                  <p className="text-xs text-[#737873] leading-relaxed m-0">
                    {exp.reason}
                  </p>
                </div>

                <div className="flex gap-2 pt-2 border-t border-[#F0F2EE]">
                  <button
                    type="button"
                    onClick={() => navigateTo('experiences', { initialExpId: exp.id })}
                    className="flex-1 py-1.5 text-xs font-bold text-[#1E4D3C] border border-[#CCD8D1] rounded-lg bg-[#FAFBF9] hover:bg-[#1E4D3C] hover:text-white transition cursor-pointer text-center"
                  >
                    查看经历
                  </button>
                  <button
                    type="button"
                    onClick={handleGoToResume}
                    className="flex-1 py-1.5 text-xs font-medium text-[#526058] border border-[#CCD8D1] rounded-lg bg-white hover:bg-[#F2F4F1] transition cursor-pointer text-center"
                  >
                    用于简历
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── 底部行动指引 (Next Step Action) ── */}
        {jdAnalysisReturnTarget ? (
          <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-5 flex flex-col sm:flex-row justify-between items-center gap-4 shadow-2xs">
            <div>
              <div className="text-sm font-bold text-[#111814] mb-0.5">
                {jdAnalysisReturnTarget === 'create_interview'
                  ? '返回新建面试并使用此岗位'
                  : '返回新建复盘并使用此岗位'}
              </div>
              <p className="text-xs text-[#737873] m-0">
                {jdAnalysisReturnTarget === 'create_interview'
                  ? '已完成 JD 研判，AI 将自动带入此岗位的考点分析生成面试准备。'
                  : '已完成 JD 研判，AI 将自动关联此岗位数据进行面试复盘。'}
              </p>
            </div>
            <button
              type="button"
              onClick={handleReturnToWizard}
              className="flex items-center gap-1.5 px-5 py-2 bg-[#1E4D3C] hover:bg-[#16382D] text-white rounded-lg text-xs font-bold shadow-2xs transition shrink-0 cursor-pointer"
            >
              <span>返回继续</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="bg-[#FAFBF9] border border-[#E2E6E2] rounded-xl p-5 flex flex-col sm:flex-row justify-between items-center gap-4 shadow-2xs">
            <div>
              <div className="text-sm font-bold text-[#111814] mb-0.5">
                下一步建议：针对 JD 要求定制专属简历
              </div>
              <p className="text-xs text-[#737873] m-0">
                当前岗位综合匹配度高达 92%，重点在简历中突出 AI 搜索与 0 到 1 评测经验。
              </p>
            </div>
            <button
              type="button"
              onClick={handleGoToResume}
              className="flex items-center gap-1.5 px-5 py-2 bg-[#1E4D3C] hover:bg-[#16382D] text-white rounded-lg text-xs font-bold shadow-2xs transition shrink-0 cursor-pointer"
            >
              <span>立即去定制简历</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

      </div>
    </div>
  );
};

