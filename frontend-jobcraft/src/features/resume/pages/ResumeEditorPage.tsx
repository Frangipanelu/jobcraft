import React from 'react';
import { useParams } from 'react-router-dom';
import { ResumeEditorView } from '../../../components/resume/ResumeEditorView';

/** /resume、/resume/:jobId 简历编辑器真实路由页（FE-ROUTE-02 / 组1-壳收口）。 */
export const ResumeEditorPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  return <ResumeEditorView jobId={jobId} />;
};
