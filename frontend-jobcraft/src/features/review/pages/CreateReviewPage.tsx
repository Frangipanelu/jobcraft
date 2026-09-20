import React from 'react';
import { useParams } from 'react-router-dom';
import { CreateReview } from '../../../pages/CreateReview';

/** /review/new、/review/new/:jobId 新建复盘真实路由壳页（FE-ROUTE-02 / 组1-壳收口）。 */
export const CreateReviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  return <CreateReview initialJobId={jobId} />;
};
