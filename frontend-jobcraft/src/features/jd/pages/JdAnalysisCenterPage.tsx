import React from 'react';
import { JDAnalysisCenterView } from '../../../components/jd/JDAnalysisCenterView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/** /jd-analysis JD 分析中心真实路由页（FE-ROUTE-02，组1-壳收口 + FE-TAB-01 路由态回填）。*/
export const JdAnalysisCenterPage: React.FC = () => {
  useSyncRouteTab('jd_analysis_center');
  return <JDAnalysisCenterView />;
};
