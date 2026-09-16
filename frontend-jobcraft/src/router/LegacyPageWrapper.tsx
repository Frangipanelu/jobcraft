import React, { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useJobCraft } from '../context/JobCraftContext';
import { MainLayout } from '../app/legacy/MainLayout';
import type { NavigationTab } from '../types/jobcraft';

interface LegacyPageWrapperProps {
  tab?: NavigationTab;
}

/**
 * 过渡层：把 React Router 的 URL 参数同步进遗留 JobCraftContext 的 navigateTo，
 * 再渲染遗留 MainLayout。路由层就绪后，各 domain 将逐步替换为独立页面，
 * 本组件与 MainLayout 将一起被移除。
 */
export const LegacyPageWrapper: React.FC<LegacyPageWrapperProps> = ({ tab }) => {
  const { navigateTo } = useJobCraft();
  const { jobId, jdId, interviewId, experienceId } = useParams<{
    jobId?: string;
    jdId?: string;
    interviewId?: string;
    experienceId?: string;
  }>();

  useEffect(() => {
    if (!tab) return;
    navigateTo(tab, {
      jobId,
      jdId,
      interviewId,
      expId: experienceId,
    });
  }, [tab, jobId, jdId, interviewId, experienceId, navigateTo]);

  return <MainLayout />;
};