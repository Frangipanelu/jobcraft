import React from 'react';
import { useParams } from 'react-router-dom';
import { CreateInterview } from '../../../pages/CreateInterview';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /interview/new·interview/new/:jobId 新建面试真实路由壳页（FE-ROUTE-02 / 组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const CreateInterviewPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  useSyncRouteTab('create_interview');
  return <CreateInterview initialJobId={jobId} />;
};
