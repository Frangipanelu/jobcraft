import React, { useState, useRef, useEffect } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  ChevronRight,
  Sparkles,
  ArrowLeft,
  Search,
  ExternalLink,
  Plus,
  User,
  Target,
  FileText,
  Settings,
  LogOut,
  Bell
} from 'lucide-react';

interface TopHeaderProps {
  onOpenNewJob: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  onOpenNewJob
}) => {
  const {
    currentTab,
    navigateTo,
    selectedJobId,
    selectedInterviewId,
    jobs,
    interviews,
    user,
    logout,
    showToast
  } = useJobCraft();

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentJob = jobs.find((j) => j.id === selectedJobId);
  const currentInterview = interviews.find((i) => i.id === selectedInterviewId);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleMenuClick = (profileTab: 'resumes' | 'profile' | 'preferences' | 'settings') => {
    setIsDropdownOpen(false);
    navigateTo('user_profile', { profileTab });
  };

  const handleSignOut = () => {
    setIsDropdownOpen(false);
    logout();
    showToast({
      type: 'info',
      title: '已退出登录',
      message: '已安全登出账号。'
    });
  };

  return (
    <header className="h-16 bg-white border-b border-edge px-8 flex items-center justify-between shrink-0 sticky top-0 z-30 shadow-2xs">
      {/* Breadcrumb path */}
      <div className="flex items-center gap-2 text-xs text-muted font-medium overflow-hidden">
        <button
          onClick={() => navigateTo('workbench')}
          className="hover:text-sage transition font-medium flex items-center gap-1 text-ink"
        >
          工作台
        </button>

        {currentTab === 'jobs' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">我的岗位</span>
          </>
        )}

        {currentTab === 'job_workspace' && currentJob && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <button
              onClick={() => navigateTo('jobs')}
              className="hover:text-sage transition text-muted"
            >
              我的岗位
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold truncate">
              {currentJob.company} · {currentJob.role}
            </span>
          </>
        )}

        {(currentTab === 'jd_analysis' || currentTab === 'jd_analysis_center') && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">JD 分析中心</span>
          </>
        )}

        {currentTab === 'jd_report' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <button
              onClick={() => navigateTo('jd_analysis')}
              className="hover:text-sage transition text-muted"
            >
              JD 分析中心
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">
              {currentJob ? `${currentJob.company} · JD 深度分析报告` : 'JD 深度分析报告'}
            </span>
          </>
        )}

        {currentTab === 'resume_editor' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            {currentJob && (
              <>
                <button
                  onClick={() => navigateTo('job_workspace', { jobId: currentJob.id })}
                  className="hover:text-sage transition text-muted"
                >
                  {currentJob.company}
                </button>
                <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
              </>
            )}
            <span className="text-ink font-semibold">定制简历工作区</span>
          </>
        )}

        {currentTab === 'interview_prep_center' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">面试准备任务中心</span>
          </>
        )}

        {currentTab === 'interview_prep_workspace' && currentInterview && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <button
              onClick={() => navigateTo('interview_prep_center')}
              className="hover:text-sage transition text-muted"
            >
              面试准备
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold truncate">
              {currentInterview.company} · {currentInterview.roundName}
            </span>
          </>
        )}

        {currentTab === 'interview_review_center' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">面试复盘中心</span>
          </>
        )}

        {currentTab === 'interview_review_detail' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <button
              onClick={() => navigateTo('interview_review_center')}
              className="hover:text-sage transition text-muted"
            >
              面试复盘
            </button>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">
              字节跳动 · 第1面业务面 · 智能复盘报告
            </span>
          </>
        )}

        {currentTab === 'experiences' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">我的经历</span>
          </>
        )}

        {currentTab === 'user_profile' && (
          <>
            <ChevronRight className="w-3.5 h-3.5 text-faint shrink-0" />
            <span className="text-ink font-semibold">个人中心与历史简历</span>
          </>
        )}
      </div>

      {/* Right controls: User Profile & Notifications */}
      <div className="flex items-center gap-3 shrink-0 relative" ref={dropdownRef}>
        {/* Notification Bell */}
        <button
          onClick={() => showToast({ type: 'info', title: '通知中心', message: '暂无新的待处理事项' })}
          className="p-2 rounded-full text-muted hover:text-ink hover:bg-page transition"
          title="通知"
        >
          <Bell className="w-4 h-4" />
        </button>

        {/* User Account Avatar Button (p1 style) */}
        <button
          onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          className="flex items-center gap-2 p-1 rounded-full hover:ring-2 hover:ring-sage/30 transition select-none cursor-pointer focus:outline-none"
        >
          <div className="w-8 h-8 rounded-full bg-sage text-white flex items-center justify-center font-bold text-xs shadow-xs">
            菁
          </div>
        </button>

        {/* Dropdown Menu (p1 prototype layout) */}
        {isDropdownOpen && (
          <div className="absolute right-0 top-12 w-64 bg-white rounded-xl shadow-xl border border-edge py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
            {/* Top User Info */}
            <div className="px-4 py-3 border-b border-edge flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-sage text-white flex items-center justify-center font-bold text-sm shadow-xs shrink-0">
                菁
              </div>
              <div className="min-w-0 flex-1 text-left">
                <div className="text-sm font-bold text-ink truncate">{user.name || '菁菁'}</div>
                <div className="text-xs text-muted truncate">{user.role || 'AI 产品方向'}</div>
              </div>
            </div>

            {/* Menu Links */}
            <div className="py-1">
              <button
                onClick={() => handleMenuClick('profile')}
                className="w-full px-4 py-2.5 text-xs text-ink hover:bg-page flex items-center gap-2.5 transition text-left"
              >
                <User className="w-4 h-4 text-muted" />
                <span>个人资料</span>
              </button>

              <button
                onClick={() => handleMenuClick('preferences')}
                className="w-full px-4 py-2.5 text-xs text-ink hover:bg-page flex items-center gap-2.5 transition text-left"
              >
                <Target className="w-4 h-4 text-muted" />
                <span>求职偏好</span>
              </button>

              <button
                onClick={() => handleMenuClick('resumes')}
                className="w-full px-4 py-2.5 text-xs text-ink hover:bg-page flex items-center gap-2.5 transition text-left font-medium"
              >
                <FileText className="w-4 h-4 text-sage" />
                <span className="flex-1">历史简历管理</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-sage-soft text-sage font-semibold">底座</span>
              </button>

              <button
                onClick={() => handleMenuClick('settings')}
                className="w-full px-4 py-2.5 text-xs text-ink hover:bg-page flex items-center gap-2.5 transition text-left"
              >
                <Settings className="w-4 h-4 text-muted" />
                <span>账号设置</span>
              </button>
            </div>

            {/* Sign Out */}
            <div className="border-t border-edge pt-1 mt-1">
              <button
                onClick={handleSignOut}
                className="w-full px-4 py-2 text-xs text-error hover:bg-error-bg flex items-center gap-2.5 transition text-left cursor-pointer"
              >
                <LogOut className="w-4 h-4 text-error" />
                <span>退出登录</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
