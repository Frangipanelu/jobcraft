import React from 'react';
import { WorkbenchView } from '../../../components/workbench/WorkbenchView';
import { useAppShellOutlet } from '../../../app/AppShell';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/**
 * /workbench 真实路由页（FE-ROUTE-02）。
 * AppShell 壳 + WorkbenchView 直接渲染，不再经 LegacyPageWrapper/MainLayout。
 */
export const WorkbenchPage: React.FC = () => {
  useSyncRouteTab('workbench');
  const { onOpenNewJob } = useAppShellOutlet();

  return <WorkbenchView onOpenNewJob={onOpenNewJob} />;
};