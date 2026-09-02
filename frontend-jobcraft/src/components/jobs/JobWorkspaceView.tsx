import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  Briefcase,
  ArrowLeft,
  FileSearch,
  FileText,
  BookOpenCheck,
  RotateCcw,
  Sparkles,
  Plus,
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink
} from 'lucide-react';
import { JDReportDetailView } from '../jd/JDReportDetailView';
import { ResumeEditorView } from '../resume/ResumeEditorView';

interface JobWorkspaceViewProps {
  onOpenMockInterview: (interviewId: string) => void;
  onOpenNewInterview: (jobId?: string) => void;
}

export const JobWorkspaceView: React.FC<JobWorkspaceViewProps> = ({
  onOpenMockInterview,
  onOpenNewInterview
}) => {
  const {
    selectedJobId,
    jobs,
    interviews,
    jdAnalyses,
    navigateTo,
    jobWorkspaceSubTab
  } = useJobCraft();

  const [activeTab, setActiveTab] = useState<'jd' | 'resume' | 'interview'>(jobWorkspaceSubTab || 'jd');

  const currentJob = jobs.find((j) => j.id === selectedJobId) || jobs[0];
  const jobInterviews = interviews.filter((i) => i.jobId === currentJob?.id);
  const currentJD = jdAnalyses.find((a) => a.id === currentJob?.jdAnalysisId || a.jobId === currentJob?.id);

  if (!currentJob) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-muted">未找到岗位信息</p>
        <button
          onClick={() => navigateTo('jobs')}
          className="mt-2 px-4 py-1.5 bg-sage hover:bg-sage-dim text-white rounded-lg text-xs font-semibold transition cursor-pointer"
        >
          返回岗位列表
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* 1. Job Context Container Header (Section 8.1) */}
      <div className="bg-white border-b border-slate-200 px-8 py-5 shadow-2xs">
        <div className="max-w-7xl mx-auto space-y-4">
          {/* Breadcrumb Back */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigateTo('jobs')}
              className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-sage font-medium transition cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>返回我的岗位列表</span>
            </button>

            <div className="flex items-center gap-2">
              <span className="text-xs text-faint">投递时间: {currentJob.applyDate}</span>
              <span className="text-edge-deep">·</span>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                  currentJob.status === 'interviewing'
                    ? 'bg-sage-soft text-sage border border-sage/20'
                    : currentJob.status === 'delivered'
                    ? 'bg-info-bg text-info border border-info/20'
                    : currentJob.status === 'finished'
                    ? 'bg-error-bg text-error border border-error/20'
                    : 'bg-warning-bg text-warning border border-warning/20'
                }`}
              >
                {currentJob.status === 'interviewing'
                  ? '面试推进中'
                  : currentJob.status === 'delivered'
                  ? '已投递'
                  : currentJob.status === 'finished'
                  ? '已结束'
                  : '待处理'}
              </span>
            </div>
          </div>

          {/* Job Identity */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold text-ink tracking-tight">
                  {currentJob.company} · {currentJob.role}
                </h1>
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-md bg-sage-soft text-sage border border-sage-soft">
                  综合匹配度 {currentJob.matchScore}%
                </span>
              </div>
              <p className="text-xs text-muted mt-1 flex items-center gap-2">
                <span>{currentJob.department}</span>
                <span>·</span>
                <span className="font-medium text-ink">{currentJob.salaryRange}</span>
                <span>·</span>
                <span className="text-muted">当前阶段：{currentJob.currentStage}</span>
              </p>
            </div>

            {/* Header Action Buttons */}
            <div className="flex items-center gap-2.5 shrink-0">
              <button
                onClick={() => onOpenMockInterview(jobInterviews[0]?.id || 'int-byte-2')}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sage-soft hover:bg-edge-deep text-sage border border-sage-soft text-xs font-semibold transition"
              >
                <Sparkles className="w-3.5 h-3.5 text-sage" />
                <span>进入模拟面试</span>
              </button>

              <button
                onClick={() => onOpenNewInterview(currentJob?.id)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>新建面试</span>
              </button>
            </div>
          </div>

          {/* 2. Top Sub-Tabs Navigation (Section 8.2: JD分析 | 定制简历 | 面试) */}
          <div className="flex items-center gap-2 pt-2 border-t border-edge">
            <button
              onClick={() => setActiveTab('jd')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === 'jd'
                  ? 'bg-ink text-white shadow-xs'
                  : 'text-muted hover:bg-page'
              }`}
            >
              <FileSearch className="w-4 h-4" />
              <span>JD 深度分析</span>
              {currentJD && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-sage text-white">
                  {currentJD.matchScore}% 匹配
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('resume')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === 'resume'
                  ? 'bg-ink text-white shadow-xs'
                  : 'text-muted hover:bg-page'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>定制简历</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-sage-soft text-sage">
                证据驱动
              </span>
            </button>

            <button
              onClick={() => setActiveTab('interview')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === 'interview'
                  ? 'bg-ink text-white shadow-xs'
                  : 'text-muted hover:bg-page'
              }`}
            >
              <BookOpenCheck className="w-4 h-4" />
              <span>面试中心 ({jobInterviews.length} 轮)</span>
            </button>
          </div>
        </div>
      </div>

      {/* 3. Sub-Tab Dynamic Viewport */}
      <div className="flex-1">
        {activeTab === 'jd' && (
          <div className="animate-in fade-in duration-200">
            <JDReportDetailView
              analysisId={currentJob.jdAnalysisId || 'jd-byte-1'}
              onNavigateToResume={() => setActiveTab('resume')}
              onNavigateToInterview={() => setActiveTab('interview')}
              embedded={true}
            />
          </div>
        )}

        {activeTab === 'resume' && (
          <div className="animate-in fade-in duration-200">
            <ResumeEditorView
              resumeId={currentJob.resumeId || 'res-byte-1'}
              jobId={currentJob.id}
              embedded={true}
            />
          </div>
        )}

        {activeTab === 'interview' && (
          <div className="max-w-7xl mx-auto p-8 space-y-6 animate-in fade-in duration-200">
            {/* Interview Center Header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-ink">
                  {currentJob.company} · 多轮面试推进
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  每轮面试拥有专属的考点预判、高频题库、公司研判以及赛后复盘沉淀
                </p>
              </div>
              <button
                onClick={() => onOpenNewInterview(currentJob?.id)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-sage text-white text-xs font-semibold hover:bg-sage-dim transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>+ 新建面试轮次</span>
              </button>
            </div>

            {/* Rounds List (Section 12) */}
            <div className="space-y-4">
              {jobInterviews.map((interview) => {
                const isUpcoming = interview.status === 'upcoming';
                const isCompleted = interview.status === 'completed';

                return (
                  <div
                    key={interview.id}
                    className={`bg-white rounded-xl border p-6 shadow-2xs transition ${
                      isUpcoming
                        ? 'border-warning/40 ring-1 ring-warning/20'
                        : 'border-edge'
                    }`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      {/* Left: Info */}
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-3">
                          <span className="text-base font-bold text-ink">
                            {interview.roundName}
                          </span>
                          <span
                            className={`text-xs px-2.5 py-0.5 rounded-md font-semibold border ${
                              isUpcoming
                                ? 'bg-warning-bg text-warning border-warning/20'
                                : isCompleted
                                ? 'bg-page text-muted border-edge'
                                : 'bg-info-bg text-info border-info/20'
                            }`}
                          >
                            {isUpcoming ? '即将进行' : isCompleted ? '已完成' : '准备中'}
                          </span>
                          <span className="text-xs text-faint font-medium">
                            时间：{interview.time}
                          </span>
                        </div>

                        <div className="text-xs text-muted flex items-center gap-3 flex-wrap">
                          <span>形式：{interview.format === 'video' ? '视频面试' : interview.format === 'phone' ? '电话面试' : '现场面试'}</span>
                          {interview.interviewer && (
                            <>
                              <span>·</span>
                              <span>面试官：{interview.interviewer}</span>
                            </>
                          )}
                          <span>·</span>
                          <span className="font-semibold text-sage">
                            准备度 {interview.readinessPercent}%
                          </span>
                        </div>

                        {interview.supplementNotes && (
                          <p className="text-xs text-muted bg-page p-2 rounded-lg border border-edge mt-2">
                            <strong className="text-ink font-semibold">HR/背景提醒：</strong> {interview.supplementNotes}
                          </p>
                        )}
                      </div>

                      {/* Right: Actions */}
                      <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
                        {isCompleted && interview.review && (
                          <button
                            onClick={() =>
                              navigateTo('interview_review_detail', {
                                jobId: currentJob.id,
                                interviewId: interview.id
                              })
                            }
                            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white hover:bg-page text-ink text-xs font-semibold border border-edge transition cursor-pointer"
                          >
                            <RotateCcw className="w-3.5 h-3.5 text-sage" />
                            <span>查看复盘报告 ({interview.review.overallScore}分)</span>
                          </button>
                        )}

                        <button
                          onClick={() =>
                            navigateTo('interview_prep_workspace', {
                              jobId: currentJob.id,
                              interviewId: interview.id
                            })
                          }
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
                        >
                          <BookOpenCheck className="w-3.5 h-3.5" />
                          <span>{isCompleted ? '查看准备方案' : '进入准备空间'}</span>
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}

              {jobInterviews.length === 0 && (
                <div className="p-8 text-center bg-white rounded-xl border border-dashed border-edge">
                  <p className="text-sm text-muted">本岗位暂未安排面试轮次</p>
                  <button
                    onClick={() => onOpenNewInterview(currentJob?.id)}
                    className="mt-3 px-4 py-2 bg-sage hover:bg-sage-dim text-white text-xs font-semibold rounded-lg cursor-pointer"
                  >
                    + 新建第1面准备
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
