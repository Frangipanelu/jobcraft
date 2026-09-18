import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import { useInterviewsQuery } from '../../features/interview/hooks';
import { useApplyReviewFeedbackMutation } from '../../features/review/hooks';
import { useTabNavigate } from '../../router/tabPaths';
import {
  ArrowLeft,
  Star,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  Quote,
  Lightbulb,
  TrendingUp,
  FileText
} from 'lucide-react';
import { InterviewQA } from '../../types/jobcraft';

interface InterviewReviewDetailViewProps {
  interviewId?: string;
}

export const InterviewReviewDetailView: React.FC<InterviewReviewDetailViewProps> = ({
  interviewId
}) => {
  const { showToast, syncInterviews, syncExperiences } = useJobCraft();
  const { data: interviews = [] } = useInterviewsQuery();
  const applyFeedbackMutation = useApplyReviewFeedbackMutation({
    onSync: syncInterviews,
    onSyncExperiences: syncExperiences
  });
  const go = useTabNavigate();

  const currentInterview = interviews.find((i) => i.id === interviewId);
  const review = currentInterview?.review;

  const [selectedQAIndex, setSelectedQAIndex] = useState<number>(0);

  if (!currentInterview || !review) {
    return (
      <div className="max-w-4xl mx-auto p-12 text-center space-y-4">
        <div className="text-base text-muted">暂无本场面试的复盘报告</div>
        <button
          onClick={() => go('interview_review_center')}
          className="px-4 py-2 rounded-lg bg-sage text-white text-xs font-semibold cursor-pointer"
        >
          返回复盘中心
        </button>
      </div>
    );
  }

  const qaList: InterviewQA[] = review.qaList && review.qaList.length > 0 ? review.qaList : [];
  const selectedQA: InterviewQA | undefined = qaList[selectedQAIndex] || qaList[0];

  const handleApplyFeedback = async (feedbackIndex: number) => {
    try {
      await applyFeedbackMutation.mutateAsync({
        interviewId: currentInterview.id,
        feedbackIndex
      });
      showToast({
        type: 'success',
        title: '经历资产已升级',
        message: '已将本次面试复盘的建议沉淀至经历资产库最新版本！'
      });
    } catch (e) {
      showToast({
        type: 'error',
        title: '沉淀失败',
        message: (e as Error).message || '请稍后重试'
      });
    }
  };

  // Helper for score badge color
  const getScoreBadgeClass = (score: number) => {
    if (score >= 80) return 'text-sage bg-sage-soft border-sage/20';
    if (score >= 70) return 'text-ink bg-page border-edge';
    return 'text-warning bg-warning-bg border-warning/20';
  };

  // 仅渲染真实评估数据，缺失时展示空值而非伪造打分
  const metricCards = selectedQA?.metricCards ?? ({} as NonNullable<InterviewQA['metricCards']>);

  // Intent items fallback
  const interviewerIntent = selectedQA?.interviewerIntent;
  const intentStars = [interviewerIntent?.importanceStars, interviewerIntent?.productAbilityStars, interviewerIntent?.techDepthStars] as const;
  const intentItems = (interviewerIntent?.mainPoints || []).map((point, idx) => ({
    title: `考察点 ${idx + 1}`,
    stars: intentStars[idx] ?? 0,
    desc: point
  }));

  // Analysis progress bars
  const answerAnalysis = selectedQA?.answerAnalysis;
  const analysisBars = answerAnalysis
    ? [
        { label: '结构清晰度', score: answerAnalysis.structure ?? answerAnalysis.clarity ?? 0 },
        { label: '量化 Impact', score: answerAnalysis.impact ?? answerAnalysis.persuasiveness ?? 0 },
        { label: '关键决策', score: answerAnalysis.decision ?? answerAnalysis.completeness ?? 0 },
        { label: '语言流畅度', score: answerAnalysis.fluency ?? answerAnalysis.jobRelevance ?? 0 }
      ]
    : [];

  // Find if current QA has related feedback
  const relatedFeedback = review.experienceFeedbacks?.find(
    (fb) => fb.experienceId === selectedQA?.relatedExperienceId
  );
  const feedbackIndex = review.experienceFeedbacks?.findIndex(
    (fb) => fb.experienceId === selectedQA?.relatedExperienceId
  );

  return (
    <div className="min-h-full bg-page p-4 md:p-6 lg:p-7 space-y-4 max-w-[1440px] mx-auto animate-in fade-in duration-300 text-ink">
      {/* 1. Header Section */}
      <div className="bg-white rounded-2xl border border-edge p-5 shadow-xs flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        {/* Left Info */}
        <div className="space-y-2">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-ink">
              {review.company} · {review.role}
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-edge text-muted">
              {review.roundName}
            </span>
          </div>

          <div className="text-xs text-faint">
            {review.reviewDate} · 识别 {qaList.length} 组 QA
          </div>
        </div>

        {/* Right Top Score Banner */}
        <div className="flex items-center gap-6 bg-canvas rounded-xl border border-edge px-5 py-3 shrink-0">
          {/* Big Number */}
          <div className="text-center pr-6 border-r border-edge">
            <div className="text-4xl font-extrabold text-ink tracking-tight leading-none">
              {review.overallScore}
            </div>
            <div className="text-[11px] text-faint font-medium mt-1">综合评分</div>
          </div>

          {/* 4 Dimension Progress Bars */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs min-w-[240px]">
            {(review.competencies || []).map((comp, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="text-[11px] text-muted font-medium w-14 shrink-0">{comp.name}</span>
                <div className="flex-1 h-1.5 bg-edge rounded-full overflow-hidden w-16">
                  <div
                    className="h-full bg-ink rounded-full transition-all duration-500"
                    style={{ width: `${comp.score}%` }}
                  />
                </div>
                <span className="text-[11px] font-bold text-ink w-5 text-right">{comp.score}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Core Problems Alert Banner (本场核心问题) */}
      {review.coreProblems && review.coreProblems.length > 0 && (
        <div className="bg-warning-bg border border-warning/20 rounded-xl px-4 py-3 flex flex-col md:flex-row md:items-center gap-3 text-xs shadow-2xs">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="font-bold text-warning bg-warning-bg px-2.5 py-0.5 rounded-md text-[11px] border border-warning/20">
              本场核心问题
            </span>
          </div>
          <div className="text-muted leading-relaxed flex-1 flex flex-col lg:flex-row lg:items-center gap-2 lg:gap-4">
            {review.coreProblems.map((prob, idx) => (
              <span key={idx} className="inline-block">
                {prob}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 3. Three-Column Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left Column: QA Question List (3 Cols) */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-edge p-3 shadow-xs space-y-2">
          <div className="px-2 py-1 flex items-center justify-between text-xs font-bold text-muted border-b border-edge pb-2">
            <span>QA 题目清单 ({qaList.length})</span>
            <span className="text-[10px] font-normal text-faint">点击切换查看详情</span>
          </div>

          <div className="space-y-1.5 max-h-[700px] overflow-y-auto custom-scrollbar pr-1">
            {qaList.map((qa, index) => {
              const isSelected = index === selectedQAIndex;
              const qScore = qa.score || qa.answerAnalysis?.completeness || 0;

              return (
                <button
                  key={qa.id || index}
                  onClick={() => setSelectedQAIndex(index)}
                  className={`w-full text-left p-3 rounded-xl transition-all cursor-pointer border ${
                    isSelected
                      ? 'bg-canvas border-sage shadow-xs'
                      : 'bg-white hover:bg-canvas border-edge'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={`text-xs font-bold shrink-0 mt-0.5 ${
                        isSelected ? 'text-sage' : 'text-faint'
                      }`}
                    >
                      Q{qa.qIndex || index + 1}
                    </span>
                    <p
                      className={`text-xs font-medium leading-snug line-clamp-2 ${
                        isSelected ? 'text-ink font-semibold' : 'text-ink'
                      }`}
                    >
                      {qa.question}
                    </p>
                  </div>

                  <div className="flex items-center justify-between mt-2.5 pt-1.5 border-t border-edge/60 text-[11px]">
                    <span className="text-faint font-mono">{qa.duration || '—'}</span>
                    <span
                      className={`px-2 py-0.2 rounded-md font-bold text-[10px] border ${getScoreBadgeClass(
                        qScore
                      )}`}
                    >
                      {qScore === 0 ? '—' : qScore}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Middle Column: Main Question & Answer Detail (6 Cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white rounded-2xl border border-edge p-5 shadow-xs space-y-5">
            {/* Header: Question & Time */}
            <div className="flex items-start justify-between gap-4 border-b border-edge pb-3.5">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-md bg-sage text-white font-bold text-xs">
                    Q{selectedQA?.qIndex || selectedQAIndex + 1}
                  </span>
                  <h2 className="text-base md:text-lg font-bold text-ink leading-snug">
                    {selectedQA?.question}
                  </h2>
                </div>
              </div>
              <span className="text-xs font-mono text-faint shrink-0 mt-1 bg-page px-2 py-1 rounded-md">
                时长 {selectedQA?.duration || '—'}
              </span>
            </div>

            {/* Transcript / Answer Record (回答记录) */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-muted">
                <Quote className="w-3.5 h-3.5 text-sage" />
                <span>回答记录</span>
              </div>
              <div className="p-4 rounded-xl bg-canvas border border-edge text-xs text-ink leading-relaxed whitespace-pre-line font-normal">
                {selectedQA?.transcript || selectedQA?.candidateAnswer}
              </div>
            </div>

            {/* 4 Dimension Cards (2x2 Grid) */}
            <div className="space-y-2">
              <div className="text-xs font-bold text-muted">回答质量维度诊断</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* 1. 结构清晰度 */}
                <div className="p-3.5 rounded-xl bg-canvas border border-edge space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted">结构清晰度</span>
                    <span className="text-lg font-extrabold text-ink">
                      {metricCards.clarityScore ?? '—'}
                    </span>
                  </div>
                  <p className="text-[11px] text-ink leading-relaxed">{metricCards.clarityDesc || '暂无该维度评估数据'}</p>
                </div>

                {/* 2. 量化 Impact */}
                <div className="p-3.5 rounded-xl bg-canvas border border-edge space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted">量化 Impact</span>
                    <span className="text-lg font-extrabold text-ink">
                      {metricCards.impactScore ?? '—'}
                    </span>
                  </div>
                  <p className="text-[11px] text-ink leading-relaxed">{metricCards.impactDesc || '暂无该维度评估数据'}</p>
                </div>

                {/* 3. 关键决策 */}
                <div className="p-3.5 rounded-xl bg-canvas border border-edge space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted">关键决策</span>
                    <span className="text-lg font-extrabold text-ink">
                      {metricCards.decisionScore ?? '—'}
                    </span>
                  </div>
                  <p className="text-[11px] text-ink leading-relaxed">{metricCards.decisionDesc || '暂无该维度评估数据'}</p>
                </div>

                {/* 4. 语言流畅度 */}
                <div className="p-3.5 rounded-xl bg-canvas border border-edge space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted">语言流畅度</span>
                    <span className="text-lg font-extrabold text-ink">
                      {metricCards.fluencyScore ?? '—'}
                    </span>
                  </div>
                  <p className="text-[11px] text-ink leading-relaxed">{metricCards.fluencyDesc || '暂无该维度评估数据'}</p>
                </div>
              </div>
            </div>

            {/* AI Advice & Next Step */}
            <div className="p-4 rounded-xl bg-sage-soft/30 border border-sage-soft space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-sage">
                <Lightbulb className="w-4 h-4 text-sage" />
                <span>下一轮优化建议与话术示范</span>
              </div>
              <p className="text-xs text-sage leading-relaxed">
{selectedQA?.suggestionAdvice ||
                    '暂无建议数据，可完成本题 AI 复盘后生成优化建议。'}
              </p>
            </div>
          </div>

          {/* Experience Sync / Feedback Box if available */}
          {relatedFeedback && (
            <div className="bg-white rounded-2xl border border-edge p-4 shadow-xs flex items-center justify-between gap-4">
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 text-xs font-bold text-ink">
                  <Database className="w-3.5 h-3.5 text-sage" />
                  <span>已关联经历资产：{relatedFeedback.experienceTitle}</span>
                </div>
                <div className="text-[11px] text-muted">
                  建议版本升级：{relatedFeedback.currentVersion} →{' '}
                  <strong className="text-sage">{relatedFeedback.proposedVersion}</strong>（沉淀本题反思与量化数据）
                </div>
              </div>

              {relatedFeedback.applied ? (
                <span className="flex items-center gap-1 text-sage font-bold text-xs bg-sage-soft px-3 py-1.5 rounded-lg border border-sage-soft shrink-0">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>已同步</span>
                </span>
              ) : (
                <button
                  onClick={() => feedbackIndex !== undefined && feedbackIndex >= 0 && handleApplyFeedback(feedbackIndex)}
                  disabled={applyFeedbackMutation.isPending}
                  className="flex items-center gap-1 px-3.5 py-1.5 bg-sage hover:bg-sage-dim text-white text-xs font-bold rounded-lg transition shadow-xs cursor-pointer shrink-0 disabled:opacity-60"
                >
                  <span>沉淀至经历库</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Analysis Panel (3 Cols) */}
        <div className="lg:col-span-3 space-y-4">
          {/* Card 1: 面试官意图 (Interviewer Intent) */}
          <div className="bg-white rounded-2xl border border-edge p-4 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between border-b border-edge pb-2.5">
              <h3 className="text-xs font-bold text-ink">面试官意图</h3>
              <span className="text-[10px] text-faint">深层考量分析</span>
            </div>

            <div className="space-y-3">
              {intentItems.length > 0 ? (
                intentItems.map((item, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-ink">{item.title}</span>
                      <div className="flex items-center gap-0.5">
                        {[1, 2, 3, 4, 5].map((starVal) => (
                          <Star
                            key={starVal}
                            className={`w-3 h-3 ${
                              starVal <= item.stars
                                ? 'fill-terra text-terra'
                                : 'fill-transparent text-edge-deep'
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                    <p className="text-[11px] text-muted leading-snug">{item.desc}</p>
                  </div>
                ))
              ) : (
                <p className="text-[11px] text-muted">暂无面试官意图分析，可完成本题 AI 复盘后查看。</p>
              )}
            </div>
          </div>

          {/* Card 2: 回答分析 (Answer Analysis) */}
          <div className="bg-white rounded-2xl border border-edge p-4 shadow-xs space-y-3.5">
            <div className="flex items-center justify-between border-b border-edge pb-2.5">
              <h3 className="text-xs font-bold text-ink">回答分析</h3>
              <span className="text-[10px] text-faint">四维量化得分</span>
            </div>

            <div className="space-y-2.5">
              {analysisBars.length > 0 ? (
                analysisBars.map((bar, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted font-medium">{bar.label}</span>
                      <span className="font-bold text-ink">{bar.score}</span>
                    </div>
                    <div className="h-1.5 bg-edge rounded-full overflow-hidden">
                      <div
                        className="h-full bg-ink rounded-full transition-all duration-500"
                        style={{ width: `${bar.score}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-[11px] text-muted">暂无四维分析数据，可完成本题 AI 复盘后查看。</p>
              )}
            </div>
          </div>

          {/* Card 3: 诊断与行动总结 (Action summary) */}
          <div className="bg-warning-bg rounded-2xl border border-warning/20 p-4 shadow-2xs space-y-2 text-xs">
            <div className="flex items-center gap-1.5 font-bold text-warning">
              <AlertTriangle className="w-3.5 h-3.5 text-warning" />
              <span>本题失分防范</span>
            </div>
            <ul className="space-y-1 text-muted text-[11px] list-disc list-inside">
              {(selectedQA?.identifiedIssues && selectedQA.identifiedIssues.length > 0
                ? selectedQA.identifiedIssues
                : ['暂无命中失分点']
              ).map(
                (issue, iIdx) => (
                  <li key={iIdx}>{issue}</li>
                )
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
