import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { UserProfileView } from '../../components/user/UserProfileView';

const PROFILE_TABS = ['resumes', 'profile', 'preferences', 'settings'] as const;
type ProfileTab = (typeof PROFILE_TABS)[number];

/**
 * /profile 真实路由页（FE-ROUTE-01 试点）。
 * 数据层已由 react-query hooks 承载（FE-QUERY-01）；
 * 这里做路由壳：解析 ?tab= 并作为 initialTab 传给 UserProfileView（URL 作为挂载时的单一来源）。
 */
export const ProfilePage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const tab = searchParams.get('tab');
  const initialTab = tab && (PROFILE_TABS as readonly string[]).includes(tab)
    ? (tab as ProfileTab)
    : undefined;

  return <UserProfileView initialTab={initialTab} />;
};