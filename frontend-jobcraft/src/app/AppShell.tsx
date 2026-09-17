import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { TopHeader } from '../components/layout/TopHeader';
import { ToastContainer } from '../components/common/Toast';
import { NewJobModal } from '../components/jobs/NewJobModal';
import { MockInterviewModal } from '../components/interview/MockInterviewModal';
import { NewInterviewModal } from '../components/interview/NewInterviewModal';

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
          <Outlet />
        </main>
      </div>

      <NewJobModal
        isOpen={isNewJobModalOpen}
        onClose={() => setIsNewJobModalOpen(false)}
      />

      <MockInterviewModal
        isOpen={!!mockInterviewId}
        onClose={() => setMockInterviewId(null)}
        interviewId={mockInterviewId || undefined}
      />

      <NewInterviewModal
        isOpen={isNewInterviewModalOpen}
        onClose={() => setIsNewInterviewModalOpen(false)}
        mode={newInterviewModalMode}
        jobId={newInterviewModalJobId}
      />

      <ToastContainer />
    </div>
  );
};