import React from 'react';
import { InterviewPrepCenterView } from '../../../components/interview/InterviewPrepCenterView';
import { useAppShellOutlet } from '../../../app/AppShell';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /prep 面试准备中心真实路由页（FE-ROUTE-02 / 组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const InterviewPrepCenterPage: React.FC = () => {
  useSyncRouteTab('interview_prep_center');
  const { onOpenNewInterview } = useAppShellOutlet();
  return (
    <InterviewPrepCenterView
      onOpenNewInterview={() => onOpenNewInterview('standalone')}
    />
  );
};
