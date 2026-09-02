import React, { useState, useEffect, useCallback } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import { InterviewRoundType, InterviewFormat } from '../../types/jobcraft';
import {
  X,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  FileText,
  Upload,
  Loader2,
  Sparkles
} from 'lucide-react';

interface Props {
  isOpen: boolean;
  jobId?: string;
  mode: 'standalone' | 'from-job';
  onClose: () => void;
}

interface InterviewDraft {
  selectedJobId?: string;
  roundNumber?: number;
  roundName?: string;
  roundType?: InterviewRoundType;
  interviewTime?: string;
  interviewFormat?: InterviewFormat;
  platform?: string;
  interviewer?: string;
  resumeMode?: 'existing' | 'upload' | 'none';
  selectedResumeId?: string;
  supplementNotes?: string;
  remindUpload?: boolean;
}

const DRAFT_KEY = 'interviewDraft';

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

const aiGenerateItems = [
  '公司背景及最新动态研究',
  '面试类型策略分析与角色推断',
  '推荐经历与话术方向',
  '高频问题及优化答案',
  '模拟面试题目'
];

export const NewInterviewModal: React.FC<Props> = ({ isOpen, jobId, mode, onClose }) => {
  const {
    jobs,
    createInterview,
    createJob,
    createJDAnalysis,
    navigateTo,
    showToast
  } = useJobCraft();

  if (!isOpen) return null;

  const steps = mode === 'standalone' ? standaloneSteps : fromJobSteps;
  const maxStep = steps.length - 1;

  // Handle open JD analysis page
  const handleOpenJDAnalysis = () => {
    saveDraft();
    navigateTo('jd_analysis');
  };

  // Restore from localStorage draft
  const [draft] = useState<InterviewDraft | null>(() => {
    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        localStorage.removeItem(DRAFT_KEY);
        return JSON.parse(saved);
      }
    } catch {}
    return null;
  });

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
  const [resumeMode, setResumeMode] = useState<'existing' | 'upload' | 'none'>(
    draft?.resumeMode || 'none'
  );
  const [selectedResumeId, setSelectedResumeId] = useState<string>(
    draft?.selectedResumeId || ''
  );
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: string } | null>(null);

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
    const draftData: InterviewDraft = {
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
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draftData));
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
    localStorage.removeItem(DRAFT_KEY);
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

  // New job form state
  const [newJobCompany, setNewJobCompany] = useState('');
  const [newJobRole, setNewJobRole] = useState('');
  const [newJobJD, setNewJobJD] = useState('');
  const [showNewJobForm, setShowNewJobForm] = useState(false);

  // Handle create job - directly create in modal
  const handleCreateJob = () => {
    if (!newJobCompany.trim() || !newJobRole.trim()) {
      showToast({
        type: 'warning',
        title: '请填写完整信息',
        message: '公司名称和岗位名称不能为空'
      });
      return;
    }
    
    // Create job directly
    const newJobId = createJob({
      company: newJobCompany.trim(),
      role: newJobRole.trim(),
      status: 'pending'
    });
    
    // Create JD analysis record
    createJDAnalysis({
      company: newJobCompany.trim(),
      role: newJobRole.trim(),
      rawText: newJobJD.trim() || '待补充JD内容',
      jobId: newJobId
    });
    
    // Select the new job
    setSelectedJobId(newJobId);
    setShowNewJobForm(false);
    setNewJobCompany('');
    setNewJobRole('');
    setNewJobJD('');
    
    showToast({
      type: 'success',
      title: '岗位已创建',
      message: '已自动创建岗位和JD记录，请继续完善信息'
    });
  };

  // Handle finish
  const handleFinish = () => {
    setIsGenerating(true);
    setCurrentAiStep(0);
  };

  // AI generation animation
  useEffect(() => {
    if (!isGenerating || currentAiStep < 0) return;

    if (currentAiStep < aiGenerateItems.length) {
      const timer = setTimeout(() => {
        setCurrentAiStep((prev) => prev + 1);
      }, 600);
      return () => clearTimeout(timer);
    } else {
      // All done, create interview and close
      const timer = setTimeout(() => {
        const newId = createInterview({
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
        localStorage.removeItem(DRAFT_KEY);
        showToast({
          type: 'success',
          title: '面试准备已创建',
          message: 'AI 正在为你生成个性化准备方案...'
        });
        onClose();
        navigateTo('interview_prep_workspace', {
          jobId: selectedJobId || undefined,
          interviewId: newId
        });
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isGenerating, currentAiStep]);

  // Render step content
  const renderStepContent = () => {
    const actualStep = mode === 'standalone' ? step : step + 1;

    // Standalone Step 0: Job selection
    if (mode === 'standalone' && step === 0) {
      return (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
              步骤 1：关联岗位
            </h3>
            <p className="text-xs mt-1" style={{ color: '#737873' }}>
              选择要关联的岗位，或新建一个岗位。
            </p>
          </div>

          {/* Job dropdown */}
          <div>
            <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
              选择岗位
            </label>
            <select
              value={selectedJobId}
              onChange={(e) => {
                setSelectedJobId(e.target.value);
                setShowNewJobForm(false);
              }}
              className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
              style={{
                border: '1px solid #E4E5E0',
                background: '#FFFFFF',
                color: '#202421'
              }}
            >
              <option value="">请选择岗位</option>
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {job.company} · {job.role}
                </option>
              ))}
            </select>
          </div>

          {/* New job form */}
          {!showNewJobForm ? (
            <div className="flex gap-2">
              <button
                onClick={() => setShowNewJobForm(true)}
                className="flex-1 py-2.5 px-3.5 rounded-lg text-[13px] font-medium transition-all"
                style={{
                  border: '1px dashed #C8D8D1',
                  background: 'transparent',
                  color: '#3E6256'
                }}
              >
                + 新建岗位
              </button>
              <button
                onClick={handleOpenJDAnalysis}
                className="py-2.5 px-4 rounded-lg text-[13px] font-medium transition-all"
                style={{
                  border: '1px solid #3E6256',
                  background: '#FFFFFF',
                  color: '#3E6256'
                }}
              >
                去JD分析页面创建
              </button>
            </div>
          ) : (
            <div
              className="p-4 rounded-[10px] space-y-3"
              style={{
                border: '1.5px solid #3E6256',
                background: '#F5FAF7'
              }}
            >
              <div className="text-[13px] font-semibold" style={{ color: '#202421' }}>
                新建岗位
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input
                  type="text"
                  placeholder="公司名称"
                  value={newJobCompany}
                  onChange={(e) => setNewJobCompany(e.target.value)}
                  className="px-3 py-2 text-[13px] rounded-lg outline-none"
                  style={{
                    border: '1px solid #E4E5E0',
                    background: '#FFFFFF',
                    color: '#202421'
                  }}
                />
                <input
                  type="text"
                  placeholder="岗位名称"
                  value={newJobRole}
                  onChange={(e) => setNewJobRole(e.target.value)}
                  className="px-3 py-2 text-[13px] rounded-lg outline-none"
                  style={{
                    border: '1px solid #E4E5E0',
                    background: '#FFFFFF',
                    color: '#202421'
                  }}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                  JD详情（可选）
                </label>
                <textarea
                  rows={4}
                  placeholder="粘贴岗位描述JD内容，用于AI分析..."
                  value={newJobJD}
                  onChange={(e) => setNewJobJD(e.target.value)}
                  className="w-full px-3 py-2 text-[13px] rounded-lg outline-none resize-none"
                  style={{
                    border: '1px solid #E4E5E0',
                    background: '#FFFFFF',
                    color: '#202421',
                    lineHeight: 1.6
                  }}
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setShowNewJobForm(false);
                    setNewJobCompany('');
                    setNewJobRole('');
                    setNewJobJD('');
                  }}
                  className="flex-1 py-2 text-[13px] rounded-lg transition-all"
                  style={{
                    border: '1px solid #E4E5E0',
                    background: '#FFFFFF',
                    color: '#737873'
                  }}
                >
                  取消
                </button>
                <button
                  onClick={handleCreateJob}
                  className="flex-1 py-2 text-[13px] font-medium rounded-lg transition-all"
                  style={{
                    background: '#3E6256',
                    color: '#FFFFFF'
                  }}
                >
                  创建
                </button>
              </div>
            </div>
          )}
        </div>
      );
    }

    // Step 1/0: Interview details
    const detailsStep = mode === 'standalone' ? 1 : 0;
    if (step === detailsStep) {
      return (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
              步骤 {detailsStep + 1}：面试详情
            </h3>
            <p className="text-xs mt-1" style={{ color: '#737873' }}>
              填写本场面试的基本信息，AI 将据此生成准备方案。
            </p>
          </div>

          {/* Job display */}
          <div>
            <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
              关联岗位
            </label>
            <div
              className="px-3.5 py-2.5 rounded-lg text-[13.5px] font-medium"
              style={{
                background: '#F5FAF7',
                border: '1px solid #C8D8D1',
                color: '#3E6256'
              }}
            >
              {currentJob?.company || '待填写公司'} · {currentJob?.role || '待填写岗位'}
            </div>
          </div>

          {/* Grid 1 */}
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                面试轮次
              </label>
              <select
                value={roundNumber}
                onChange={(e) => {
                  const rNum = parseInt(e.target.value);
                  setRoundNumber(rNum);
                  setRoundName(
                    `第${rNum}面 · ${rNum === 1 ? '业务面' : rNum === 2 ? '技术/架构面' : rNum === 3 ? '总监面' : '终面'}`
                  );
                }}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              >
                <option value={1}>第1面</option>
                <option value={2}>第2面</option>
                <option value={3}>第3面</option>
                <option value={4}>HR面</option>
                <option value={5}>终面</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                面试类型
              </label>
              <select
                value={roundType}
                onChange={(e) => setRoundType(e.target.value as InterviewRoundType)}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              >
                <option value="business">业务面</option>
                <option value="tech">技术面</option>
                <option value="hr">HR面</option>
                <option value="product">产品面</option>
                <option value="comprehensive">总监面/终面</option>
              </select>
            </div>
          </div>

          {/* Grid 2 */}
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                面试日期
              </label>
              <input
                type="date"
                value={interviewTime.split(' ')[0] || '2026-09-02'}
                onChange={(e) =>
                  setInterviewTime(`${e.target.value} ${interviewTime.split(' ')[1] || '14:00'}`)
                }
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                面试时间
              </label>
              <input
                type="time"
                value={interviewTime.split(' ')[1] || '14:00'}
                onChange={(e) =>
                  setInterviewTime(`${interviewTime.split(' ')[0] || '2026-09-02'} ${e.target.value}`)
                }
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              />
            </div>
          </div>

          {/* Grid 3 */}
          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                面试形式
              </label>
              <select
                value={interviewFormat}
                onChange={(e) => setInterviewFormat(e.target.value as InterviewFormat)}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              >
                <option value="video">视频面试</option>
                <option value="phone">电话面试</option>
                <option value="onsite">现场面试</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
                平台（可选）
              </label>
              <input
                type="text"
                placeholder="如 Zoom, Teams, 牛客..."
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              />
            </div>
          </div>

          {/* Interviewer */}
          <div>
            <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
              面试官信息（可选）
            </label>
            <input
              type="text"
              placeholder="如：技术总监、产品 lead…"
              value={interviewer}
              onChange={(e) => setInterviewer(e.target.value)}
              className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
              style={{
                border: '1px solid #E4E5E0',
                background: '#FFFFFF',
                color: '#202421'
              }}
            />
          </div>
        </div>
      );
    }

    // Step 2/1: Resume
    const resumeStep = mode === 'standalone' ? 2 : 1;
    if (step === resumeStep) {
      return (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
              步骤 {resumeStep + 1}：关联简历
            </h3>
            <p className="text-xs mt-1" style={{ color: '#737873' }}>
              选择用于本次面试的简历，同一方向可沿用已有简历。
            </p>
          </div>

          {/* Mode switch */}
          <div className="flex gap-2">
            {(['existing', 'upload', 'none'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setResumeMode(mode)}
                className="px-3.5 py-1.5 text-[13px] rounded-lg transition-all"
                style={{
                  border: resumeMode === mode ? '1px solid #3E6256' : '1px solid #E4E5E0',
                  background: resumeMode === mode ? '#E5EEE9' : '#FFFFFF',
                  color: resumeMode === mode ? '#3E6256' : '#737873',
                  fontWeight: resumeMode === mode ? 500 : 400
                }}
              >
                {mode === 'existing' ? '从简历库选择' : mode === 'upload' ? '上传简历' : '暂不关联'}
              </button>
            ))}
          </div>

          {/* Existing resume */}
          {resumeMode === 'existing' && (
            <div className="space-y-3">
              <select
                value={selectedResumeId}
                onChange={(e) => setSelectedResumeId(e.target.value)}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              >
                <option value="">请选择简历</option>
                <option value="resume-1">字节跳动·AI产品经理 定制版 V2.1</option>
                <option value="resume-2">通用产品经理简历 V1.0</option>
                <option value="resume-3">腾讯·产品经理 定制版 V1.2</option>
              </select>

              {selectedResumeId && (
                <div
                  className="p-3 rounded-lg"
                  style={{ background: '#FAFAF8', border: '1px solid #E4E5E0' }}
                >
                  <div className="text-[13px] font-medium" style={{ color: '#202421' }}>
                    {selectedResumeId === 'resume-1'
                      ? '字节跳动·AI产品经理 定制版 V2.1'
                      : selectedResumeId === 'resume-2'
                      ? '通用产品经理简历 V1.0'
                      : '腾讯·产品经理 定制版 V1.2'}
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#A8ADA8' }}>
                    更新于 2026-08-28 · 关联岗位：字节跳动·AI产品经理
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Upload resume */}
          {resumeMode === 'upload' && (
            <div
              className="rounded-xl text-center transition-all"
              style={{
                border: isDragging ? '2px dashed #3E6256' : '2px dashed #D0D2CB',
                background: isDragging ? '#F5FAF7' : '#FAFAF8',
                padding: '36px 20px'
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const file = e.dataTransfer.files[0];
                if (file) {
                  const size = file.size < 1024 * 1024
                    ? `${(file.size / 1024).toFixed(1)} KB`
                    : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
                  setUploadedFile({ name: file.name, size });
                }
              }}
            >
              <div className="text-4xl mb-2">📄</div>
              <div className="text-sm font-semibold mb-1" style={{ color: '#202421' }}>
                拖入简历文件
              </div>
              <div className="text-xs mb-3" style={{ color: '#A8ADA8' }}>
                支持 DOCX / PDF / TXT
              </div>
              <button
                type="button"
                className="px-4 py-[7px] text-[13px] rounded-lg"
                style={{
                  border: '1px solid #C8D8D1',
                  background: '#FFFFFF',
                  color: '#3E6256'
                }}
              >
                浏览文件
              </button>

              {uploadedFile && (
                <div className="mt-3 p-2 rounded-lg" style={{ background: '#F5FAF7' }}>
                  <div className="text-[13px] font-medium" style={{ color: '#202421' }}>
                    {uploadedFile.name}
                  </div>
                  <div className="text-xs" style={{ color: '#A8ADA8' }}>
                    {uploadedFile.size}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* No resume */}
          {resumeMode === 'none' && (
            <div className="py-8 text-center">
              <p className="text-[13px]" style={{ color: '#A8ADA8' }}>
                可以稍后在面试准备工作中关联简历
              </p>
            </div>
          )}
        </div>
      );
    }

    // Step 3/2: Additional info
    const additionalStep = mode === 'standalone' ? 3 : 2;
    if (step === additionalStep) {
      return (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
              步骤 {additionalStep + 1}：补充信息
            </h3>
            <p className="text-xs mt-1" style={{ color: '#737873' }}>
              补充额外背景信息，AI 将生成更精准的准备方案。
            </p>
          </div>

          {/* Supplement notes */}
          <div>
            <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
              补充说明（可选）
            </label>
            <textarea
              rows={5}
              placeholder="例如：特别关注哪方面的准备？有哪些已知信息？"
              value={supplementNotes}
              onChange={(e) => setSupplementNotes(e.target.value)}
              className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none resize-y"
              style={{
                border: '1px solid #E4E5E0',
                background: '#FFFFFF',
                color: '#202421',
                lineHeight: 1.6
              }}
            />
          </div>

          {/* Checkbox */}
          <label
            className="flex items-center gap-2.5 p-3.5 rounded-lg cursor-pointer"
            style={{ background: '#FAFAF8', border: '1px solid #E4E5E0' }}
          >
            <input
              type="checkbox"
              checked={remindUpload}
              onChange={(e) => setRemindUpload(e.target.checked)}
              className="w-3.5 h-3.5"
              style={{ accentColor: '#3E6256' }}
            />
            <span className="text-[13.5px]" style={{ color: '#202421' }}>
              面试结束后提醒我上传录音，用于复盘分析
            </span>
          </label>

          {/* AI Preview */}
          <div
            className="rounded-[10px]"
            style={{
              background: '#F5FAF7',
              border: '1px solid #C8D8D1',
              padding: '14px 16px',
              marginTop: '20px'
            }}
          >
            <div
              className="text-xs font-semibold mb-2"
              style={{ color: '#3E6256' }}
            >
              AI 将为你生成：
            </div>
            <div className="space-y-1">
              {aiGenerateItems.map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle2
                    className="w-3.5 h-3.5 shrink-0"
                    style={{ color: '#3E6256' }}
                  />
                  <span className="text-xs" style={{ color: '#4A6559' }}>
                    {item}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Loading Animation */}
          {isGenerating && currentAiStep >= 0 && (
            <div
              className="rounded-[10px] mt-4"
              style={{
                background: '#F5FAF7',
                border: '1px solid #C8D8D1',
                padding: '14px 16px'
              }}
            >
              <div
                className="text-xs font-semibold mb-3 flex items-center gap-1.5"
                style={{ color: '#3E6256' }}
              >
                <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                AI 正在为你生成...
              </div>
              <div className="space-y-2">
                {aiGenerateItems.map((item, i) => (
                  <div key={item} className="flex items-center gap-2 text-xs">
                    {i < currentAiStep ? (
                      <CheckCircle2 className="w-3.5 h-3.5 shrink-0" style={{ color: '#3E6256' }} />
                    ) : i === currentAiStep ? (
                      <Loader2 className="w-3.5 h-3.5 shrink-0 animate-spin" style={{ color: '#3E6256' }} />
                    ) : (
                      <div
                        className="w-3.5 h-3.5 rounded-full shrink-0"
                        style={{ border: '1.5px solid #D0D2CB' }}
                      />
                    )}
                    <span style={{ color: i <= currentAiStep ? '#202421' : '#A8ADA8' }}>
                      {item}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
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
