import React, { useState, useEffect, useRef } from 'react';
import { useJobCraft } from '../context/JobCraftContext';
import { InterviewRoundType, InterviewFormat } from '../types/jobcraft';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  Upload,
  Settings,
  Sparkles,
  CheckCircle2
} from 'lucide-react';

const steps = [
  { num: 0, label: '关联岗位' },
  { num: 1, label: '应聘信息' },
  { num: 2, label: '面试信息' },
  { num: 3, label: '补充信息' }
];

const interviewPrepAiSteps = [
  '正在分析岗位画像与考点...',
  '检索个人经历与项目沉淀...',
  '推演面试官提问重心与策略...',
  '生成高频考点攻防方案...',
  '生成模拟面试预测题库...',
  '面试准备方案生成中...'
];

export const CreateInterview: React.FC = () => {
  const {
    jobs,
    selectedJobId: contextSelectedJobId,
    historicalResumes,
    addHistoricalResume,
    createInterview,
    navigateTo,
    interviewDraft,
    saveInterviewDraft,
    clearInterviewDraft,
    setJdAnalysisReturnTarget,
    showToast
  } = useJobCraft();

  // Filter jobs in "interview prep" stage
  const prepStageJobs = jobs.filter(
    (j) =>
      j.status === 'interviewing' ||
      j.status === 'pending' ||
      j.steps.prepStage === 'in_progress' ||
      j.currentStage.includes('准备') ||
      j.currentStage.includes('面')
  );

  // Restore draft or initial value
  const initialJobId =
    interviewDraft?.selectedJobId ||
    (contextSelectedJobId && jobs.some((j) => j.id === contextSelectedJobId)
      ? contextSelectedJobId
      : prepStageJobs[0]?.id || jobs[0]?.id || '');

  const [step, setStep] = useState<number>(interviewDraft?.step ? interviewDraft.step - 1 : 0);
  const [selectedJobId, setSelectedJobId] = useState<string>(initialJobId);

  // Step 1: Application Info
  const [selectedResumeId, setSelectedResumeId] = useState<string>(
    historicalResumes.find((r) => r.isDefault)?.id || historicalResumes[0]?.id || 'hr-1'
  );
  const [customUploadedFileName, setCustomUploadedFileName] = useState<string | null>(null);
  const [coverLetter, setCoverLetter] = useState(interviewDraft?.coverLetter || '');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 2: Interview Info
  const [roundNumber, setRoundNumber] = useState<number>(interviewDraft?.roundNumber || 2);
  const [roundName, setRoundName] = useState<string>(
    interviewDraft?.roundName || '第2面 · 业务与技术交叉面'
  );
  const [roundType, setRoundType] = useState<InterviewRoundType>(
    interviewDraft?.roundType || 'tech'
  );
  const [interviewDate, setInterviewDate] = useState<string>(
    interviewDraft?.interviewTime ? interviewDraft.interviewTime.split(' ')[0] : '2026-09-03'
  );
  const [interviewTimeHour, setInterviewTimeHour] = useState<string>(
    interviewDraft?.interviewTime ? interviewDraft.interviewTime.split(' ')[1] || '14:00' : '14:00'
  );
  const [interviewFormat, setInterviewFormat] = useState<InterviewFormat>(
    interviewDraft?.interviewFormat || 'video'
  );
  const [platform, setPlatform] = useState<string>(interviewDraft?.platform || '腾讯会议 / 飞书会议');
  const [interviewer, setInterviewer] = useState<string>(
    interviewDraft?.interviewer || '业务技术负责人 / 交叉面试官'
  );

  // Step 3: Supplement Info
  const [supplementNotes, setSupplementNotes] = useState<string>(
    interviewDraft?.supplementNotes || '重点准备大模型评测体系、算法协同机制与量化业务产出。'
  );
  const [remindUpload, setRemindUpload] = useState<boolean>(
    interviewDraft?.remindUpload !== undefined ? interviewDraft.remindUpload : true
  );

  // AI Generation Loading State (Separate Page)
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentAiStep, setCurrentAiStep] = useState(0);

  const selectedJob = jobs.find((j) => j.id === selectedJobId);

  // Auto-sync round name when round number changes
  const handleRoundNumberChange = (num: number) => {
    setRoundNumber(num);
    if (num === 1) {
      setRoundName('第1面 · 业务初面');
      setRoundType('business');
    } else if (num === 2) {
      setRoundName('第2面 · 业务与技术交叉面');
      setRoundType('tech');
    } else if (num === 3) {
      setRoundName('第3面 · 总监/业务负责人面');
      setRoundType('comprehensive');
    } else if (num === 4) {
      setRoundName('第4面 · HRBP 综合面');
      setRoundType('hr');
    } else {
      setRoundName(`第${num}面 · 终面`);
      setRoundType('comprehensive');
    }
  };

  const canNext = () => {
    if (step === 0) {
      return !!selectedJobId;
    }
    if (step === 1) {
      return !!selectedResumeId;
    }
    return true;
  };

  const handleBack = () => {
    if (step === 0) {
      navigateTo('interview_prep_center');
    } else {
      setStep((s) => s - 1);
    }
  };

  const handleNext = () => {
    if (step < 3 && canNext()) {
      setStep((s) => s + 1);
    }
  };

  // Jump to JD analysis to create new JD and return later
  const handleGoToJDAnalysis = () => {
    saveInterviewDraft({
      step: 1,
      selectedJobId,
      isCustomJob: false,
      customCompany: '',
      customRole: '',
      roundNumber,
      roundName,
      roundType,
      interviewTime: `${interviewDate} ${interviewTimeHour}`,
      interviewFormat,
      platform,
      interviewer,
      supplementNotes,
      remindUpload,
      resumeVersion: 'ai',
      coverLetter
    });
    setJdAnalysisReturnTarget('create_interview');
    showToast({
      type: 'info',
      title: '前往 JD 分析',
      message: '创建并研判完成后，可直接带入新建岗位返回此处。'
    });
    navigateTo('jd_analysis_center');
  };

  // Handle local file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const newResumeId = `hr-upload-${Date.now()}`;
      addHistoricalResume({
        name: file.name,
        fileSize: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        isDefault: false,
        parsedExperiencesCount: 4,
        format: file.name.endsWith('.docx') ? 'docx' : 'pdf',
        tags: ['本地上传', '最新简历']
      });
      setCustomUploadedFileName(file.name);
      setSelectedResumeId(newResumeId);
      showToast({
        type: 'success',
        title: '简历上传成功',
        message: `已自动选择「${file.name}」用于本场面试推演。`
      });
    }
  };

  const handleSimulatedDrop = () => {
    const defaultUploadedName = `${selectedJob?.company || '定制'}_AI产品专家_2026最新简历.pdf`;
    const newResumeId = `hr-upload-${Date.now()}`;
    addHistoricalResume({
      name: defaultUploadedName,
      fileSize: '1.6 MB',
      isDefault: false,
      parsedExperiencesCount: 5,
      format: 'pdf',
      tags: ['本地上传', '最新简历', 'STAR已对齐']
    });
    setCustomUploadedFileName(defaultUploadedName);
    setSelectedResumeId(newResumeId);
    showToast({
      type: 'success',
      title: '简历已上传并解析',
      message: `已自动选择「${defaultUploadedName}」。`
    });
  };

  // Trigger AI generation
  const handleFinish = () => {
    setIsGenerating(true);
    setCurrentAiStep(0);
  };

  // Step progression animation (600ms per step)
  useEffect(() => {
    if (!isGenerating) return;

    if (currentAiStep < interviewPrepAiSteps.length) {
      const timer = setTimeout(() => {
        setCurrentAiStep((prev) => prev + 1);
      }, 650);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        const fullTime = `${interviewDate} ${interviewTimeHour}`;
        const newIntId = createInterview({
          jobId: selectedJobId || undefined,
          company: selectedJob?.company || '目标企业',
          role: selectedJob?.role || '目标岗位',
          roundNumber,
          roundName,
          roundType,
          time: fullTime,
          format: interviewFormat,
          interviewer,
          supplementNotes
        });

        clearInterviewDraft();
        showToast({
          type: 'success',
          title: '面试准备方案已生成',
          message: `已为「${selectedJob?.company || '目标企业'} ${roundName}」生成攻防策略与高频题库。`
        });
        navigateTo('interview_prep_workspace', { interviewId: newIntId });
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isGenerating, currentAiStep]);

  // If in AI generation mode, render standalone loading page (as in image 3)
  if (isGenerating) {
    return (
      <div className="min-h-full bg-page flex flex-col items-center justify-center px-4 py-16 animate-in fade-in duration-300">
        <div className="w-full max-w-xl bg-white rounded-2xl border border-edge p-8 sm:p-10 shadow-sm text-center">
          {/* Top Gear Animation */}
          <div className="w-14 h-14 rounded-full bg-[#f2f3ef] flex items-center justify-center mx-auto mb-4 text-ink shadow-2xs">
            <Settings className="w-6 h-6 animate-spin" style={{ animationDuration: '3.5s' }} />
          </div>

          {/* Titles */}
          <h2 className="text-xl font-bold text-ink mb-1 tracking-tight">AI 正在生成个性化准备方案</h2>
          <p className="text-xs text-muted mb-6">请稍候，这通常需要 10–30 秒</p>

          {/* Checklist container */}
          <div className="bg-[#f8f9f7] rounded-xl p-5 sm:p-6 border border-edge/60 text-left space-y-3.5">
            {interviewPrepAiSteps.map((stepName, idx) => {
              const isDone = currentAiStep > idx;
              const isCurrent = currentAiStep === idx;
              return (
                <div key={stepName} className="flex items-center gap-3 text-xs sm:text-sm transition-colors">
                  {isDone ? (
                    <span className="text-xs font-bold text-ink w-4 text-center shrink-0">✓</span>
                  ) : isCurrent ? (
                    <span className="text-xs font-bold text-ink w-4 text-center shrink-0 animate-pulse">◎</span>
                  ) : (
                    <span className="text-xs text-[#A8ADA8] w-4 text-center shrink-0">○</span>
                  )}
                  <span
                    className={
                      isDone
                        ? 'text-ink font-medium'
                        : isCurrent
                        ? 'text-ink font-bold'
                        : 'text-[#A8ADA8]'
                    }
                  >
                    {stepName}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-page pb-16">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 pt-6 md:pt-8">
        {/* Top return breadcrumb */}
        <button
          onClick={handleBack}
          className="flex items-center gap-1.5 text-xs font-semibold text-muted hover:text-ink transition cursor-pointer mb-5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>{step === 0 ? '返回面试准备' : '上一步'}</span>
        </button>

        {/* Page Header (as in image 4) */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-ink tracking-tight">新建面试</h1>
          <p className="text-xs md:text-sm text-muted mt-1">
            填写面试信息，AI 将生成个性化准备方案
          </p>
        </div>

        {/* Step Indicator (as in image 4) */}
        <div className="flex items-center justify-between mb-8 px-2">
          {steps.map((s, i) => {
            const isCurrent = step === s.num;
            const isDone = step > s.num;
            return (
              <React.Fragment key={s.num}>
                <div
                  onClick={() => {
                    if (s.num < step) setStep(s.num);
                  }}
                  className={`flex flex-col items-center gap-1.5 transition ${
                    s.num < step ? 'cursor-pointer' : ''
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                      isCurrent
                        ? 'bg-black text-white shadow-xs ring-4 ring-black/5'
                        : isDone
                        ? 'bg-[#4A6559] text-white'
                        : 'bg-[#F0F0EC] text-[#A8ADA8]'
                    }`}
                  >
                    {isDone ? <Check className="w-3.5 h-3.5 stroke-[2.5]" /> : s.num + 1}
                  </div>
                  <span
                    className={`text-[11.5px] tracking-tight whitespace-nowrap ${
                      isCurrent
                        ? 'font-bold text-ink'
                        : isDone
                        ? 'font-medium text-[#4A6559]'
                        : 'text-[#A8ADA8]'
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={`flex-1 mx-3 h-0.5 rounded-full transition-colors ${
                      step > s.num ? 'bg-[#4A6559]' : 'bg-[#E5E7E4]'
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Form Container Card */}
        <div className="bg-white rounded-2xl border border-edge p-6 sm:p-8 shadow-2xs space-y-6">
          {/* Step 0: 关联岗位 (Exact Match with Image 4) */}
          {step === 0 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 1: 关联岗位</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  选择要为哪个岗位新建面试准备，或新建一个岗位。
                </p>
              </div>

              {/* 关联已有岗位 下拉框 */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-ink">
                  关联已有岗位
                </label>
                <div className="relative">
                  <select
                    value={selectedJobId}
                    onChange={(e) => setSelectedJobId(e.target.value)}
                    className="w-full px-4 py-3 bg-white border border-edge rounded-xl text-xs sm:text-sm text-ink focus:outline-none focus:border-sage focus:ring-1 focus:ring-sage transition appearance-none cursor-pointer"
                  >
                    <option value="">请选择岗位...</option>
                    <optgroup label="【准备面试环节】匹配岗位">
                      {prepStageJobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.company} · {j.role} （{j.currentStage || '面试准备中'}）
                        </option>
                      ))}
                    </optgroup>
                    {jobs.filter((j) => !prepStageJobs.some((pj) => pj.id === j.id)).length > 0 && (
                      <optgroup label="全部其他在选岗位">
                        {jobs
                          .filter((j) => !prepStageJobs.some((pj) => pj.id === j.id))
                          .map((j) => (
                            <option key={j.id} value={j.id}>
                              {j.company} · {j.role} （{j.currentStage || j.status}）
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </select>
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-muted">
                    <ChevronRight className="w-4 h-4 rotate-90" />
                  </div>
                </div>

                {/* 选中岗位反馈卡片 (如图2模式) */}
                {selectedJob && (
                  <div className="mt-2.5 p-3.5 rounded-xl border border-edge bg-[#f8f9f7]/60 flex items-center justify-between animate-in fade-in duration-200">
                    <div className="flex items-center gap-2">
                      <span className="text-xs sm:text-sm font-bold text-ink">
                        {selectedJob.company} · {selectedJob.role}
                      </span>
                      <span className="text-xs text-muted">
                        {selectedJob.currentStage || '准备面试中'}
                      </span>
                    </div>
                    <div className="w-5 h-5 rounded-full bg-sage-soft text-sage border border-sage/40 flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  </div>
                )}
              </div>

              {/* 分割线：或 */}
              <div className="relative my-6 text-center">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-edge" />
                </div>
                <span className="relative px-3 bg-white text-xs text-muted">或</span>
              </div>

              {/* 虚线边框按钮：+ 新建岗位 · 前往 JD 分析 */}
              <div>
                <button
                  type="button"
                  onClick={handleGoToJDAnalysis}
                  className="w-full py-3.5 px-4 rounded-xl border border-dashed border-[#A8ADA8]/70 hover:border-sage hover:bg-sage-soft/10 text-xs sm:text-sm font-semibold text-ink hover:text-sage transition flex items-center justify-center gap-1.5 cursor-pointer group shadow-2xs"
                >
                  <span>+ 新建岗位 · 前往 JD 分析</span>
                </button>
                <div className="text-center text-[11px] text-muted mt-2">
                  JD 分析完成后可直接返回此页面并自动选中新岗位
                </div>
              </div>
            </div>
          )}

          {/* Step 1: 应聘信息 */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 2: 应聘信息</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  确认关联岗位与本次面试使用的简历版本，AI 将据此调取经历库进行攻防推演。
                </p>
              </div>

              {/* 关联岗位 (只读展示) */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  关联岗位（已选）
                </label>
                <div className="p-3.5 rounded-xl bg-[#f8f9f7] border border-edge flex items-center justify-between">
                  <div>
                    <div className="text-xs sm:text-sm font-bold text-ink">
                      {selectedJob?.company} · {selectedJob?.role}
                    </div>
                    <div className="text-[11px] text-muted mt-0.5">
                      {selectedJob?.department || '核心业务线'} · {selectedJob?.salaryRange || '40K–60K · 16薪'}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setStep(0)}
                    className="text-xs font-semibold text-[#4A6559] hover:underline cursor-pointer"
                  >
                    更换岗位
                  </button>
                </div>
              </div>

              {/* 选择简历 */}
              <div className="space-y-3">
                <label className="block text-xs font-semibold text-ink">
                  选择简历 *
                </label>
                <div className="relative">
                  <select
                    value={selectedResumeId}
                    onChange={(e) => {
                      if (e.target.value === 'upload_trigger') {
                        fileInputRef.current?.click();
                      } else {
                        setSelectedResumeId(e.target.value);
                      }
                    }}
                    className="w-full px-3.5 py-3 bg-white border border-edge rounded-xl text-xs sm:text-sm font-semibold text-ink focus:outline-none focus:border-sage transition appearance-none cursor-pointer"
                  >
                    <optgroup label="简历库中已解析简历">
                      {historicalResumes.map((hr) => (
                        <option key={hr.id} value={hr.id}>
                          {hr.name} ({hr.fileSize} · {hr.isDefault ? '默认底座' : '历史版本'})
                        </option>
                      ))}
                    </optgroup>
                    <option value="res-tailored-1">
                      {selectedJob?.company || '目标企业'} · AI 定制优化版简历（ATS 匹配 96%）
                    </option>
                    <option value="upload_trigger">
                      + 上传本地新简历 (PDF / Word) ...
                    </option>
                  </select>
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-muted">
                    <ChevronRight className="w-4 h-4 rotate-90" />
                  </div>
                </div>

                {/* Hidden File Input */}
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileUpload}
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                />

                {/* 上传区域 */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    handleSimulatedDrop();
                  }}
                  className="p-4 border border-dashed border-[#A8ADA8]/70 hover:border-sage rounded-xl bg-[#f8f9f7]/60 hover:bg-sage-soft/10 flex items-center justify-between gap-3 transition cursor-pointer group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-white border border-edge text-sage group-hover:scale-105 transition shadow-2xs">
                      <Upload className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-ink group-hover:text-sage transition">
                        {customUploadedFileName ? `已上传：${customUploadedFileName}` : '点击上传新简历或将文件拖拽至此处'}
                      </div>
                      <div className="text-[11px] text-muted">
                        支持 PDF、DOCX 格式，AI 将自动解析项目经历并对齐本岗位考点
                      </div>
                    </div>
                  </div>
                  <span className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-white border border-edge text-ink group-hover:border-sage shadow-2xs shrink-0">
                    浏览文件
                  </span>
                </div>
              </div>

              {/* Cover Letter (Optional) */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  投递附言 / 个人介绍补充（可选）
                </label>
                <textarea
                  rows={2}
                  value={coverLetter}
                  onChange={(e) => setCoverLetter(e.target.value)}
                  placeholder="填写投递时附带的求职信要点或期望沟通的重点方向..."
                  className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink placeholder:text-faint focus:outline-none focus:border-sage transition resize-none leading-relaxed"
                />
              </div>
            </div>
          )}

          {/* Step 2: 面试信息 */}
          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 3: 面试信息</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  输入面试轮次、形式与面试官信息，AI 将针对性推断面试官考核重点与问题角度。
                </p>
              </div>

              {/* Round & Type */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">面试轮次 *</label>
                  <select
                    value={roundNumber}
                    onChange={(e) => handleRoundNumberChange(parseInt(e.target.value))}
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs font-semibold text-ink focus:outline-none focus:border-sage transition cursor-pointer"
                  >
                    <option value={1}>第1面 · 业务初面</option>
                    <option value={2}>第2面 · 业务/技术交叉面</option>
                    <option value={3}>第3面 · 总监/业务负责人面</option>
                    <option value={4}>第4面 · HRBP综合面</option>
                    <option value={5}>第5面 · 终面 / 总裁面</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">面试类型 *</label>
                  <select
                    value={roundType}
                    onChange={(e) => setRoundType(e.target.value as InterviewRoundType)}
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs font-semibold text-ink focus:outline-none focus:border-sage transition cursor-pointer"
                  >
                    <option value="business">业务面（考察业务匹配与落地实操）</option>
                    <option value="tech">技术/架构面（考察底层机制与边界）</option>
                    <option value="product">产品专项面（考察方案推演与架构）</option>
                    <option value="hr">HR面（考察动机、自驱力与团队协作）</option>
                    <option value="comprehensive">综合终面（考察战略视野与商业ROI）</option>
                  </select>
                </div>
              </div>

              {/* Date & Time */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">面试日期 *</label>
                  <input
                    type="date"
                    value={interviewDate}
                    onChange={(e) => setInterviewDate(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">面试时间 *</label>
                  <input
                    type="time"
                    value={interviewTimeHour}
                    onChange={(e) => setInterviewTimeHour(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                  />
                </div>
              </div>

              {/* Format & Platform */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">面试形式 *</label>
                  <select
                    value={interviewFormat}
                    onChange={(e) => setInterviewFormat(e.target.value as InterviewFormat)}
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs font-semibold text-ink focus:outline-none focus:border-sage transition cursor-pointer"
                  >
                    <option value="video">视频面试 (Remote Video)</option>
                    <option value="phone">电话面试 (Phone)</option>
                    <option value="onsite">现场面试 (On-site)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-ink">会议平台 / 地点</label>
                  <input
                    type="text"
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value)}
                    placeholder="如：腾讯会议、飞书会议、Zoom、现场地址..."
                    className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                  />
                </div>
              </div>

              {/* Interviewer */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  面试官信息 / 背景说明（可选）
                </label>
                <input
                  type="text"
                  value={interviewer}
                  onChange={(e) => setInterviewer(e.target.value)}
                  placeholder="如：李明（搜索策略负责人）、技术架构师..."
                  className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                />
              </div>
            </div>
          )}

          {/* Step 3: 补充信息 & 生成方案 */}
          {step === 3 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 4: 补充信息</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  补充针对本轮面试的已知信息，AI 将结合你的经历库生成专属攻防方案。
                </p>
              </div>

              {/* Supplement notes */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-ink">
                  补充说明 / 关注重点（可选）
                </label>
                <textarea
                  rows={3}
                  value={supplementNotes}
                  onChange={(e) => setSupplementNotes(e.target.value)}
                  placeholder="例如：HR 提醒重点关注大模型 Eval 评测体系与跨算法团队沟通；希望强化 NDCG 量化指标表达..."
                  className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink placeholder:text-faint focus:outline-none focus:border-sage transition resize-none leading-relaxed"
                />
              </div>

              {/* Remind Checkbox */}
              <label className="flex items-center gap-2.5 p-3.5 rounded-xl bg-page border border-edge cursor-pointer hover:bg-page/80 transition">
                <input
                  type="checkbox"
                  checked={remindUpload}
                  onChange={(e) => setRemindUpload(e.target.checked)}
                  className="w-4 h-4 rounded text-[#4A6559] accent-[#4A6559] cursor-pointer"
                />
                <span className="text-xs font-medium text-ink">
                  面试结束后提醒我上传录音或速记，用于一键逐题复盘诊断
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Bottom Actions Toolbar (as in image 4) */}
        <div className="flex items-center justify-between mt-6">
          <span className="text-xs text-muted">
            第 {step + 1} 步 / 共 {steps.length} 步
          </span>

          <div className="flex items-center gap-3">
            {step > 0 && (
              <button
                type="button"
                onClick={handleBack}
                className="px-4 py-2 rounded-xl border border-edge bg-white hover:bg-page text-xs font-semibold text-ink transition cursor-pointer"
              >
                上一步
              </button>
            )}

            {step < 3 ? (
              <button
                type="button"
                onClick={handleNext}
                disabled={!canNext()}
                className={`flex items-center gap-1.5 px-6 py-2.5 rounded-xl text-xs font-bold transition shadow-xs cursor-pointer ${
                  canNext()
                    ? 'bg-[#395347] hover:bg-[#2d4239] text-white'
                    : 'bg-[#c5c8c5] text-white cursor-not-allowed'
                }`}
              >
                <span>下一步</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#395347] hover:bg-[#2d4239] text-white text-xs font-bold shadow-xs transition cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>创建并生成攻防方案</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
