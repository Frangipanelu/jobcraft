import React, { useState, useEffect, useCallback } from 'react';
import { useToastActions } from '../../context/JobCraftContext';
import { useTabNavigate } from '../../router/tabPaths';
import { useCreateInterviewMutation } from '../../features/interview/hooks';
import { useJobsQuery } from '../../features/jobs/hooks';
import { InterviewRoundType, InterviewFormat, InterviewDraft } from '../../types/jobcraft';
import { JobSelectionStep } from './JobSelectionStep';
import { InterviewDetailsStep } from './InterviewDetailsStep';
import { ResumeStep, ResumeMode } from './ResumeStep';
import { AdditionalInfoStep, AI_GENERATE_ITEMS } from './AdditionalInfoStep';
import {
  loadInterviewModalDraft,
  saveInterviewModalDraft,
  clearInterviewModalDraft,
} from './interviewModalDraft';
import {
  X,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Loader2
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  jobId?: string;
  mode: 'standalone' | 'from-job';
  onClose: () => void;
}

const standaloneSteps = [
  { num: 0, label: '关联岗位' },
  { num: 1, label: '面试详情' },
  { num: 2, label: '关联简历' },
  { num: 3, label: '补充信息' }
];

const fromJobSteps = [
  { num: 0, label: '面试详情' },
  { num: 1, label: '关联简历' },
  { num: 2, label: '补充信息' }
];

