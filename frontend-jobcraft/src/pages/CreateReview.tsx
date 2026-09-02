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
  FileText,
  Clock,
  Video
} from 'lucide-react';

const steps = [
  { num: 0, label: '关联岗位' },
  { num: 1, label: '关联面试' },
  { num: 2, label: '上传记录' }
];

const analysisSteps = [
  '正在解析面试记录...',
  '识别关键问答段落...',
  '分析回答结构与逻辑...',
  '生成能力维度评估...',
  '整理优化建议...',
  '复盘报告生成中...'
];

const demoTranscriptText = `【面试官】：你好，请简要介绍一下你在快知智能主导的 AI 搜索评测体系项目，当初是如何衡量模型质量好坏的？
【候选人】：你好，在快知智能，我从 0 到 1 搭建了面向 15 个垂类的高质量 Eval 评测集与自动化 LLM-as-a-Judge 评测管线。我们主要从三大维度衡量：首先是忠实度（Faithfulness），杜绝检索幻觉；其次是答案相关性；最后是端到端搜索质量指标 NDCG@5。通过双模型裁判交叉判别与 5% 金标抽检，评测周期由 2 周缩短至 4 小时以内，模型幻觉率下降了 34.2%。
【面试官】：追问一下，当双模型裁判（比如 GPT-4 和 Claude）打分出现分歧时，你们是怎么裁决的？
【候选人】：我们设计了自动化仲裁兜底机制。如果两个模型打分差异超过 1 分（5 分制），系统会自动触发第三模型或分流至资深人工标注员金标仲裁池，并将该 Bad Case 沉淀到黄金仲裁案例库中。`;

