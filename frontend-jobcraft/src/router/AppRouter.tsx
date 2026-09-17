import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LegacyPageWrapper } from './LegacyPageWrapper';
import { AppShell } from '../app/AppShell';
import { ProfilePage } from '../features/profile/ProfilePage';

/**
 * 路由表：
 * - 显式路由在 URL 与遗留 currentTab 之间建立映射（通过 LegacyPageWrapper 同步）。
 * - 遗留 navigateTo 触发的视图切换不改变 URL，属于过渡期允许的行为。
 * - FE-ROUTE-01：/profile 已迁移为真实路由（AppShell 壳 + ProfilePage），不再经过 LegacyPageWrapper。
 */
export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/workbench" replace />} />
      <Route path="/workbench" element={<LegacyPageWrapper tab="workbench" />} />
      <Route path="/jobs/:jobId" element={<LegacyPageWrapper tab="job_workspace" />} />
      <Route path="/jobs/:jobId/jd/:jdId" element={<LegacyPageWrapper tab="jd_report" />} />
      <Route path="/prep/:interviewId" element={<LegacyPageWrapper tab="interview_prep_workspace" />} />
      <Route path="/review/:reviewId" element={<LegacyPageWrapper tab="interview_review_detail" />} />
      <Route path="/experiences" element={<LegacyPageWrapper tab="experiences" />} />
      <Route path="/experiences/:experienceId" element={<LegacyPageWrapper tab="experiences" />} />
      <Route path="/profile" element={<AppShell />}>
        <Route index element={<ProfilePage />} />
      </Route>
      <Route path="*" element={<LegacyPageWrapper />} />
    </Routes>
  );
};

export const AppRouter: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};