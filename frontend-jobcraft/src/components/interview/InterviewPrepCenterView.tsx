import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  BookOpenCheck,
  Plus,
  ArrowRight,
  Clock,
  CheckCircle2,
  Calendar,
  Sparkles,
  Search,
  Building2,
  User,
  Play,
  Layers,
  ChevronRight
} from 'lucide-react';

interface InterviewPrepCenterViewProps {
  onOpenMockInterview: (interviewId: string) => void;
  onOpenNewInterview: () => void;
}

export const InterviewPrepCenterView: React.FC<InterviewPrepCenterViewProps> = ({
  onOpenMockInterview,
  onOpenNewInterview
}) => {
  const { interviews, navigateTo } = useJobCraft();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'upcoming' | 'completed'>('all');

  const upcomingInterviews = interviews.filter((i) => i.status === 'upcoming' || i.status === 'preparing');
  const completedInterviews = interviews.filter((i) => i.status === 'completed');

  const filteredInterviews = interviews.filter((i) => {
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'upcoming' && (i.status === 'upcoming' || i.status === 'preparing')) ||
      (statusFilter === 'completed' && i.status === 'completed');
    const matchesSearch =
      i.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      i.roundName.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-edge pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-ink tracking-tight">面试准备中心</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sage-soft text-sage border border-sage-soft">
              {upcomingInterviews.length} 场待备战
            </span>
          </div>
          <p className="text-xs md:text-sm text-muted mt-1">
            将目标企业、岗位考核诉求与候选人经历资产库对齐，制定结构化攻防问答策略与模拟演练
          </p>
        </div>

        <button
          onClick={onOpenNewInterview}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-bold shadow-xs transition shrink-0 cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>新建面试</span>
        </button>
      </div>

      {/* Structured Registry Table (替代碎卡片，呈现清晰的日程与备考档案表) */}
      <div className="bg-white rounded-xl border border-edge overflow-hidden shadow-2xs space-y-3">
        {/* Filter bar */}
        <div className="p-3.5 bg-page border-b border-edge flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition shrink-0 ${
                statusFilter === 'all'
                  ? 'bg-ink text-white'
                  : 'text-muted hover:bg-edge'
              }`}
            >
              全部面试 ({interviews.length})
            </button>
            <button
              onClick={() => setStatusFilter('upcoming')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition shrink-0 ${
                statusFilter === 'upcoming'
                  ? 'bg-ink text-white'
                  : 'text-muted hover:bg-edge'
              }`}
            >
              待备战 / 推进中 ({upcomingInterviews.length})
            </button>
            <button
              onClick={() => setStatusFilter('completed')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition shrink-0 ${
                statusFilter === 'completed'
                  ? 'bg-ink text-white'
                  : 'text-muted hover:bg-edge'
              }`}
            >
              已完成 ({completedInterviews.length})
            </button>
          </div>

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

        {/* Structured Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-edge text-muted font-semibold bg-canvas">
                <th className="p-3.5 w-60">目标公司与轮次</th>
                <th className="p-3.5 w-44">面试时间与形式</th>
                <th className="p-3.5 w-40">面试官画像</th>
                <th className="p-3.5 w-32">备战准备度</th>
                <th className="p-3.5">高频问题与攻防策略</th>
                <th className="p-3.5 w-48 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-edge">
              {filteredInterviews.map((interview) => {
                const prep = interview.preparation;
                const highFreqCount = prep?.highFreqQuestions?.length || 0;
                const preparedCount = prep?.highFreqQuestions?.filter((q) => q.isPrepared).length || 0;
                const isUpcoming = interview.status === 'upcoming' || interview.status === 'preparing';

                return (
                  <tr key={interview.id} className="hover:bg-page/40 transition">
                    {/* Company & Role */}
                    <td className="p-3.5 align-top font-bold text-ink">
                      <div className="text-sm font-bold text-ink">{interview.company}</div>
                      <div className="text-xs text-muted font-medium mt-0.5">{interview.role}</div>
                      <div className="text-[11px] text-sage font-semibold mt-1">
                        {interview.roundName}
                      </div>
                    </td>

                    {/* Time & Format */}
                    <td className="p-3.5 align-top text-ink">
                      <div className="flex items-center gap-1.5 font-medium">
                        <Calendar className="w-3.5 h-3.5 text-faint" />
                        <span>{interview.time}</span>
                      </div>
                      <div className="text-[11px] text-faint mt-1">
                        {interview.format === 'video' ? '视频面试 (腾讯会议/飞书)' : '电话 / 现场'}
                      </div>
                    </td>

                    {/* Interviewer Profile */}
                    <td className="p-3.5 align-top text-ink">
                      <div className="font-semibold text-ink">
                        {interview.interviewer || '业务负责人 / 专家'}
                      </div>
                      <div className="text-[11px] text-faint mt-0.5">
                        {interview.supplementNotes ? interview.supplementNotes.slice(0, 20) + '...' : '考察业务攻坚与架构'}
                      </div>
                    </td>

                    {/* Readiness */}
                    <td className="p-3.5 align-top">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-xs font-bold bg-sage-soft text-sage border border-sage-soft">
                          {interview.readinessPercent}%
                        </span>
                      </div>
                      <div className="text-[10px] text-faint mt-1">
                        已攻克 {preparedCount}/{highFreqCount} 题
                      </div>
                    </td>

                    {/* High-frequency Strategy Summary */}
                    <td className="p-3.5 align-top text-muted leading-relaxed">
                      <div className="font-medium text-ink line-clamp-1">
                        重点聚焦：{prep?.companyResearch?.aiHiringIntent?.slice(0, 30) || '核心业务痛点与技术落地'}
                      </div>
                      <div className="text-[11px] text-faint mt-0.5 line-clamp-1">
                        主打经历：{prep?.recommendedExperiences?.[0]?.proves?.join(' · ') || '端侧 AI 评测管线'}
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="p-3.5 align-top text-right space-y-1.5">
                      <div className="flex items-center justify-end gap-1.5">
                        {isUpcoming && (
                          <button
                            onClick={() => onOpenMockInterview(interview.id)}
                            className="px-2.5 py-1 rounded bg-sage-soft hover:bg-edge-deep text-sage text-xs font-bold border border-sage-soft transition flex items-center gap-1 cursor-pointer"
                            title="进入实时 AI 模拟面试"
                          >
                            <Play className="w-3 h-3 text-sage" />
                            <span>模拟面试</span>
                          </button>
                        )}
                        <button
                          onClick={() =>
                            navigateTo('interview_prep_workspace', {
                              jobId: interview.jobId,
                              interviewId: interview.id
                            })
                          }
                          className="px-3 py-1 rounded bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition cursor-pointer"
                        >
                          进入备战
                        </button>
                      </div>

                      {interview.review && (
                        <div className="text-right">
                          <button
                            onClick={() =>
                              navigateTo('interview_review', {
                                interviewId: interview.id
                              })
                            }
                            className="text-[11px] text-warning hover:underline font-semibold"
                          >
                            查看复盘报告 →
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}

              {filteredInterviews.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-xs text-faint">
                    未找到符合条件的面试记录
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
