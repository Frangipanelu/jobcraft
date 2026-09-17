import React from 'react';
import { JobsListView } from '../../../components/jobs/JobsListView';
import { useAppShellOutlet } from '../../../app/AppShell';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/**
 * /jobs 岗位列表真实路由页（FE-ROUTE-02）。
 * AppShell 壳 + JobsListView 直接渲染。
 */
export const JobsPage: React.FC = () => {
  useSyncRouteTab('jobs');
  const { onOpenNewJob } = useAppShellOutlet();

  return <JobsListView onOpenNewJob={onOpenNewJob} />;
};