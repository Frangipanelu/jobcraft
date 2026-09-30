import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useJobCraft } from '../context/JobCraftContext';
import type { NavigationTab } from '../types/jobcraft';

/**
 * 路由态同步钩子（FE-ROUTE-02 / FE-NAV-01）：
 * 将当前 URL 参数同步进遗留 JobCraftContext（sidebar 高亮 / 面包屑 / selectedJobId）。
 * 只回填状态、不触发跳转（`syncTabState`），否则会与来源 URL 互相打架。
 */
export function useSyncRouteTab(tab?: NavigationTab) {
  const { syncTabState } = useJobCraft();
  const { jobId, jdId, interviewId, experienceId } = useParams<{
    jobId?: string;
    jdId?: string;
    interviewId?: string;
    experienceId?: string;
  }>();

  useEffect(() => {
    if (!tab) return;
    syncTabState(tab, {
      jobId,
      jdId,
      interviewId,
      expId: experienceId,
    });
  }, [tab, jobId, jdId, interviewId, experienceId, syncTabState]);
}