export const NewInterviewModal: React.FC<Props> = ({ isOpen, jobId, mode, onClose }) => {
  const { showToast } = useToastActions();
  const { data: jobs = [] } = useJobsQuery();
  const createInterview = useCreateInterviewMutation();
  const go = useTabNavigate();

  if (!isOpen) return null;

  const steps = mode === 'standalone' ? standaloneSteps : fromJobSteps;
  const maxStep = steps.length - 1;

  // Handle open JD analysis page
  const handleOpenJDAnalysis = () => {
    saveDraft();
    go('jd_analysis');
  };

  // Restore from localStorage draft
  const [draft] = useState<Partial<InterviewDraft> | null>(() => loadInterviewModalDraft());

  // State
  const [step, setStep] = useState<number>(
    draft?.selectedJobId && mode === 'standalone' ? 1 : 0
  );

  // Step 0 - Job selection (standalone only)
  const [selectedJobId, setSelectedJobId] = useState<string>(
    draft?.selectedJobId || jobId || ''
  );

  // Step 1/0 - Interview details
  const [roundNumber, setRoundNumber] = useState<number>(draft?.roundNumber || 2);
  const [roundName, setRoundName] = useState<string>(
    draft?.roundName || '第2面 · 技术/架构面'
  );
  const [roundType, setRoundType] = useState<InterviewRoundType>(
    draft?.roundType || 'tech'
  );
  const [interviewTime, setInterviewTime] = useState<string>(
    draft?.interviewTime || '2026-09-02 14:00'
  );
  const [interviewFormat, setInterviewFormat] = useState<InterviewFormat>(
    draft?.interviewFormat || 'video'
  );
  const [platform, setPlatform] = useState<string>(draft?.platform || '');
  const [interviewer, setInterviewer] = useState<string>(draft?.interviewer || '');

  // Step 2/1 - Resume
  const [resumeMode, setResumeMode] = useState<ResumeMode>(
    draft?.resumeMode || 'none'
  );
  const [selectedResumeId, setSelectedResumeId] = useState<string>(
    draft?.selectedResumeId || ''
  );

  // Step 3/2 - Additional info
  const [supplementNotes, setSupplementNotes] = useState<string>(
    draft?.supplementNotes || ''
  );
  const [remindUpload, setRemindUpload] = useState<boolean>(
    draft?.remindUpload || false
  );

  // Loading state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentAiStep, setCurrentAiStep] = useState(-1);

  const currentJob = jobs.find((j) => j.id === selectedJobId);

  // Can proceed
  const canNext = () => {
    if (mode === 'standalone' && step === 0) {
      return !!selectedJobId;
    }
    return true;
  };

  // Save draft
  const saveDraft = useCallback(() => {
    const draftData: Partial<InterviewDraft> = {
      selectedJobId,
      roundNumber,
      roundName,
      roundType,
      interviewTime,
      interviewFormat,
      platform,
      interviewer,
      resumeMode,
      selectedResumeId,
      supplementNotes,
      remindUpload
    };
    saveInterviewModalDraft(draftData);
  }, [
    selectedJobId,
    roundNumber,
    roundName,
    roundType,
    interviewTime,
    interviewFormat,
    platform,
    interviewer,
    resumeMode,
    selectedResumeId,
    supplementNotes,
    remindUpload
  ]);

  // Handle close
  const handleClose = () => {
    clearInterviewModalDraft();
    onClose();
  };

  // Handle back
  const handleBack = () => {
    if (step === 0) {
      handleClose();
    } else {
      setStep((s) => s - 1);
    }
  };

  // Handle next
  const handleNext = () => {
    if (step < maxStep) {
      setStep((s) => s + 1);
    }
  };

  // Handle finish
  const handleFinish = () => {
    setIsGenerating(true);
    setCurrentAiStep(0);
  };

  // AI generation animation
  useEffect(() => {
    if (!isGenerating || currentAiStep < 0) return;

    if (currentAiStep < AI_GENERATE_ITEMS.length) {
      const timer = setTimeout(() => {
        setCurrentAiStep((prev) => prev + 1);
      }, 600);
      return () => clearTimeout(timer);
    } else {
      // All done, create interview (real backend generation) and close
      const timer = setTimeout(async () => {
        try {
          const newInterview = await createInterview.mutateAsync({
            jobId: selectedJobId || undefined,
            company: currentJob?.company || '待填写公司',
            role: currentJob?.role || '待填写岗位',
            roundNumber,
            roundName,
            roundType,
            time: interviewTime,
            format: interviewFormat,
            interviewer,
            supplementNotes
          });
          clearInterviewModalDraft();
          showToast({
            type: 'success',
            title: '面试准备已创建',
            message: 'AI 已生成个性化准备方案'
          });
          onClose();
          go('interview_prep_workspace', {
            jobId: selectedJobId || undefined,
            interviewId: newInterview.id
          });
        } catch (err) {
          setIsGenerating(false);
          setCurrentAiStep(-1);
          showToast({
            type: 'error',
            title: '生成面试准备失败',
            message: (err as Error).message || '请稍后重试'
          });
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isGenerating, currentAiStep]);

  // Render step content
  const renderStepContent = () => {
    // Standalone Step 0: Job selection
    if (mode === 'standalone' && step === 0) {
      return (
        <JobSelectionStep
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelectJob={setSelectedJobId}
          onOpenJDAnalysis={handleOpenJDAnalysis}
        />
      );
    }

    // Step 1/0: Interview details
    const detailsStep = mode === 'standalone' ? 1 : 0;
    if (step === detailsStep) {
      return (
        <InterviewDetailsStep
          stepNumber={detailsStep + 1}
          currentJob={currentJob}
          roundNumber={roundNumber}
          roundType={roundType}
          interviewTime={interviewTime}
          interviewFormat={interviewFormat}
          platform={platform}
          interviewer={interviewer}
          onRoundChange={(num, name) => {
            setRoundNumber(num);
            setRoundName(name);
          }}
          onRoundTypeChange={setRoundType}
          onTimeChange={setInterviewTime}
          onFormatChange={setInterviewFormat}
          onPlatformChange={setPlatform}
          onInterviewerChange={setInterviewer}
        />
      );
    }

    // Step 2/1: Resume
    const resumeStep = mode === 'standalone' ? 2 : 1;
    if (step === resumeStep) {
      return (
        <ResumeStep
          stepNumber={resumeStep + 1}
          resumeMode={resumeMode}
          onResumeModeChange={setResumeMode}
          selectedResumeId={selectedResumeId}
          onSelectedResumeIdChange={setSelectedResumeId}
        />
      );
    }

    // Step 3/2: Additional info
    const additionalStep = mode === 'standalone' ? 3 : 2;
    if (step === additionalStep) {
      return (
        <AdditionalInfoStep
          stepNumber={additionalStep + 1}
          supplementNotes={supplementNotes}
          remindUpload={remindUpload}
          isGenerating={isGenerating}
          currentAiStep={currentAiStep}
          onSupplementNotesChange={setSupplementNotes}
          onRemindUploadChange={setRemindUpload}
        />
      );
    }

    return null;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop - adaptive to screen */}
      <div
        className="absolute inset-0"
        style={{
          background: 'rgba(15, 20, 18, 0.55)',
          backdropFilter: 'blur(4px)'
        }}
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        className="relative w-full mx-4 flex items-center justify-center"
        style={{
          maxWidth: '680px'
        }}
      >
        <div
          className="w-full rounded-2xl overflow-hidden"
          style={{
            maxHeight: '85vh',
            background: '#FFFFFF',
            border: '1px solid #E4E5E0',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
            animation: 'modalFadeIn 200ms ease-out'
          }}
        >
        <style>{`
          @keyframes modalFadeIn {
            from {
              opacity: 0;
              transform: scale(0.97);
            }
            to {
              opacity: 1;
              transform: scale(1);
            }
          }
        `}</style>

        {/* Header */}
        <div
          className="flex items-center justify-between sticky top-0 z-10"
          style={{ padding: '20px 28px 0', background: '#FFFFFF' }}
        >
          <div className="flex items-center gap-3">
            <button
              onClick={handleClose}
              className="w-4 h-4 flex items-center justify-center cursor-pointer transition-colors"
              style={{ color: '#A8ADA8' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#202421')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#A8ADA8')}
            >
              <X className="w-4 h-4" />
            </button>
            <h2 className="text-lg font-bold" style={{ color: '#202421' }}>
              新建面试准备
            </h2>
          </div>
          <span className="text-xs" style={{ color: '#A8ADA8' }}>
            步骤 {step + 1} / {steps.length}
          </span>
        </div>

        {/* Step indicator */}
        <div
          className="flex items-center"
          style={{ padding: '16px 28px 0', marginBottom: '20px' }}
        >
          {steps.map((s, i) => (
            <React.Fragment key={s.num}>
              <div className="flex flex-col items-center">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-[13px] font-semibold"
                  style={{
                    background:
                      step > s.num ? '#3E6256' : step === s.num ? '#202421' : '#F0F0EC',
                    color:
                      step >= s.num ? '#FFFFFF' : '#A8ADA8'
                  }}
                >
                  {step > s.num ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : (
                    s.num + 1
                  )}
                </div>
                <span
                  className="text-[11px] mt-1.5 whitespace-nowrap"
                  style={{
                    color: step === s.num ? '#202421' : '#A8ADA8',
                    fontWeight: step === s.num ? 600 : 400
                  }}
                >
                  {s.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div
                  className="flex-1 mx-2"
                  style={{
                    height: '1.5px',
                    marginTop: '16px',
                    background: step > s.num ? '#3E6256' : '#E4E5E0'
                  }}
                />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Content */}
        <div
          className="overflow-y-auto"
          style={{ padding: '0 28px', maxHeight: 'calc(85vh - 200px)' }}
        >
          {renderStepContent()}
        </div>

        {/* Footer */}
        <div
          className="sticky bottom-0 flex items-center justify-between"
          style={{
            padding: '16px 28px',
            background: '#FFFFFF',
            borderTop: '1px solid #F0F0EC'
          }}
        >
          <span className="text-xs" style={{ color: '#A8ADA8' }}>
            第 {step + 1} 步 / 共 {steps.length} 步
          </span>

          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={handleBack}
                className="flex items-center gap-1.5 px-4 py-2 text-[13px] rounded-lg transition-all"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#737873'
                }}
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                上一步
              </button>
            )}

            {step < maxStep ? (
              <button
                onClick={handleNext}
                disabled={!canNext()}
                className="flex items-center gap-1.5 px-5 py-2 text-[13.5px] font-medium rounded-lg transition-all"
                style={{
                  background: canNext() ? '#3E6256' : '#D0D2CB',
                  color: '#FFFFFF',
                  cursor: canNext() ? 'pointer' : 'not-allowed'
                }}
              >
                下一步
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                onClick={handleFinish}
                disabled={isGenerating}
                className="flex items-center gap-1.5 px-5 py-2 text-[13.5px] font-semibold rounded-lg transition-all"
                style={{
                  background: isGenerating ? '#D0D2CB' : '#3E6256',
                  color: '#FFFFFF',
                  cursor: isGenerating ? 'not-allowed' : 'pointer'
                }}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    生成中...
                  </>
                ) : (
                  <>
                    创建面试并生成准备方案
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
        </div>
      </div>
    </div>
  );
};