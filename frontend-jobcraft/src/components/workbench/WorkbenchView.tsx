import React from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
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

  // Metrics aligned with Image 7
  const deliveredCount = 12;
  const interviewingCount = 3;
  const pendingCount = 5;
  const finishedCount = 2;

  // Render 6-step pipeline tracker for each job matching Image 7
  const getJobSteps = (index: number): StepItem[] => {
    if (index === 0) {
      // 字节跳动: ✓ JD分析 — ✓ 经历匹配 — ✓ 定制简历 — ✓ 已投递 — ● 面试准备 — ○ 面试复盘
      return [
        { key: 'jd', name: 'JD分析', status: 'done' },
        { key: 'match', name: '经历匹配', status: 'done' },
        { key: 'resume', name: '定制简历', status: 'done' },
        { key: 'applied', name: '已投递', status: 'done' },
        { key: 'prep', name: '面试准备', status: 'active' },
        { key: 'review', name: '面试复盘', status: 'pending' }
      ];
    } else if (index === 1) {
      // 腾讯: ✓ JD分析 — ✓ 经历匹配 — ✓ 定制简历 — ● 已投递 — ○ 面试准备 — ○ 面试复盘
      return [
        { key: 'jd', name: 'JD分析', status: 'done' },
        { key: 'match', name: '经历匹配', status: 'done' },
        { key: 'resume', name: '定制简历', status: 'done' },
        { key: 'applied', name: '已投递', status: 'active' },
        { key: 'prep', name: '面试准备', status: 'pending' },
        { key: 'review', name: '面试复盘', status: 'pending' }
      ];
    } else {
      // 某科技创业公司: ● JD分析 — ○ 经历匹配 — ○ 定制简历 — ○ 已投递 — ○ 面试准备 — ○ 面试复盘
      return [
        { key: 'jd', name: 'JD分析', status: 'active' },
        { key: 'match', name: '经历匹配', status: 'pending' },
        { key: 'resume', name: '定制简历', status: 'pending' },
        { key: 'applied', name: '已投递', status: 'pending' },
        { key: 'prep', name: '面试准备', status: 'pending' },
        { key: 'review', name: '面试复盘', status: 'pending' }
      ];
    }
  };

  const getStatusBadge = (index: number) => {
    if (index === 0) {
      return { text: '面试中', className: 'bg-sage-soft text-sage border border-sage/20' };
    }
    if (index === 1) {
      return { text: '已受邀', className: 'bg-warning-bg text-warning border border-warning/20' };
    }
    return { text: 'JD分析中', className: 'bg-info-bg text-info border border-info/20' };
  };

  const getNextStepText = (index: number) => {
    if (index === 0) return '准备第一轮业务面';
    if (index === 1) return '等待面试通知';
    return '查看 JD 分析结果';
  };

  const getJobMatchScore = (index: number) => {
    if (index === 0) return 82;
    if (index === 1) return 76;
    return 68;
  };

  const getRoleName = (index: number) => {
    if (index === 0) return 'AI 产品经理';
    if (index === 1) return '产品经理';
    return 'AI 产品经理';
  };

  const getCompanyName = (index: number, job: any) => {
    if (index === 0) return '字节跳动';
    if (index === 1) return '腾讯';
    return '某科技创业公司';
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* 1. Header Greeting & Action (Image 7) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-[26px] font-extrabold text-[#111814] tracking-tight">
            晚上好，{user.name || '菁菁'}
          </h1>
          <p className="text-xs sm:text-[13px] text-[#4E5B53] mt-1 font-medium">
            <span className="text-sage font-bold">3 个岗位</span> 正在推进，今天有 <span className="text-warning font-bold">1 个重要任务</span> 需要完成。
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
              <span>+3 本周新增</span>
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
          <div className="space-y-4">
            {jobs.slice(0, 3).map((job, index) => {
              const badge = getStatusBadge(index);
              const steps = getJobSteps(index);
              const nextStep = getNextStepText(index);
              const matchScore = getJobMatchScore(index);
              const companyName = getCompanyName(index, job);
              const roleName = getRoleName(index);

              return (
                <div
                  key={job.id || `job-${index}`}
                  className="bg-white rounded-2xl border border-[#E2E8E4] p-5 sm:p-6 shadow-xs hover:border-[#234937]/40 transition-all duration-200 space-y-3.5"
                >
                  {/* Row 1: Company & Status Badge & Match score */}
                  <div className="flex items-center justify-between">
                    <div className="text-[16px] font-bold text-[#111814]">
                      {companyName}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${badge.className}`}>
                        {badge.text}
                      </span>
                      <span className="text-xs text-[#6B7280] font-medium">
                        匹配度 <strong className="font-bold text-[#111814]">{matchScore}%</strong>
                      </span>
                    </div>
                  </div>

                  {/* Row 2: Role */}
                  <div className="text-xs text-[#6B7280] -mt-1">
                    {roleName}
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
              {/* Item 1 */}
              <div className="space-y-1.5">
                <div className="text-xs font-bold text-ink">
                  准备字节跳动第一轮面试
                </div>
                <div className="text-xs text-muted">明天 14:00</div>
                <button
                  onClick={() => navigateTo('interview_prep_workspace', { jobId: 'job-1' })}
                  className="px-3.5 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-2xs transition cursor-pointer"
                >
                  开始准备
                </button>
              </div>

              {/* Item 2 */}
              <div className="space-y-1.5 pt-3 border-t border-[#EDF1EE]">
                <div className="text-xs font-bold text-ink">
                  查看腾讯产品经理 JD 分析
                </div>
                <div className="text-xs text-muted">AI 已完成岗位匹配</div>
                <button
                  onClick={() => navigateTo('jd_report', { jdId: 'jd-tencent-1' })}
                  className="px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-medium transition cursor-pointer shadow-2xs"
                >
                  查看分析
                </button>
              </div>

              {/* Item 3 */}
              <div className="space-y-1.5 pt-3 border-t border-[#EDF1EE]">
                <div className="text-xs font-bold text-ink">
                  完成某科技公司定制简历
                </div>
                <div className="text-xs text-faint">草稿未完成</div>
                <button
                  onClick={() => navigateTo('resume_editor', { jobId: 'job-3' })}
                  className="px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-medium transition cursor-pointer shadow-2xs"
                >
                  继续编辑
                </button>
              </div>
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
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 font-medium text-[#111814]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#111814]" />
                  <span>JD 分析完成</span>
                </div>
                <div className="text-[11px] text-[#6B7280] pl-3">腾讯 · 2小时前</div>
              </div>

              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 font-medium text-[#111814]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#111814]" />
                  <span>经历匹配完成</span>
                </div>
                <div className="text-[11px] text-[#6B7280] pl-3">字节跳动 · 5小时前</div>
              </div>

              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 font-medium text-[#111814]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#111814]" />
                  <span>简历已生成</span>
                </div>
                <div className="text-[11px] text-[#6B7280] pl-3">字节跳动 · 昨天 18:20</div>
              </div>

              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5 font-medium text-[#111814]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#111814]" />
                  <span>状态更新为已投递</span>
                </div>
                <div className="text-[11px] text-[#6B7280] pl-3">某科技公司 · 昨天 14:00</div>
              </div>
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
              有 3 条经历没有量化成果，完成后可以提升岗位匹配度。
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
