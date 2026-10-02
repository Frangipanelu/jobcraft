import React from 'react';
import { useParams } from 'react-router-dom';
import { InterviewPrepWorkspaceView } from '../../../components/interview/InterviewPrepWorkspaceView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /prep/:interviewId 面试准备空间真实路由页（FE-ROUTE-03）。 */
export const InterviewPrepPage: React.FC = () => {
  const { interviewId } = useParams<{ interviewId: string }>();
  useSyncRouteTab('interview_prep_workspace');

  return <InterviewPrepWorkspaceView interviewId={interviewId} />;
};
