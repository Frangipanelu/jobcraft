import React from 'react';
import { InterviewPrepCenterView } from '../../../components/interview/InterviewPrepCenterView';
import { useAppShellOutlet } from '../../../app/AppShell';

/** /prep 面试准备中心真实路由页（FE-ROUTE-02 / 组1-壳收口）。 */
export const InterviewPrepCenterPage: React.FC = () => {
  const { onOpenMockInterview, onOpenNewInterview } = useAppShellOutlet();
  return (
    <InterviewPrepCenterView
      onOpenMockInterview={onOpenMockInterview}
      onOpenNewInterview={() => onOpenNewInterview('standalone')}
    />
  );
};
