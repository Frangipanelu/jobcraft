import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { NavigationTab } from '../types/jobcraft';

/** `navigateTo` 兼容的参数形状（FE-ROUTE-03）。 */
export interface TabNavParams {
  jobId?: string;
  interviewId?: string;
  jdId?: string;
  expId?: string;
  workspaceTab?: 'jd' | 'resume' | 'interview';
  profileTab?: 'resumes' | 'profile' | 'preferences' | 'settings';
}

/**
 * tab → URL 的单一映射（FE-ROUTE-03）。
 * 已迁移 tab 用 AppShell 真实路由；中心 / 创建 / 简历编辑用 LegacyPageWrapper，但同样拥有 URL。
 * 返回值恒为绝对路径，供 `useTabNavigate` 与直接 `navigate()` 共用。
 */
export function tabToPath(tab: NavigationTab, params: TabNavParams = {}): string {
  switch (tab) {
    case 'workbench':
      return '/workbench';
    case 'jobs':
      return '/jobs';
    case 'job_workspace':
      return `/jobs/${params.jobId ?? ''}`;
    case 'jd_analysis':
    case 'jd_analysis_center':
      return '/jd-analysis';
    case 'jd_report':
      return `/jd-report/${params.jdId ?? ''}`;
    case 'experiences':
      return params.expId ? `/experiences/${params.expId}` : '/experiences';
    case 'resume_editor':
      return params.jobId ? `/resume/${params.jobId}` : '/resume';
    case 'interview_prep_center':
      return '/prep';
    case 'interview_prep_workspace':
      return `/prep/${params.interviewId ?? ''}`;
    case 'create_interview':
      return '/interview/new';
    case 'interview_review_center':
      return '/review';
    case 'create_review':
      return '/review/new';
    case 'interview_review_detail':
      return `/review/${params.interviewId ?? ''}`;
    case 'user_profile':
    case 'settings':
      return '/profile';
    default:
      return '/workbench';
  }
}

/**
 * 导航钩子：以 legacy `navigateTo(tab, params)` 的调用形态触发真实路由跳转（FE-ROUTE-03）。
 * 选中项等副作用由落地路由的 `useSyncRouteTab` 从 URL 参数回填，故此处只做导航。
 */
export function useTabNavigate() {
  const navigate = useNavigate();
  return useCallback(
    (tab: NavigationTab, params?: TabNavParams) => navigate(tabToPath(tab, params)),
    [navigate],
  );
}
