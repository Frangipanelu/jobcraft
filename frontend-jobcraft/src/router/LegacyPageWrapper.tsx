import React from 'react';
import { MainLayout } from '../app/legacy/MainLayout';
import { useSyncRouteTab } from './useSyncRouteTab';
import type { NavigationTab } from '../types/jobcraft';

interface LegacyPageWrapperProps {
  tab?: NavigationTab;
}

/**
 * 过渡层：把 React Router 的 URL 参数同步进遗留 JobCraftContext 的 currentTab，
 * 再渲染遗留 MainLayout。路由层就绪后，各 domain 将逐步替换为独立页面，
 * 本组件与 MainLayout 将一起被移除。URL→context 同步逻辑见 useSyncRouteTab。
 */
export const LegacyPageWrapper: React.FC<LegacyPageWrapperProps> = ({ tab }) => {
  useSyncRouteTab(tab);
  return <MainLayout />;
};