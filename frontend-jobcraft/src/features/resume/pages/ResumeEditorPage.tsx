import React from 'react';
import { useParams } from 'react-router-dom';
import { ResumeEditorView } from '../../../components/resume/ResumeEditorView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /resume·/resume/:jobId 简历编辑器真实路由页（FE-ROUTE-02 / 组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const ResumeEditorPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  useSyncRouteTab('resume_editor');
  return <ResumeEditorView jobId={jobId} />;
};
