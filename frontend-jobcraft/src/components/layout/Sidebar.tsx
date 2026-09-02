import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import { NavigationTab } from '../../types/jobcraft';
import {
  LayoutDashboard,
  Briefcase,
  FileSearch,
  BookOpenCheck,
  RotateCcw,
  Sparkles,
  Award,
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen
} from 'lucide-react';

interface SidebarProps {
  onOpenNewJob: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  onOpenNewJob
}) => {
  const { currentTab, navigateTo, jobs, interviews } = useJobCraft();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const interviewingJobsCount = jobs.filter((j) => j.status === 'interviewing').length;
  const pendingReviewCount = interviews.filter((i) => i.status === 'completed' && !i.review).length || 1;

  const navItems: {
    section?: string;
    items: {
      id: NavigationTab;
      label: string;
      icon: React.ReactNode;
      badge?: string | number;
      badgeColor?: string;
    }[];
  }[] = [
    {
      items: [
        {
          id: 'workbench',
          label: '工作台',
          icon: <LayoutDashboard className="w-4 h-4" />
        }
      ]
    },
    {
      section: '职业资产',
      items: [
        {
          id: 'experiences',
          label: '我的经历',
          icon: <Award className="w-4 h-4" />
        }
      ]
    },
    {
      section: '求职',
      items: [
        {
          id: 'jobs',
          label: '我的岗位',
          icon: <Briefcase className="w-4 h-4" />,
          badge: interviewingJobsCount > 0 ? `${interviewingJobsCount}` : undefined,
          badgeColor: 'bg-sage-soft text-sage'
        },
        {
          id: 'jd_analysis',
          label: 'JD 分析',
          icon: <FileSearch className="w-4 h-4" />
        }
      ]
    },
    {
      section: '面试',
      items: [
        {
          id: 'interview_prep_center',
          label: '面试准备',
          icon: <BookOpenCheck className="w-4 h-4" />
        },
        {
          id: 'interview_review_center',
          label: '面试复盘',
          icon: <RotateCcw className="w-4 h-4" />,
          badge: pendingReviewCount > 0 ? `${pendingReviewCount}` : undefined,
          badgeColor: 'bg-warning-bg text-warning'
        }
      ]
    }
  ];

  return (
    <aside
      className={`h-screen bg-ink text-faint flex flex-col justify-between shrink-0 select-none border-r border-ink transition-all duration-300 ${
        isCollapsed ? 'w-[68px]' : 'w-60'
      }`}
    >
      {/* Brand Header */}
      <div className="flex-1 flex flex-col min-h-0">
        <div
          className={`border-b border-white/10 flex items-center transition-all ${
            isCollapsed ? 'justify-center py-3.5 px-2' : 'justify-between p-4'
          }`}
        >
          {isCollapsed ? (
            <button
              onClick={() => setIsCollapsed(false)}
              className="w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 text-faint hover:text-white flex items-center justify-center transition cursor-pointer"
              title="展开侧边栏"
            >
              <PanelLeftOpen className="w-5 h-5 text-sage-dim" />
            </button>
          ) : (
            <>
              <div className="flex items-center gap-2.5 min-w-0 overflow-hidden">
                <div
                  className="w-8 h-8 rounded-lg bg-sage flex items-center justify-center text-white shadow-sm shadow-sage/30 shrink-0"
                  title="JobCraft"
                >
                  <Sparkles className="w-4 h-4" />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white tracking-tight text-sm">JobCraft</span>
                    <span className="text-[10px] font-bold tracking-wide uppercase px-1.5 py-0.5 rounded bg-sage/30 text-sage-dim border border-sage/50 shrink-0">
                      V2
                    </span>
                  </div>
                  <p className="text-[11px] text-faint font-medium truncate">求职与经历闭环</p>
                </div>
              </div>

              {/* Collapse button */}
              <button
                onClick={() => setIsCollapsed(true)}
                className="p-1.5 rounded-lg text-faint hover:text-white hover:bg-white/10 transition shrink-0 cursor-pointer"
                title="收起侧边栏"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            </>
          )}
        </div>

        {/* Navigation list */}
        <div className="p-2 space-y-4 overflow-y-auto flex-1 custom-scrollbar">
          {navItems.map((group, gIdx) => (
            <div key={gIdx} className="space-y-1">
              {!isCollapsed && group.section && (
                <div className="px-3 py-1 text-[11px] font-semibold text-muted uppercase tracking-wider">
                  {group.section}
                </div>
              )}
              {group.items.map((item) => {
                const isActivewk =
                  currentTab === item.id ||
                  (item.id === 'jobs' && currentTab === 'job_workspace') ||
                  (item.id === 'jd_analysis' && (currentTab === 'jd_report' || currentTab === 'jd_analysis_center')) ||
                  (item.id === 'interview_prep_center' && currentTab === 'interview_prep_workspace') ||
                  (item.id === 'interview_review_center' && currentTab === 'interview_review_detail');

                return (
                  <button
                    key={item.id}
                    onClick={() => navigateTo(item.id)}
                    title={isCollapsed ? item.label : undefined}
                    className={`flex items-center ${
                      isCollapsed
                        ? 'justify-center w-10 h-10 mx-auto rounded-xl'
                        : 'w-full justify-between px-3 py-2 rounded-lg'
                    } text-xs font-medium transition-all relative cursor-pointer ${
                      isActivewk
                        ? 'bg-sage text-white font-semibold shadow-xs'
                        : 'text-faint hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-2.5'} min-w-0`}>
                      <span className={isActivewk ? 'text-white' : 'text-faint'}>
                        {item.icon}
                      </span>
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                    </div>

                    {!isCollapsed && item.badge && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-md font-semibold shrink-0 ${
                          item.badgeColor || 'bg-ink text-faint'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}

                    {isCollapsed && item.badge && (
                      <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-warning ring-2 ring-ink" />
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
};
