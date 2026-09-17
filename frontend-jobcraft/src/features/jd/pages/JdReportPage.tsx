import React from 'react';
import { useParams } from 'react-router-dom';
import { JDReportDetailView } from '../../../components/jd/JDReportDetailView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/**
 * /jd-report/:jdId（及 /jobs/:jobId/jd/:jdId 别名）JD 分析报告真实路由页（FE-ROUTE-03）。
 */
export const JdReportPage: React.FC = () => {
  const { jdId } = useParams<{ jdId: string }>();
  useSyncRouteTab('jd_report');
  return <JDReportDetailView analysisId={jdId} />;
};
