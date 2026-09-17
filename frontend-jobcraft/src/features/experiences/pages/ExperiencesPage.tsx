import React from 'react';
import { useParams } from 'react-router-dom';
import { ExperiencesView } from '../../../components/experiences/ExperiencesView';
import { useSyncRouteTab } from '../../../router/useSyncRouteTab';

/**
 * /experiences 与 /experiences/:experienceId 真实路由页（FE-ROUTE-03）。
 * experienceId 命中时打开对应经历的编辑弹窗（ExperiencesView.initialSelectedExpId）。
 */
export const ExperiencesPage: React.FC = () => {
  const { experienceId } = useParams<{ experienceId: string }>();
  useSyncRouteTab('experiences');
  return <ExperiencesView initialSelectedExpId={experienceId} />;
};
