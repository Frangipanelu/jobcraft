import React, { useState } from 'react';
import { Outlet, useOutletContext } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { TopHeader } from '../components/layout/TopHeader';
import { ToastContainer } from '../components/common/Toast';
import { NewJobModal } from '../components/jobs/NewJobModal';
import { MockInterviewModal } from '../components/interview/MockInterviewModal';
import { NewInterviewModal } from '../components/interview/NewInterviewModal';

/** AppShell 通过 <Outlet context> 下发给子页面的 modal openers（FE-ROUTE-02）。 */
export interface AppShellOutletContext {
  onOpenNewJob: () => void;
  onOpenMockInterview: (interviewId: string) => void;
  onOpenNewInterview: (mode?: 'standalone' | 'from-job', jobId?: string) => void;
}

export const useAppShellOutlet = () => useOutletContext<AppShellOutletContext>();

/**
 * 应用壳（迁移后真实路由页的统一宿主）。
 * 与遗留 MainLayout 并行存在：已迁移路由经本壳渲染，遗留路由仍经 MainLayout。
 * 页面通过 <Outlet/> 注入；全局 Modal 与 Toast 在此统一挂载。
 */
export const AppShell: React.FC = () => {
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

  const outletContext: AppShellOutletContext = {
    onOpenNewJob: () => setIsNewJobModalOpen(true),
    onOpenMockInterview: handleOpenMockInterview,
    onOpenNewInterview: handleOpenNewInterview,
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
          <Outlet context={outletContext} />
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