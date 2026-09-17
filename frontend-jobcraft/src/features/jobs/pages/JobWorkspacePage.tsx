import React from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { JobWorkspaceView } from '../../../components/jobs/JobWorkspaceView';
import { useAppShellOutlet } from '../../../app/AppShell';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

type JobSubTab = 'jd' | 'resume' | 'interview';

function toJobSubTab(value: string | null): JobSubTab | undefined {
  return value === 'resume' || value === 'interview' || value === 'jd' ? value : undefined;
}

/**
 * /jobs/:jobId 岗位空间真实路由页（FE-ROUTE-02）。
 * jobId 来自 URL 参数；?tab=jd|resume|interview 作为子 tab 初值（NewJobModal 创建后落地 jd）。
 */
export const JobWorkspacePage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const [searchParams] = useSearchParams();
  useSyncRouteTab('job_workspace');
  const { onOpenMockInterview, onOpenNewInterview } = useAppShellOutlet();

  return (
    <JobWorkspaceView
      jobId={jobId}
      initialSubTab={toJobSubTab(searchParams.get('tab'))}
      onOpenMockInterview={onOpenMockInterview}
      onOpenNewInterview={onOpenNewInterview}
    />
  );
};