import React from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import type { Job } from '../../types/jobcraft';
import {
  Plus,
  ChevronRight,
  TrendingUp,
  Sparkles
} from 'lucide-react';

interface WorkbenchViewProps {
  onOpenNewJob: () => void;
}

interface StepItem {
  key: string;
  name: string;
  status: 'done' | 'active' | 'pending';
}

export const WorkbenchView: React.FC<WorkbenchViewProps> = ({
  onOpenNewJob
}) => {
  const {
    user,
    jobs,
    navigateTo
  } = useJobCraft();

  // Metrics derived from real jobs data (dashboard → submissionToJob)
  const deliveredCount = jobs.filter(
    (j) => j.status !== 'pending'
  ).length;
  const interviewingCount = jobs.filter(
    (j) => j.status === 'interviewing'
  ).length;
  const pendingCount = jobs.filter(
    (j) => j.status === 'pending'
  ).length;
  const finishedCount = jobs.filter(
    (j) => j.status === 'finished'
  ).length;

  const activeCount = jobs.filter(
    (j) => j.status !== 'finished'
  ).length;

  // jobs applied within the last 7 days (for the "本周新增" badge)
  const appliedThisWeekCount = jobs.filter((j) => {
    const d = j.applyDate ? new Date(j.applyDate).getTime() : NaN;
    if (Number.isNaN(d)) return false;
    return Date.now() - d < 7 * 24 * 60 * 60 * 1000;
  }).length;

  // Map real Job.steps (dashboard flags) to the 6-step pipeline tracker
  const JOB_STEPS: { key: string; name: string }[] = [
    { key: 'jd', name: 'JD分析' },
    { key: 'match', name: '经历匹配' },
    { key: 'resume', name: '定制简历' },
    { key: 'applied', name: '已投递' },
    { key: 'prep', name: '面试准备' },
    { key: 'review', name: '面试复盘' }
  ];

  const getJobSteps = (job: Job): StepItem[] => {
    const s = job.steps;
    const statusMap: Record<string, 'done' | 'active' | 'pending'> = {
      jd: s.jdAnalysis ? 'done' : 'pending',
      match: s.expMatched ? 'done' : 'pending',
      resume: s.customResume ? 'done' : 'pending',
      applied: s.applied ? 'done' : 'pending',
      prep: s.prepStage === 'done' ? 'done' : 'pending',
      review: s.reviewStage === 'done' ? 'done' : 'pending'
    };
    // Mark the first non-done step as 'active'
    let markedActive = false;
    return JOB_STEPS.map((step) => {
      let status = statusMap[step.key];
      if (status === 'pending' && !markedActive) {
        status = 'active';
        markedActive = true;
      }
      return { key: step.key, name: step.name, status };
    });
  };

  const STATUS_BADGE: Record<Job['status'], { text: string; className: string }> = {
    interviewing: { text: '面试中', className: 'bg-warning-bg text-warning border border-warning/20' },
    delivered: { text: '已投递', className: 'bg-sage-soft text-sage border border-sage/20' },
    finished: { text: '已完成', className: 'bg-page text-muted border border-edge' },
    pending: { text: '待处理', className: 'bg-info-bg text-info border border-info/20' }
  };

  const getStatusBadge = (job: Job) =>
    STATUS_BADGE[job.status] || STATUS_BADGE.pending;

  const NEXT_STEP_TEXT: Record<Job['status'], string> = {
    interviewing: '准备下一轮面试',
    delivered: '等待面试通知',
    pending: '查看 JD 分析结果',
    finished: '复盘已完成'
  };

  const getNextStepText = (job: Job) => NEXT_STEP_TEXT[job.status];

  // "下一步行动": up to 3 jobs still in progress, prioritized by pipeline position
  const nextUpJobs = [...jobs]
    .filter((j) => j.status !== 'finished')
    .sort((a, b) => {
      const order: Record<Job['status'], number> = {
        interviewing: 0,
        delivered: 1,
        pending: 2,
        finished: 3
      };
      return order[a.status] - order[b.status];
    })
    .slice(0, 3);

  const formatRelativeTime = (iso?: string): string => {
    if (!iso) return '';
    const then = new Date(iso).getTime();
    const diffMs = Math.max(0, Date.now() - then);
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(hours / 24);
    return days === 1 ? '昨天' : `${days} 天前`;
  };

  // "最近活动": derive one event per in-progress job from real fields
  const recentEvents = jobs
    .filter((j) => j.status !== 'pending')
    .map((j) => ({
      company: j.company || '未命名岗位',
      action:
        j.status === 'interviewing'
          ? '进入面试准备阶段'
          : j.status === 'finished'
          ? '面试复盘完成'
          : '已投递',
      time: formatRelativeTime(j.applyDate || j.lastUpdated)
    }))
    .slice(0, 4);

  // "AI 建议": data-driven hint (no invented counts)
  const aiSuggestion = pendingCount > 0
    ? `有 ${pendingCount} 个岗位还停留在待处理阶段，建议先完成 JD 分析，以明确匹配方向。`
    : jobs.length === 0
    ? '尚未开始跟踪任何岗位，识别目标 JD 后即可获得定制化的求职推进建议。'
    : '所有在推进的岗位状态正常，保持投递节奏并针对反馈持续优化经历描述。';

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* 1. Header Greeting & Action (Image 7) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-[26px] font-extrabold text-[#111814] tracking-tight">
            晚上好，{user.name || '未设置姓名'}
          </h1>
          <p className="text-xs sm:text-[13px] text-[#4E5B53] mt-1 font-medium">
            <span className="text-sage font-bold">{activeCount} 个岗位</span> 正在推进，今天有 <span className="text-warning font-bold">{pendingCount} 个重要任务</span> 需要完成。
          </p>
        </div>

        <button
          onClick={onOpenNewJob}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#234937] hover:bg-[#1A382A] text-white text-xs sm:text-[13px] font-bold shadow-xs transition-all duration-200 cursor-pointer self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>跟踪新的岗位</span>
        </button>
      </div>

      {/* 2. Top Stats 4 Cards Row (Images 3-6 Layout) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Card 1: 已投递岗位 (Image 4) */}
        <div
          onClick={() => navigateTo('jobs')}
          className="bg-white rounded-2xl border border-edge p-5 shadow-xs hover:border-sage/40 transition-all duration-200 cursor-pointer space-y-1.5"
        >
          <div className="text-3xl sm:text-[34px] font-black text-ink tracking-tight leading-none">
            {deliveredCount}
          </div>
          <div className="text-xs sm:text-[13px] font-bold text-ink">
            已投递岗位
          </div>
          <div>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-md bg-sage-soft text-sage border border-sage/20">
              <TrendingUp className="w-3 h-3" />
              <span>+{appliedThisWeekCount} 本周新增</span>
            </span>
          </div>
        </div>

        {/* Card 2: 面试中 (Image 5) */}
        <div
          onClick={() => navigateTo('interview_prep_center')}
          className="bg-white rounded-2xl border border-edge p-5 shadow-xs hover:border-sage/40 transition-all duration-200 cursor-pointer space-y-1.5"
        >
          <div className="text-3xl sm:text-[34px] font-black text-ink tracking-tight leading-none">
            {interviewingCount}
          </div>
          <div className="text-xs sm:text-[13px] font-bold text-ink">
            面试中
          </div>
          <div>
            <span className="inline-block text-[11px] font-semibold px-2.5 py-0.5 rounded-md bg-warning-bg text-warning border border-warning/20">
              重点推进
            </span>
          </div>
        </div>

        {/* Card 3: 待处理分析 (Image 3) */}
        <div
          onClick={() => navigateTo('jd_analysis')}
          className="bg-white rounded-2xl border border-edge p-5 shadow-xs hover:border-sage/40 transition-all duration-200 cursor-pointer space-y-1.5"
        >
          <div className="text-3xl sm:text-[34px] font-black text-ink tracking-tight leading-none">
            {pendingCount}
          </div>
          <div className="text-xs sm:text-[13px] font-bold text-ink">
            待处理分析
          </div>
          <div>
            <span className="inline-block text-[11px] font-semibold px-2.5 py-0.5 rounded-md bg-info-bg text-info border border-info/20">
              需补齐材料
            </span>
          </div>
        </div>

        {/* Card 4: 已完成复盘 (Image 6) */}
        <div
          onClick={() => navigateTo('interview_review_center')}
          className="bg-white rounded-2xl border border-edge p-5 shadow-xs hover:border-sage/40 transition-all duration-200 cursor-pointer space-y-1.5"
        >
          <div className="text-3xl sm:text-[34px] font-black text-ink tracking-tight leading-none">
            {finishedCount}
          </div>
          <div className="text-xs sm:text-[13px] font-bold text-ink">
            已完成复盘
          </div>
          <div>
            <span className="inline-block text-[11px] font-semibold px-2.5 py-0.5 rounded-md bg-page text-muted border border-edge">
              经验已沉淀
            </span>
          </div>
        </div>
      </div>

      {/* 3. Main Section: 正在推进 (Left 8 cols) + 下一步行动/最近活动/AI建议 (Right 4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (8 cols): 正在推进 */}
        <div className="lg:col-span-8 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-[#111814]">正在推进</h2>
            <button
              onClick={() => navigateTo('jobs')}
              className="text-xs text-[#6B7280] hover:text-[#111814] transition font-medium cursor-pointer"
            >
              查看全部 &gt;
            </button>
          </div>

          {/* Job Cards */}
          {jobs.length === 0 ? (
            <div className="bg-white rounded-2xl border border-[#E2E8E4] p-8 text-center space-y-2">
              <div className="text-[15px] font-bold text-[#111814]">还没有跟踪的岗位</div>
              <p className="text-xs text-[#6B7280]">
                点击右上角「跟踪新的岗位」，从 JD 分析开始建立你的求职推进记录。
              </p>
              <button
                onClick={onOpenNewJob}
                className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#234937] hover:bg-[#1A382A] text-white text-xs font-bold shadow-xs transition-all duration-200 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>跟踪新的岗位</span>
              </button>
            </div>
          ) : (
          <div className="space-y-4">
            {jobs.slice(0, 3).map((job, index) => {
              const badge = getStatusBadge(job);
              const steps = getJobSteps(job);
              const nextStep = getNextStepText(job);
              const matchScore = job.matchScore > 0 ? `${job.matchScore}%` : '—';

              return (
                <div
                  key={job.id || `job-${index}`}
                  className="bg-white rounded-2xl border border-[#E2E8E4] p-5 sm:p-6 shadow-xs hover:border-[#234937]/40 transition-all duration-200 space-y-3.5"
                >
                  {/* Row 1: Company & Status Badge & Match score */}
                  <div className="flex items-center justify-between">
                    <div className="text-[16px] font-bold text-[#111814]">
                      {job.company || '未命名岗位'}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${badge.className}`}>
                        {badge.text}
                      </span>
                      <span className="text-xs text-[#6B7280] font-medium">
                        匹配度 <strong className="font-bold text-[#111814]">{matchScore}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Row 2: Role */}
                  <div className="text-xs text-[#6B7280] -mt-1">
                    {job.role || '—'}
                  </div>

                  {/* Row 3: 6-Step Pipeline Tracker (Image 7 Stepper Style) */}
                  <div className="bg-[#F8FAF9] rounded-xl p-3.5 border border-[#E8EEEB] overflow-x-auto">
                    <div className="flex items-center justify-between min-w-[500px] text-xs">
                      {steps.map((st, sIdx) => {
                        const isLast = sIdx === steps.length - 1;
                        return (
                          <React.Fragment key={st.key}>
                            <div className="flex items-center gap-1 shrink-0">
                              {st.status === 'done' && (
                                <span className="text-[#234937] font-semibold flex items-center gap-1">
                                  <span className="text-[11px] font-bold">✓</span>
                                  <span>{st.name}</span>
                                </span>
                              )}
                              {st.status === 'active' && (
                                <span className="text-[#111814] font-bold flex items-center gap-1.5">
                                  <span className="w-2 h-2 rounded-full bg-[#234937] inline-block"></span>
                                  <span>{st.name}</span>
                                </span>
                              )}
                              {st.status === 'pending' && (
                                <span className="text-[#9CA3AF] font-normal flex items-center gap-1">
                                  <span className="w-2 h-2 rounded-full border border-[#9CA3AF] inline-block"></span>
                                  <span>{st.name}</span>
                                </span>
                              )}
                            </div>

                            {!isLast && (
                              <span className="text-[#D1D5DB] text-xs select-none">—</span>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>

                  {/* Row 4: Bottom Next Step & Action Link */}
                  <div className="flex items-center justify-between text-xs pt-1">
                    <div className="text-[#4B5563]">
                      <span>· 下一步：<strong className="text-[#111814] font-semibold">{nextStep}</strong></span>
                    </div>

                    <button
                      onClick={() => navigateTo('job_workspace', { jobId: job.id })}
                      className="text-xs text-[#234937] hover:underline font-semibold flex items-center gap-0.5 cursor-pointer"
                    >
                      <span>进入岗位</span>
                      <span>&gt;</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          )}
        </div>

        {/* Right Column (4 cols): 下一步行动 / 最近活动 / AI 建议 (Image 7) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Card 1: NEXT UP 下一步行动 */}
          <div className="bg-white rounded-xl border border-[#E2E8E5] p-5 sm:p-5.5 shadow-[0_1px_3px_rgba(0,0,0,0.03),0_1px_2px_rgba(0,0,0,0.02)] space-y-4">
            <div>
              <div className="text-[10px] font-bold text-faint uppercase tracking-wider">
                NEXT UP
              </div>
              <h2 className="text-[15px] font-bold text-ink mt-0.5">下一步行动</h2>
            </div>

            <div className="space-y-3.5">
              {nextUpJobs.length === 0 && (
                <div className="text-xs text-faint py-1.5">
                  暂无待推进的岗位，跟踪新的 JD 后这里会显示你的下一步行动。
                </div>
              )}
              {nextUpJobs.map((job, idx) => (
                <div
                  key={job.id || `next-${idx}`}
                  className={`space-y-1.5 ${idx > 0 ? 'pt-3 border-t border-[#EDF1EE]' : ''}`}
                >
                  <div className="text-xs font-bold text-ink">
                    {job.company || '未命名岗位'} · {getNextStepText(job)}
                  </div>
                  <div className="text-xs text-muted">
                    {job.status === 'interviewing' ? '面试准备阶段' : job.status === 'pending' ? 'JD 分析待完成' : '等待反馈'}
                  </div>
                  <button
                    onClick={() => navigateTo('job_workspace', { jobId: job.id })}
                    className="px-3.5 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-2xs transition cursor-pointer"
                  >
                    {job.status === 'pending' ? '去分析' : '进入岗位'}
                  </button>
                </div>
              ))}
            </div>

            <div className="border-t border-[#EDF1EE] pt-2.5">
              <button
                onClick={() => navigateTo('jobs')}
                className="text-xs text-muted hover:text-ink font-medium flex items-center justify-between w-full cursor-pointer transition"
              >
                <span>查看全部 &gt;</span>
              </button>
            </div>
          </div>

          {/* Card 2: RECENT 最近活动 */}
          <div className="bg-white rounded-2xl border border-[#E2E8E4] p-5 shadow-xs space-y-3.5">
            <div>
              <div className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-wider">
                RECENT
              </div>
              <h2 className="text-[15px] font-bold text-[#111814] mt-0.5">最近活动</h2>
            </div>

            <div className="space-y-3 text-xs">
              {recentEvents.length === 0 && (
                <div className="text-[11px] text-faint">
                  暂无活动记录，开始跟踪岗位后这里会显示最近更新。
                </div>
              )}
              {recentEvents.map((ev, idx) => (
                <div key={`${ev.company}-${idx}`} className="space-y-0.5">
                  <div className="flex items-center gap-1.5 font-medium text-[#111814]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#111814]" />
                    <span>{ev.action}</span>
                  </div>
                  <div className="text-[11px] text-[#6B7280] pl-3">
                    {ev.company} · {ev.time || '最近'}
                  </div>
                </div>
              ))}
            </div>

            <div className="border-t border-[#F3F4F6] pt-2">
              <button
                onClick={() => navigateTo('jobs')}
                className="text-xs text-[#6B7280] hover:text-[#111814] font-medium flex items-center justify-between w-full cursor-pointer"
              >
                <span>查看全部 &gt;</span>
              </button>
            </div>
          </div>

          {/* Card 3: AI 建议 */}
          <div className="bg-[#F7F9F7] rounded-2xl border border-[#DCE4DE] p-4.5 shadow-xs space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-[#234937]">
              <Sparkles className="w-3.5 h-3.5 text-[#234937]" />
              <span>AI 建议</span>
            </div>
            <p className="text-xs text-[#4B5563] leading-relaxed">
              {aiSuggestion}
            </p>
            <button
              onClick={() => navigateTo('experiences')}
              className="text-xs font-semibold text-[#234937] hover:underline flex items-center gap-0.5 cursor-pointer pt-1"
            >
              <span>查看建议 &gt;</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
