import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LegacyPageWrapper } from './LegacyPageWrapper';
import { AppShell } from '../app/AppShell';
import { ProfilePage } from '../features/profile/ProfilePage';
import { WorkbenchPage } from '../features/jobs/pages/WorkbenchPage';
import { JobsPage } from '../features/jobs/pages/JobsPage';
import { JobWorkspacePage } from '../features/jobs/pages/JobWorkspacePage';
import { ExperiencesPage } from '../features/experiences/pages/ExperiencesPage';
import { InterviewPrepPage } from '../features/interview/pages/InterviewPrepPage';
import { InterviewReviewPage } from '../features/review/pages/InterviewReviewPage';
import { JdReportPage } from '../features/jd/pages/JdReportPage';

/**
 * 路由表：
 * - 已迁移 tab 走 AppShell 真实路由（独立页面 + URL 参数取参）。
 * - 尚未拆分的中心 / 创建 / 简历编辑走 LegacyPageWrapper（MainLayout 按 tab 渲染），但同样有 URL，
 *   保证 AppShell 内导航可达（FE-ROUTE-03）。
 * - tab → URL 映射的单一实现见 ./tabPaths.ts；遗留 navigateTo 触发的视图切换不改变 URL（过渡期行为）。
 */
export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/workbench" replace />} />
      <Route path="/workbench" element={<AppShell />}>
        <Route index element={<WorkbenchPage />} />
      </Route>
      <Route path="/jobs" element={<AppShell />}>
        <Route index element={<JobsPage />} />
      </Route>
      <Route path="/jobs/:jobId" element={<AppShell />}>
        <Route index element={<JobWorkspacePage />} />
      </Route>
      <Route path="/jobs/:jobId/jd/:jdId" element={<AppShell />}>
        <Route index element={<JdReportPage />} />
      </Route>
      <Route path="/jd-report/:jdId" element={<AppShell />}>
        <Route index element={<JdReportPage />} />
      </Route>
      <Route path="/experiences" element={<AppShell />}>
        <Route index element={<ExperiencesPage />} />
      </Route>
      <Route path="/experiences/:experienceId" element={<AppShell />}>
        <Route index element={<ExperiencesPage />} />
      </Route>
      <Route path="/prep/:interviewId" element={<AppShell />}>
        <Route index element={<InterviewPrepPage />} />
      </Route>
      <Route path="/review/:interviewId" element={<AppShell />}>
        <Route index element={<InterviewReviewPage />} />
      </Route>
      <Route path="/profile" element={<AppShell />}>
        <Route index element={<ProfilePage />} />
      </Route>

      <Route path="/jd-analysis" element={<LegacyPageWrapper tab="jd_analysis_center" />} />
      <Route path="/resume" element={<LegacyPageWrapper tab="resume_editor" />} />
      <Route path="/resume/:jobId" element={<LegacyPageWrapper tab="resume_editor" />} />
      <Route path="/prep" element={<LegacyPageWrapper tab="interview_prep_center" />} />
      <Route path="/interview/new" element={<LegacyPageWrapper tab="create_interview" />} />
      <Route path="/review" element={<LegacyPageWrapper tab="interview_review_center" />} />
      <Route path="/review/new" element={<LegacyPageWrapper tab="create_review" />} />

      <Route path="*" element={<Navigate to="/workbench" replace />} />
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
