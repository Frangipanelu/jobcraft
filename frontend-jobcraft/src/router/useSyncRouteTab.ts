import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useJobCraft } from '../context/JobCraftContext';
import type { NavigationTab } from '../types/jobcraft';

/**
 * 路由态同步钩子（FE-ROUTE-02）：
 * 将当前 URL 参数同步进遗留 JobCraftContext（sidebar 高亮 / 面包屑 / selectedJobId）。
 * LegacyPageWrapper 与已迁移的 AppShell 页面共用，保证两种渲染方式行为一致。
 */
export function useSyncRouteTab(tab?: NavigationTab) {
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
}