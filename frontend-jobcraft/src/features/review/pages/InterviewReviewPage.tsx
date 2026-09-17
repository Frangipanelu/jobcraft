import React from 'react';
import { useParams } from 'react-router-dom';
import { InterviewReviewDetailView } from '../../../components/review/InterviewReviewDetailView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /review/:interviewId 面试复盘详情真实路由页（FE-ROUTE-03）。 */
export const InterviewReviewPage: React.FC = () => {
  const { interviewId } = useParams<{ interviewId: string }>();
  useSyncRouteTab('interview_review_detail');
  return <InterviewReviewDetailView interviewId={interviewId} />;
};