export const CreateReview: React.FC = () => {
  const {
    jobs,
    interviews,
    createReviewFromTranscript,
    navigateTo,
    setJdAnalysisReturnTarget,
    showToast
  } = useJobCraft();

  const [step, setStep] = useState<0 | 1 | 2>(0);

  // Filter jobs in "completed / reviewing" stage
  const reviewStageJobs = jobs.filter(
    (j) =>
      j.status === 'finished' ||
      j.status === 'interviewing' ||
      j.steps.reviewStage === 'done' ||
      j.steps.reviewStage === 'in_progress' ||
      j.interviewIds.length > 0
  );

  // Step 0 - Job selection
  const [selectedJobId, setSelectedJobId] = useState<string>(
    reviewStageJobs[0]?.id || jobs[0]?.id || ''
  );

  // Step 1 - Interview selection
  const [selectedInterviewId, setSelectedInterviewId] = useState<string>('');
  const [newInterviewMode, setNewInterviewMode] = useState(false);
  const [manualForm, setManualForm] = useState({
    company: '',
    role: '',
    roundNumber: 1,
    roundName: '第1面 · 业务初面',
    roundType: 'business' as InterviewRoundType,
    date: '2026-09-01',
    time: '14:00',
    format: 'video' as InterviewFormat,
    interviewer: '业务技术面试官'
  });

  // Step 2 - Upload
  const [uploadMode, setUploadMode] = useState<'paste' | 'file'>('paste');
  const [pasteText, setPasteText] = useState(demoTranscriptText);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Standalone AI Analysis state (image 3)
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeStep, setAnalyzeStep] = useState(0);

  const selectedJob = jobs.find((j) => j.id === selectedJobId);
  const jobInterviews = selectedJobId
    ? interviews.filter((i) => i.jobId === selectedJobId)
    : [];

  // Auto-select first interview if available
  useEffect(() => {
    if (jobInterviews.length > 0 && !selectedInterviewId && !newInterviewMode) {
      setSelectedInterviewId(jobInterviews[0].id);
    }
  }, [selectedJobId, jobInterviews, selectedInterviewId, newInterviewMode]);

  const canNext = () => {
    if (step === 0) {
      return !!selectedJobId;
    }
    if (step === 1) {
      if (newInterviewMode || jobInterviews.length === 0) {
        return !!(selectedJob?.company || manualForm.company.trim());
      }
      return !!selectedInterviewId;
    }
    return true;
  };

  const handleBack = () => {
    if (step === 0) {
      navigateTo('interview_review_center');
    } else {
      setStep((s) => (s - 1) as 0 | 1 | 2);
    }
  };

  const handleNext = () => {
    if (step < 2 && canNext()) {
      setStep((s) => (s + 1) as 0 | 1 | 2);
    }
  };

  // Jump to JD analysis to create new JD and return to review later
  const handleGoToJDAnalysis = () => {
    setJdAnalysisReturnTarget('create_review');
    showToast({
      type: 'info',
      title: '前往 JD 分析',
      message: '分析完成后可直接带入此岗位返回新建复盘。'
    });
    navigateTo('jd_analysis_center');
  };

  // Handle local file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadedFileName(file.name);
      showToast({
        type: 'success',
        title: '录音/记录上传成功',
        message: `已解析「${file.name}」，准备开始智能复盘研判。`
      });
    }
  };

  const handleSimulatedDrop = () => {
    const defaultName = `${selectedJob?.company || '字节跳动'}_第1面录音与速记.m4a`;
    setUploadedFileName(defaultName);
    showToast({
      type: 'success',
      title: '文件已导入',
      message: `已载入「${defaultName}」。`
    });
  };

  // Trigger AI analysis
  const handleStartAnalysis = () => {
    if (uploadMode === 'paste' && !pasteText.trim()) {
      showToast({
        type: 'warning',
        title: '请输入面试速记文本',
        message: '请粘贴面试对话或速记记录以便 AI 进行深度复盘。'
      });
      return;
    }
    setIsAnalyzing(true);
    setAnalyzeStep(0);
  };

  // Progress animation (650ms per step)
  useEffect(() => {
    if (!isAnalyzing) return;

    if (analyzeStep < analysisSteps.length) {
      const timer = setTimeout(() => {
        setAnalyzeStep((prev) => prev + 1);
      }, 650);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        const interview = interviews.find((i) => i.id === selectedInterviewId);
        const companyName = selectedJob?.company || manualForm.company || '字节跳动';
        const roleName = selectedJob?.role || manualForm.role || 'AI 产品经理';
        const roundNameStr = interview?.roundName || manualForm.roundName;

        const newRevId = createReviewFromTranscript({
          jobId: selectedJobId || undefined,
          interviewId: selectedInterviewId || undefined,
          company: companyName,
          role: roleName,
          roundName: roundNameStr,
          transcriptText: pasteText
        });

        showToast({
          type: 'success',
          title: '面试复盘已生成',
          message: `已完成「${companyName} ${roundNameStr}」的深度逐题诊断与经历库反哺。`
        });
        navigateTo('interview_review_detail', { reviewId: newRevId });
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isAnalyzing, analyzeStep]);

  // If in AI analysis mode, render standalone loading page (as in image 3)
  if (isAnalyzing) {
    return (
      <div className="min-h-full bg-page flex flex-col items-center justify-center px-4 py-16 animate-in fade-in duration-300">
        <div className="w-full max-w-xl bg-white rounded-2xl border border-edge p-8 sm:p-10 shadow-sm text-center">
          {/* Top Gear Animation */}
          <div className="w-14 h-14 rounded-full bg-[#f2f3ef] flex items-center justify-center mx-auto mb-4 text-ink shadow-2xs">
            <Settings className="w-6 h-6 animate-spin" style={{ animationDuration: '3.5s' }} />
          </div>

          {/* Titles */}
          <h2 className="text-xl font-bold text-ink mb-1 tracking-tight">AI 正在生成复盘报告</h2>
          <p className="text-xs text-muted mb-6">请稍候，这通常需要 10–30 秒</p>

          {/* Checklist container (exact match with image 3) */}
          <div className="bg-[#f8f9f7] rounded-xl p-5 sm:p-6 border border-edge/60 text-left space-y-3.5">
            {analysisSteps.map((stepName, idx) => {
              const isDone = analyzeStep > idx;
              const isCurrent = analyzeStep === idx;
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
          <span>{step === 0 ? '返回面试复盘' : '上一步'}</span>
        </button>

        {/* Page Header (as in image 1) */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-ink tracking-tight">新建复盘</h1>
          <p className="text-xs md:text-sm text-muted mt-1">
            上传面试记录，AI 将生成深度复盘分析报告
          </p>
        </div>

        {/* Step Indicator (as in image 1) */}
        <div className="flex items-center justify-between mb-8 px-4">
          {steps.map((s, i) => {
            const isCurrent = step === s.num;
            const isDone = step > s.num;
            return (
              <React.Fragment key={s.num}>
                <div
                  onClick={() => {
                    if (s.num < step) setStep(s.num as 0 | 1 | 2);
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
                    className={`flex-1 mx-4 h-0.5 rounded-full transition-colors ${
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
          {/* Step 0: 关联岗位 (Exact Match with Image 1 & Image 2) */}
          {step === 0 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 1: 关联岗位</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  选择要为哪个岗位创建复盘，仅显示已完成至少一场面试的岗位。
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
                    <option value="">请选择岗位（已完成面试）...</option>
                    <optgroup label="【已完成面试/可复盘】岗位">
                      {reviewStageJobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {j.company} · {j.role} （{j.currentStage || '第1面已完成'}）
                        </option>
                      ))}
                    </optgroup>
                    {jobs.filter((j) => !reviewStageJobs.some((rj) => rj.id === j.id)).length > 0 && (
                      <optgroup label="全部其他在选岗位">
                        {jobs
                          .filter((j) => !reviewStageJobs.some((rj) => rj.id === j.id))
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

                {/* 选中岗位反馈卡片 (如图 2) */}
                {selectedJob && (
                  <div className="mt-2.5 p-3.5 rounded-xl border border-edge bg-[#f8f9f7]/60 flex items-center justify-between animate-in fade-in duration-200">
                    <div className="flex items-center gap-2">
                      <span className="text-xs sm:text-sm font-bold text-ink">
                        {selectedJob.company} · {selectedJob.role}
                      </span>
                      <span className="text-xs text-muted">
                        {selectedJob.currentStage || '第1面已完成'}
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

          {/* Step 1: 关联面试 */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 2: 关联面试</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  选择本岗位下的具体面试场次，或新建本次已完成的面试信息。
                </p>
              </div>

              {/* 关联岗位提示 */}
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

              {/* 已有面试列表 */}
              {jobInterviews.length > 0 && !newInterviewMode ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink">选择面试场次 *</label>
                    <button
                      type="button"
                      onClick={() => setNewInterviewMode(true)}
                      className="text-xs font-semibold text-[#4A6559] hover:underline cursor-pointer"
                    >
                      + 录入新面试场次
                    </button>
                  </div>

                  <div className="grid grid-cols-1 gap-2.5">
                    {jobInterviews.map((intv) => {
                      const isSelected = selectedInterviewId === intv.id;
                      return (
                        <div
                          key={intv.id}
                          onClick={() => setSelectedInterviewId(intv.id)}
                          className={`p-3.5 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                            isSelected
                              ? 'border-sage bg-sage-soft/15 ring-1 ring-sage'
                              : 'border-edge bg-white hover:border-sage-dark/40'
                          }`}
                        >
                          <div>
                            <div className="text-xs sm:text-sm font-bold text-ink flex items-center gap-2">
                              <span>{intv.roundName}</span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white border border-edge text-muted">
                                {intv.roundType === 'tech'
                                  ? '技术面'
                                  : intv.roundType === 'business'
                                  ? '业务面'
                                  : intv.roundType === 'hr'
                                  ? 'HR面'
                                  : '综合面'}
                              </span>
                            </div>
                            <div className="text-[11px] text-muted mt-1 flex items-center gap-3">
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {intv.time}
                              </span>
                              <span className="flex items-center gap-1">
                                <Video className="w-3 h-3" />
                                {intv.interviewer || '面试官'}
                              </span>
                            </div>
                          </div>
                          <div
                            className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                              isSelected
                                ? 'border-[#395347] bg-[#395347] text-white'
                                : 'border-edge bg-white'
                            }`}
                          >
                            {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                /* 手动录入新面试场次 */
                <div className="space-y-4 pt-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink">录入新面试场次信息</label>
                    {jobInterviews.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setNewInterviewMode(false)}
                        className="text-xs font-semibold text-muted hover:text-ink cursor-pointer"
                      >
                        返回选择已有面试
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-semibold text-ink">面试轮次 *</label>
                      <select
                        value={manualForm.roundNumber}
                        onChange={(e) => {
                          const num = parseInt(e.target.value);
                          setManualForm((prev) => ({
                            ...prev,
                            roundNumber: num,
                            roundName:
                              num === 1
                                ? '第1面 · 业务初面'
                                : num === 2
                                ? '第2面 · 业务与技术交叉面'
                                : num === 3
                                ? '第3面 · 总监/业务负责人面'
                                : num === 4
                                ? '第4面 · HRBP综合面'
                                : `第${num}面 · 终面`
                          }));
                        }}
                        className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs font-semibold text-ink focus:outline-none focus:border-sage transition cursor-pointer"
                      >
                        <option value={1}>第1面 · 业务初面</option>
                        <option value={2}>第2面 · 业务与技术交叉面</option>
                        <option value={3}>第3面 · 总监/业务负责人面</option>
                        <option value={4}>第4面 · HRBP综合面</option>
                        <option value={5}>第5面 · 终面</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="block text-xs font-semibold text-ink">面试日期 *</label>
                      <input
                        type="date"
                        value={manualForm.date}
                        onChange={(e) => setManualForm({ ...manualForm, date: e.target.value })}
                        className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-semibold text-ink">面试形式</label>
                      <select
                        value={manualForm.format}
                        onChange={(e) =>
                          setManualForm({ ...manualForm, format: e.target.value as InterviewFormat })
                        }
                        className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs font-semibold text-ink focus:outline-none focus:border-sage transition cursor-pointer"
                      >
                        <option value="video">视频面试 (Remote Video)</option>
                        <option value="phone">电话面试 (Phone)</option>
                        <option value="onsite">现场面试 (On-site)</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <label className="block text-xs font-semibold text-ink">面试官信息（可选）</label>
                      <input
                        type="text"
                        value={manualForm.interviewer}
                        onChange={(e) =>
                          setManualForm({ ...manualForm, interviewer: e.target.value })
                        }
                        placeholder="如：业务主管、交叉技术官..."
                        className="w-full px-3.5 py-2.5 bg-page border border-edge rounded-xl text-xs text-ink focus:outline-none focus:border-sage transition"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 2: 上传记录 */}
          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-base font-bold text-ink">步骤 3: 上传记录</h3>
                <div className="border-b border-edge/60 my-3" />
                <p className="text-xs text-muted">
                  支持直接粘贴面试速记文字，或上传音频文件（m4a/mp3/wav/txt），AI 将自动结构化提炼问答对与攻防诊断。
                </p>
              </div>

              {/* Mode switch pills */}
              <div className="flex p-1 bg-[#f8f9f7] rounded-xl border border-edge/80 w-fit">
                <button
                  type="button"
                  onClick={() => setUploadMode('paste')}
                  className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    uploadMode === 'paste'
                      ? 'bg-white text-ink shadow-2xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  粘贴速记文本 / 对话记录
                </button>
                <button
                  type="button"
                  onClick={() => setUploadMode('file')}
                  className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    uploadMode === 'file'
                      ? 'bg-white text-ink shadow-2xs'
                      : 'text-muted hover:text-ink'
                  }`}
                >
                  上传录音 / 转录文档
                </button>
              </div>

              {uploadMode === 'paste' ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink">
                      面试速记 / 对话记录文本 *
                    </label>
                    <span className="text-[11px] text-muted">
                      已载入示例速记对话（可直接用于研判）
                    </span>
                  </div>
                  <textarea
                    rows={8}
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder="【面试官】：请介绍一下...&#10;【候选人】：我当时主要负责..."
                    className="w-full p-3.5 bg-page border border-edge rounded-xl text-xs font-mono text-ink placeholder:text-faint focus:outline-none focus:border-sage transition resize-none leading-relaxed"
                  />
                </div>
              ) : (
                <div className="space-y-3">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept=".mp3,.m4a,.wav,.txt,.docx"
                    className="hidden"
                  />
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      handleSimulatedDrop();
                    }}
                    className="p-8 border border-dashed border-[#A8ADA8]/70 hover:border-sage rounded-xl bg-[#f8f9f7]/60 hover:bg-sage-soft/10 flex flex-col items-center justify-center gap-3 transition cursor-pointer group text-center"
                  >
                    <div className="p-3 rounded-full bg-white border border-edge text-sage group-hover:scale-105 transition shadow-2xs">
                      <Upload className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-ink group-hover:text-sage transition">
                        {uploadedFileName ? `已选择：${uploadedFileName}` : '点击上传录音或将音频文件拖拽至此处'}
                      </div>
                      <div className="text-[11px] text-muted mt-1">
                        支持 MP3, M4A, WAV, TXT, DOCX 等格式，单文件最大 500MB
                      </div>
                    </div>
                    <span className="text-xs font-semibold px-4 py-2 rounded-xl bg-white border border-edge text-ink group-hover:border-sage shadow-2xs">
                      选择本地文件
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Bottom Actions Toolbar */}
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

            {step < 2 ? (
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
                onClick={handleStartAnalysis}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#395347] hover:bg-[#2d4239] text-white text-xs font-bold shadow-xs transition cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>开始 AI 智能复盘研判</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
