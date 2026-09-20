import React from 'react';
import { useParams } from 'react-router-dom';
import { CreateInterview } from '../../../pages/CreateInterview';

/** /interview/new、/interview/new/:jobId 新建面试真实路由壳页（FE-ROUTE-02 / 组1-壳收口）。 */
export const CreateInterviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  return <CreateInterview initialJobId={jobId} />;
};
