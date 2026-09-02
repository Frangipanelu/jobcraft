import React, { useState } from 'react';
import { JobCraftProvider, useJobCraft } from './context/JobCraftContext';
import { Sidebar } from './components/layout/Sidebar';
import { TopHeader } from './components/layout/TopHeader';
import { ToastContainer } from './components/common/Toast';

// Views
import { WorkbenchView } from './components/workbench/WorkbenchView';
import { ExperiencesView } from './components/experiences/ExperiencesView';
import { JobsListView } from './components/jobs/JobsListView';
import { JobWorkspaceView } from './components/jobs/JobWorkspaceView';
import { JDAnalysisCenterView } from './components/jd/JDAnalysisCenterView';
import { JDReportDetailView } from './components/jd/JDReportDetailView';
import { ResumeEditorView } from './components/resume/ResumeEditorView';
import { InterviewPrepCenterView } from './components/interview/InterviewPrepCenterView';
import { InterviewPrepWorkspaceView } from './components/interview/InterviewPrepWorkspaceView';
import { InterviewReviewCenterView } from './components/review/InterviewReviewCenterView';
import { InterviewReviewDetailView } from './components/review/InterviewReviewDetailView';
import { UserProfileView } from './components/user/UserProfileView';

// Pages
import { CreateInterview } from './pages/CreateInterview';
import { CreateReview } from './pages/CreateReview';
import { NewInterviewPrep } from './pages/NewInterviewPrep';
import { NewReview } from './pages/NewReview';
import { AuthPage } from './pages/AuthPage';

// Modals
import { NewJobModal } from './components/jobs/NewJobModal';
import { MockInterviewModal } from './components/interview/MockInterviewModal';
import { NewInterviewModal } from './components/interview/NewInterviewModal';

const MainLayout: React.FC = () => {
  const {
    currentTab,
    selectedJobId,
    selectedInterviewId,
    selectedJDId,
    selectedExperienceId,
    navigateTo
  } = useJobCraft();

  // Modals state
  const [isNewJobModalOpen, setIsNewJobModalOpen] = useState(false);
  const [mockInterviewId, setMockInterviewId] = useState<string | null>(null);
  const [isNewInterviewModalOpen, setIsNewInterviewModalOpen] = useState(false);
  const [newInterviewModalMode, setNewInterviewModalMode] = useState<'standalone' | 'from-job'>('standalone');
  const [newInterviewModalJobId, setNewInterviewModalJobId] = useState<string | undefined>(undefined);

  const handleOpenMockInterview = (interviewId: string) => {
    setMockInterviewId(interviewId);
  };

  const handleCloseMockInterview = () => {
    setMockInterviewId(null);
  };

  const handleOpenNewInterview = (mode: 'standalone' | 'from-job' = 'standalone', jobId?: string) => {
    setNewInterviewModalMode(mode);
    setNewInterviewModalJobId(jobId);
    setIsNewInterviewModalOpen(true);
  };

  const handleCloseNewInterview = () => {
    setIsNewInterviewModalOpen(false);
    setNewInterviewModalJobId(undefined);
  };

  const renderActiveView = () => {
    switch (currentTab) {
      case 'workbench':
        return (
          <WorkbenchView
            onOpenNewJob={() => setIsNewJobModalOpen(true)}
          />
        );

      case 'experiences':
        return <ExperiencesView initialSelectedExpId={selectedExperienceId || undefined} />;

      case 'jobs':
        return <JobsListView onOpenNewJob={() => setIsNewJobModalOpen(true)} />;

      case 'job_workspace':
        return (
          <JobWorkspaceView
            onOpenMockInterview={handleOpenMockInterview}
            onOpenNewInterview={(jobId) => handleOpenNewInterview('from-job', jobId)}
          />
        );

      case 'jd_analysis':
      case 'jd_analysis_center':
        return <JDAnalysisCenterView />;

      case 'jd_report':
        return <JDReportDetailView analysisId={selectedJDId} />;

      case 'resume_editor':
        return <ResumeEditorView jobId={selectedJobId} />;

      case 'interview_prep_center':
        return (
          <InterviewPrepCenterView
            onOpenMockInterview={handleOpenMockInterview}
            onOpenNewInterview={() => navigateTo('create_interview')}
          />
        );

      case 'interview_prep_workspace':
        return (
          <InterviewPrepWorkspaceView
            interviewId={selectedInterviewId}
            onOpenMockInterview={handleOpenMockInterview}
            onOpenNewInterview={() => navigateTo('create_interview')}
          />
        );

      case 'create_interview':
        return <CreateInterview />;

      case 'interview_review_center':
        return <InterviewReviewCenterView />;

      case 'create_review':
        return <CreateReview />;

      case 'interview_review_detail':
        return (
          <InterviewReviewDetailView
            interviewId={selectedInterviewId}
          />
        );

      case 'user_profile':
        return <UserProfileView />;

      default:
        return (
          <WorkbenchView
            onOpenNewJob={() => setIsNewJobModalOpen(true)}
          />
        );
    }
  };

  return (
    <div className="flex h-screen bg-page font-sans text-ink antialiased overflow-hidden selection:bg-sage-soft selection:text-sage">
      <Sidebar
        onOpenNewJob={() => setIsNewJobModalOpen(true)}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopHeader
          onOpenNewJob={() => setIsNewJobModalOpen(true)}
        />

        <main className="flex-1 overflow-y-auto custom-scrollbar">
          {renderActiveView()}
        </main>
      </div>

      <NewJobModal
        isOpen={isNewJobModalOpen}
        onClose={() => setIsNewJobModalOpen(false)}
      />

      <MockInterviewModal
        isOpen={!!mockInterviewId}
        onClose={handleCloseMockInterview}
        interviewId={mockInterviewId || undefined}
      />

      <NewInterviewModal
        isOpen={isNewInterviewModalOpen}
        onClose={handleCloseNewInterview}
        mode={newInterviewModalMode}
        jobId={newInterviewModalJobId}
      />

      <ToastContainer />
    </div>
  );
};

export default function App() {
  return (
    <JobCraftProvider>
      <AppShell />
    </JobCraftProvider>
  );
}

const AppShell: React.FC = () => {
  const { isAuthenticated, isInitialLoaded, isLoading } = useJobCraft();

  // 初次启动：正在确认登录状态
  if (isLoading && !isInitialLoaded) {
    return (
      <div className="flex h-screen bg-page items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sage border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted">正在进入 JobCraft…</p>
        </div>
      </div>
    );
  }

  // 未登录：进入登录/注册页
  if (!isAuthenticated) {
    return <AuthPage />;
  }

  return <MainLayout />;
};
