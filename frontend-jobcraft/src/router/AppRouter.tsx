import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../app/AppShell';
import { ProfilePage } from '../features/profile/ProfilePage';
import { WorkbenchPage } from '../features/jobs/pages/WorkbenchPage';
import { JobsPage } from '../features/jobs/pages/JobsPage';
import { JobWorkspacePage } from '../features/jobs/pages/JobWorkspacePage';
import { ExperiencesPage } from '../features/experiences/pages/ExperiencesPage';
import { InterviewPrepPage } from '../features/interview/pages/InterviewPrepPage';
import { InterviewReviewPage } from '../features/review/pages/InterviewReviewPage';
import { JdReportPage } from '../features/jd/pages/JdReportPage';
import { JdAnalysisCenterPage } from '../features/jd/pages/JdAnalysisCenterPage';
import { ResumeEditorPage } from '../features/resume/pages/ResumeEditorPage';
import { InterviewPrepCenterPage } from '../features/interview/pages/InterviewPrepCenterPage';
import { CreateInterviewPage } from '../features/interview/pages/CreateInterviewPage';
import { InterviewReviewCenterPage } from '../features/review/pages/InterviewReviewCenterPage';
import { CreateReviewPage } from '../features/review/pages/CreateReviewPage';

/**
 * 路由表（FE-ROUTE-02 / 组1-壳收口后）：
 * 所有 tab 均有 URL，全部走 AppShell 真实路由页（此前经 LegacyPageWrapper 的 6 条路由已收口为真实壳页）。
 * 中心 / 创建 / 简历编辑持有 URL（`/jd-analysis`、`/resume/:jobId`、`/interview/new/:jobId`、`/review/new/:jobId`），
 * 选中项经 URL 参数回填；遗留 MainLayout / LegacyPageWrapper / useSyncRouteTab 已移除（FE-ROUTE-04/05）。
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
      <Route path="/jd-analysis" element={<AppShell />}>
        <Route index element={<JdAnalysisCenterPage />} />
      </Route>
      <Route path="/resume" element={<AppShell />}>
        <Route index element={<ResumeEditorPage />} />
      </Route>
      <Route path="/resume/:jobId" element={<AppShell />}>
        <Route index element={<ResumeEditorPage />} />
      </Route>
      <Route path="/experiences" element={<AppShell />}>
        <Route index element={<ExperiencesPage />} />
      </Route>
      <Route path="/experiences/:experienceId" element={<AppShell />}>
        <Route index element={<ExperiencesPage />} />
      </Route>
      <Route path="/prep" element={<AppShell />}>
        <Route index element={<InterviewPrepCenterPage />} />
      </Route>
      <Route path="/prep/:interviewId" element={<AppShell />}>
        <Route index element={<InterviewPrepPage />} />
      </Route>
      <Route path="/interview/new" element={<AppShell />}>
        <Route index element={<CreateInterviewPage />} />
      </Route>
      <Route path="/interview/new/:jobId" element={<AppShell />}>
        <Route index element={<CreateInterviewPage />} />
      </Route>
      <Route path="/review" element={<AppShell />}>
        <Route index element={<InterviewReviewCenterPage />} />
      </Route>
      <Route path="/review/:interviewId" element={<AppShell />}>
        <Route index element={<InterviewReviewPage />} />
      </Route>
      <Route path="/review/new" element={<AppShell />}>
        <Route index element={<CreateReviewPage />} />
      </Route>
      <Route path="/review/new/:jobId" element={<AppShell />}>
        <Route index element={<CreateReviewPage />} />
      </Route>
      <Route path="/profile" element={<AppShell />}>
        <Route index element={<ProfilePage />} />
      </Route>

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
