import React from 'react';
import { useParams } from 'react-router-dom';
import { CreateReview } from '../../../pages/CreateReview';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /review/new·review/new/:jobId 新建复盘真实路由壳页（FE-ROUTE-02 / 组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const CreateReviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  useSyncRouteTab('create_review');
  return <CreateReview initialJobId={jobId} />;
};
