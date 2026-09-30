import React from 'react';
import { InterviewReviewCenterView } from '../../../components/review/InterviewReviewCenterView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /review 面试复盘中心真实路由壳页（FE-ROUTE-02 / 组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const InterviewReviewCenterPage: React.FC = () => {
  useSyncRouteTab('interview_review_center');
  return <InterviewReviewCenterView />;
};
