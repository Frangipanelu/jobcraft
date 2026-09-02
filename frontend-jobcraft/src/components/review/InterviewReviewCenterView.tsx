import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  RotateCcw,
  Plus,
  ArrowRight,
  TrendingUp,
  Award,
  Sparkles,
  Calendar,
  CheckCircle2,
  Search,
  ArrowLeft,
  FileCheck2
} from 'lucide-react';

interface InterviewReviewCenterViewProps {}

export const InterviewReviewCenterView: React.FC<InterviewReviewCenterViewProps> = () => {
  const { interviews, navigateTo } = useJobCraft();
  const [searchQuery, setSearchQuery] = useState('');

  const interviewsWithReviews = interviews.filter((i) => !!i.review);
  const interviewsWithoutReviews = interviews.filter((i) => !i.review);

  const filteredReviewed = interviewsWithReviews.filter(
    (i) =>
      i.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.roundName.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-edge pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-ink tracking-tight">面试复盘中心</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sage-soft text-sage border border-sage-soft">
              已沉淀 {interviewsWithReviews.length} 场复盘
            </span>
          </div>
          <p className="text-xs md:text-sm text-muted mt-1">
            把每一次真实面试经历转化为能力沉淀，逐题诊断得失并将亮点反哺回经历资产库
          </p>
        </div>

        <button
          onClick={() => navigateTo('create_review')}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-bold shadow-xs transition shrink-0 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>新建复盘</span>
        </button>
      </div>

      {/* Metrics Summary Strip */}
      <div className="bg-white rounded-xl border border-edge p-4 shadow-2xs grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-edge">
        <div className="p-2 sm:px-4 space-y-1">
          <div className="text-[11px] font-semibold text-muted uppercase">已完成逐题复盘</div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-ink">{interviewsWithReviews.length} 场</span>
            <span className="text-xs text-sage font-semibold">100% 反哺率</span>
          </div>
        </div>

        <div className="p-2 sm:px-4 space-y-1">
          <div className="text-[11px] font-semibold text-muted uppercase">平均得分</div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-sage">85.0 分</span>
            <span className="text-xs text-muted">最高 88 分 (字节业务面)</span>
          </div>
        </div>

        <div className="p-2 sm:px-4 space-y-1">
          <div className="text-[11px] font-semibold text-muted uppercase">待复盘场次</div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-terra">{interviewsWithoutReviews.length} 场</span>
            <span className="text-xs text-terra">建议 24h 内完成</span>
          </div>
        </div>
      </div>

      {/* Structured Review Ledger Table */}
      <div className="bg-white rounded-xl border border-edge overflow-hidden shadow-2xs">
        <div className="p-3.5 bg-page border-b border-edge flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-xs font-bold text-ink">已复盘面试台账</h2>

          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 text-faint absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="搜索公司、岗位或面试轮次..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-edge bg-white text-ink placeholder:text-faint focus:border-sage focus:outline-none"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-edge text-muted font-semibold bg-canvas">
                <th className="p-3.5 w-52">公司与面试轮次</th>
                <th className="p-3.5 w-32">面试时间</th>
                <th className="p-3.5 w-28">综合得分</th>
                <th className="p-3.5 w-40">通过概率与评级</th>
                <th className="p-3.5">核心诊断与反哺亮点</th>
                <th className="p-3.5 w-32 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-edge">
              {filteredReviewed.map((interview) => {
                const currentReview = interview.review!;
                return (
                  <tr key={interview.id} className="hover:bg-page/40 transition">
                    <td className="p-3.5 align-top font-bold text-ink">
                      <div className="text-sm font-bold text-ink">{interview.company}</div>
                      <div className="text-xs text-muted font-medium mt-0.5">{interview.role}</div>
                      <div className="text-[11px] text-sage font-semibold mt-1">
                        {interview.roundName}
                      </div>
                    </td>

                    <td className="p-3.5 align-top text-muted">
                      <div className="flex items-center gap-1 font-medium text-ink">
                        <Calendar className="w-3.5 h-3.5 text-faint" />
                        <span>{interview.time}</span>
                      </div>
                      <div className="text-[11px] text-faint mt-0.5">
                        {interview.format === 'video' ? '视频面试' : '现场面试'}
                      </div>
                    </td>

                    <td className="p-3.5 align-top">
                      <div className="text-base font-bold text-sage">
                        {currentReview.overallScore} <span className="text-xs text-faint font-normal">/ 100</span>
                      </div>
                    </td>

                    <td className="p-3.5 align-top">
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-sage-soft text-sage border border-sage-soft inline-block">
                        {currentReview.passProbability || '高概率通过'}
                      </span>
                    </td>

                    <td className="p-3.5 align-top text-muted leading-relaxed">
                      <div className="font-medium text-ink">
                        诊断：{currentReview.aiDiagnosis?.slice(0, 48) || '对轻量化评测体系阐述清晰，指标具备说服力'}...
                      </div>
                      <div className="text-[11px] text-sage mt-1 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-sage" />
                        <span>已完成经历资产库反哺沉淀</span>
                      </div>
                    </td>

                    <td className="p-3.5 align-top text-right">
                      <button
                        onClick={() =>
                          navigateTo('interview_review_detail', {
                            interviewId: interview.id
                          })
                        }
                        className="px-3 py-1.5 rounded bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition cursor-pointer"
                      >
                        查看详细报告
                      </button>
                    </td>
                  </tr>
                );
              })}

              {filteredReviewed.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-xs text-faint">
                    未找到复盘记录
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
