import React, { useState } from 'react';
import { useJobCraft } from '../context/JobCraftContext';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  Upload,
  FileText,
  Loader2,
  Building2,
  Calendar,
  ClipboardList
} from 'lucide-react';

const steps = [
  { num: 0, label: '关联来源' },
  { num: 1, label: '面试信息' },
  { num: 2, label: '上传记录' }
];

const analysisSteps = [
  '识别文档格式',
  '提取问答记录',
  '分析面试官意图',
  '分析回答质量',
  '生成改进建议'
];

export const NewReview: React.FC = () => {
  const {
    jobs,
    interviews,
    addInterviewReview,
    createReviewFromTranscript,
    createJob,
    createJDAnalysis,
    navigateTo,
    showToast
  } = useJobCraft();

  const [step, setStep] = useState<0 | 1 | 2>(0);

  // Step 0
  const [selectedJobId, setSelectedJobId] = useState<string>('');
  const [noJob, setNoJob] = useState(false);
  const [selectedInterviewId, setSelectedInterviewId] = useState<string>('');

  // New job form
  const [newJobCompany, setNewJobCompany] = useState('');
  const [newJobRole, setNewJobRole] = useState('');
  const [showNewJobForm, setShowNewJobForm] = useState(false);

  // Step 1 - manual form
  const [manualCompany, setManualCompany] = useState('');
  const [manualRole, setManualRole] = useState('');
  const [manualRoundName, setManualRoundName] = useState('');
  const [manualTime, setManualTime] = useState('');

  // Step 2
  const [uploadMode, setUploadMode] = useState<'file' | 'text'>('text');
  const [transcriptContent, setTranscriptContent] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);

  const selectedJob = jobs.find((j) => j.id === selectedJobId);
  const jobInterviews = selectedJobId
    ? interviews.filter((i) => i.jobId === selectedJobId)
    : [];
  const selectedInterview = interviews.find((i) => i.id === selectedInterviewId);

  const canNext = () => {
    if (step === 0) {
      if (noJob) return true;
      return !!selectedJobId;
    }
    return true;
  };

  // Handle back
  const handleBack = () => {
    if (step === 0) {
      navigateTo('interview_review_center');
    } else {
      setStep((s) => (s - 1) as 0 | 1 | 2);
    }
  };

  // Handle next
  const handleNext = () => {
    if (step < 2) {
      setStep((s) => (s + 1) as 0 | 1 | 2);
    }
  };

  // Handle create job
  const handleCreateJob = () => {
    if (!newJobCompany.trim() || !newJobRole.trim()) {
      showToast({
        type: 'warning',
        title: '请填写完整信息',
        message: '公司名称和岗位名称不能为空'
      });
      return;
    }

    const newJobId = createJob({
      company: newJobCompany.trim(),
      role: newJobRole.trim(),
      status: 'pending'
    });

    createJDAnalysis({
      company: newJobCompany.trim(),
      role: newJobRole.trim(),
      rawText: '待补充JD内容',
      jobId: newJobId
    });

    setSelectedJobId(newJobId);
    setShowNewJobForm(false);
    setNewJobCompany('');
    setNewJobRole('');

    showToast({
      type: 'success',
      title: '岗位已创建',
      message: '已自动创建岗位和JD记录'
    });
  };

  // Handle analysis
  const handleStartAnalysis = () => {
    if (!transcriptContent.trim()) return;
    setIsAnalyzing(true);
    setAnalysisStep(0);

    const interval = setInterval(() => {
      setAnalysisStep((prev) => {
        if (prev >= analysisSteps.length - 1) {
          clearInterval(interval);
          setTimeout(() => {
            if (selectedInterviewId) {
              createReviewFromTranscript({
                interviewId: selectedInterviewId,
                transcript: transcriptContent
              });
              navigateTo('interview_review_detail', { interviewId: selectedInterviewId });
            } else {
              addInterviewReview(interviews[0]?.id || 'int-byte-1', {
                overallScore: 88,
                passProbability: '通过概率较高',
                highlights: ['回答逻辑清晰，量化数据充分'],
                drawbacks: ['可补充更多技术深度细节']
              });
              navigateTo('interview_review_center');
            }
            showToast({ type: 'success', title: '智能复盘报告已生成' });
          }, 600);
          return prev;
        }
        return prev + 1;
      });
    }, 800);
  };

  // Render step content
  const renderStepContent = () => {
    // Step 0: Source selection
    if (step === 0) {
      return (
        <div className="space-y-5">
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#202421' }}>
              关联来源
            </h3>
            <p className="text-sm mt-1" style={{ color: '#737873' }}>
              关联岗位和面试后，AI 可以更精准地分析得失。
            </p>
          </div>

          {/* No job toggle */}
          <label
            className="flex items-center gap-3 p-4 rounded-xl cursor-pointer transition-all"
            style={{
              border: noJob ? '1.5px solid #3E6256' : '1.5px solid #E4E5E0',
              background: noJob ? '#F5FAF7' : '#FFFFFF'
            }}
          >
            <input
              type="radio"
              checked={noJob}
              onChange={() => {
                setNoJob(true);
                setSelectedJobId('');
                setSelectedInterviewId('');
              }}
              className="w-4 h-4"
              style={{ accentColor: '#3E6256' }}
            />
            <div>
              <div className="text-sm font-semibold" style={{ color: '#202421' }}>
                暂不关联岗位
              </div>
              <div className="text-xs mt-0.5" style={{ color: '#A8ADA8' }}>
                系统自动创建JD记录（未分析），稍后可补充
              </div>
            </div>
          </label>

          {!noJob && (
            <>
              {/* Job dropdown */}
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: '#737873' }}>
                  选择岗位
                </label>
                <select
                  value={selectedJobId}
                  onChange={(e) => {
                    setSelectedJobId(e.target.value);
                    setSelectedInterviewId('');
                    setShowNewJobForm(false);
                  }}
                  className="w-full px-4 py-3 text-sm rounded-xl outline-none"
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
                <button
                  onClick={() => setShowNewJobForm(true)}
                  className="w-full py-3 px-4 rounded-xl text-sm font-medium transition-all"
                  style={{
                    border: '1px dashed #C8D8D1',
                    background: 'transparent',
                    color: '#3E6256'
                  }}
                >
                  + 新建岗位
                </button>
              ) : (
                <div
                  className="p-5 rounded-xl space-y-4"
                  style={{
                    border: '1px solid #3E6256',
                    background: '#F5FAF7'
                  }}
                >
                  <div className="text-sm font-semibold" style={{ color: '#202421' }}>
                    新建岗位
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <input
                      type="text"
                      placeholder="公司名称"
                      value={newJobCompany}
                      onChange={(e) => setNewJobCompany(e.target.value)}
                      className="px-4 py-3 text-sm rounded-xl outline-none"
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
                      className="px-4 py-3 text-sm rounded-xl outline-none"
                      style={{
                        border: '1px solid #E4E5E0',
                        background: '#FFFFFF',
                        color: '#202421'
                      }}
                    />
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => {
                        setShowNewJobForm(false);
                        setNewJobCompany('');
                        setNewJobRole('');
                      }}
                      className="flex-1 py-3 text-sm rounded-xl transition-all"
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
                      className="flex-1 py-3 text-sm font-medium rounded-xl transition-all"
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
            </>
          )}

          {/* Show interviews for selected job */}
          {selectedJobId && jobInterviews.length > 0 && !noJob && (
            <div className="space-y-3">
              <label className="block text-sm font-medium" style={{ color: '#737873' }}>
                选择面试轮次
              </label>
              {jobInterviews.map((int) => (
                <div
                  key={int.id}
                  onClick={() => setSelectedInterviewId(int.id)}
                  className="p-4 rounded-xl flex items-center justify-between cursor-pointer transition-all"
                  style={{
                    border: selectedInterviewId === int.id ? '1.5px solid #3E6256' : '1.5px solid #E4E5E0',
                    background: selectedInterviewId === int.id ? '#F5FAF7' : '#FFFFFF'
                  }}
                >
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4" style={{ color: '#A8ADA8' }} />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#202421' }}>
                        {int.roundName}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: '#A8ADA8' }}>
                        {int.time} · {int.format === 'video' ? '视频' : '现场'}
                      </div>
                    </div>
                  </div>
                  {selectedInterviewId === int.id && (
                    <CheckCircle2 className="w-5 h-5" style={{ color: '#3E6256' }} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    // Step 1: Interview info
    if (step === 1) {
      return (
        <div className="space-y-5">
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#202421' }}>
              面试信息确认
            </h3>
            <p className="text-sm mt-1" style={{ color: '#737873' }}>
              确认或补充面试基本信息
            </p>
          </div>

          {/* Show selected interview card */}
          {selectedInterview && !noJob && (
            <div
              className="p-4 rounded-xl space-y-2"
              style={{
                border: '1px solid #3E6256',
                background: '#F5FAF7'
              }}
            >
              <div className="text-sm font-bold" style={{ color: '#202421' }}>
                {selectedInterview.company} · {selectedInterview.role}
              </div>
              <div className="text-xs" style={{ color: '#A8ADA8' }}>
                {selectedInterview.roundName} · {selectedInterview.time}
              </div>
            </div>
          )}

          {/* Manual form */}
          {(noJob || !selectedInterview) && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#737873' }}>
                    公司名称
                  </label>
                  <input
                    type="text"
                    placeholder="例如：字节跳动"
                    value={manualCompany}
                    onChange={(e) => setManualCompany(e.target.value)}
                    className="w-full px-4 py-3 text-sm rounded-xl outline-none"
                    style={{
                      border: '1px solid #E4E5E0',
                      background: '#FFFFFF',
                      color: '#202421'
                    }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#737873' }}>
                    岗位名称
                  </label>
                  <input
                    type="text"
                    placeholder="例如：AI PM"
                    value={manualRole}
                    onChange={(e) => setManualRole(e.target.value)}
                    className="w-full px-4 py-3 text-sm rounded-xl outline-none"
                    style={{
                      border: '1px solid #E4E5E0',
                      background: '#FFFFFF',
                      color: '#202421'
                    }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#737873' }}>
                    面试轮次
                  </label>
                  <input
                    type="text"
                    placeholder="例如：第2面 · 技术面"
                    value={manualRoundName}
                    onChange={(e) => setManualRoundName(e.target.value)}
                    className="w-full px-4 py-3 text-sm rounded-xl outline-none"
                    style={{
                      border: '1px solid #E4E5E0',
                      background: '#FFFFFF',
                      color: '#202421'
                    }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: '#737873' }}>
                    面试时间
                  </label>
                  <input
                    type="text"
                    placeholder="例如：2026-09-01 14:00"
                    value={manualTime}
                    onChange={(e) => setManualTime(e.target.value)}
                    className="w-full px-4 py-3 text-sm rounded-xl outline-none"
                    style={{
                      border: '1px solid #E4E5E0',
                      background: '#FFFFFF',
                      color: '#202421'
                    }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    // Step 2: Upload record
    if (step === 2) {
      return (
        <div className="space-y-5">
          <div>
            <h3 className="text-base font-semibold" style={{ color: '#202421' }}>
              上传面试记录
            </h3>
            <p className="text-sm mt-1" style={{ color: '#737873' }}>
              支持文件上传或粘贴文本，AI 自动完成逐题诊断
            </p>
          </div>

          {/* Mode switch */}
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setUploadMode('file')}
              className="p-4 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all"
              style={{
                border: uploadMode === 'file' ? '1px solid #3E6256' : '1px solid #E4E5E0',
                background: uploadMode === 'file' ? '#E5EEE9' : '#FFFFFF',
                color: uploadMode === 'file' ? '#3E6256' : '#737873'
              }}
            >
              <Upload className="w-4 h-4" />
              <span>上传文件</span>
            </button>
            <button
              type="button"
              onClick={() => setUploadMode('text')}
              className="p-4 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all"
              style={{
                border: uploadMode === 'text' ? '1px solid #3E6256' : '1px solid #E4E5E0',
                background: uploadMode === 'text' ? '#E5EEE9' : '#FFFFFF',
                color: uploadMode === 'text' ? '#3E6256' : '#737873'
              }}
            >
              <FileText className="w-4 h-4" />
              <span>粘贴文本</span>
            </button>
          </div>

          {uploadMode === 'file' ? (
            <div
              className="rounded-xl text-center"
              style={{
                border: '2px dashed #D0D2CB',
                background: '#FAFAF8',
                padding: '48px 24px'
              }}
            >
              <Upload className="w-10 h-10 mx-auto mb-3" style={{ color: '#A8ADA8' }} />
              <p className="text-base font-bold mb-1" style={{ color: '#202421' }}>
                拖拽文件到此处或点击浏览
              </p>
              <p className="text-sm" style={{ color: '#A8ADA8' }}>
                支持 DOCX / PDF / TXT / Markdown
              </p>
            </div>
          ) : (
            <div>
              <textarea
                rows={10}
                placeholder={`粘贴面试过程中的核心提问与作答记录...\n\n例如：\n面试官：请介绍一下你在过去负责的最具挑战性的 AI 项目？\n我：我们设计了一套 LLM-as-a-Judge 自动化评测管线...`}
                value={transcriptContent}
                onChange={(e) => setTranscriptContent(e.target.value)}
                className="w-full px-4 py-3 text-sm rounded-xl outline-none resize-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421',
                  lineHeight: 1.6
                }}
              />
              <div className="flex items-center justify-between mt-2">
                <span className="text-xs" style={{ color: '#A8ADA8' }}>
                  格式：问答对话记录或会议纪要
                </span>
                <span className="text-xs" style={{ color: '#A8ADA8' }}>
                  {transcriptContent.length} 字
                </span>
              </div>
            </div>
          )}

          {/* AI 分析预览 */}
          <div
            className="p-4 rounded-xl space-y-3"
            style={{
              background: '#F5FAF7',
              border: '1px solid #C8D8D1'
            }}
          >
            <div className="text-sm font-bold flex items-center gap-2" style={{ color: '#3E6256' }}>
              <Sparkles className="w-4 h-4" />
              AI 将分析的 5 项能力维度
            </div>
            <div className="grid grid-cols-1 gap-2">
              {['岗位匹配度', '回答结构性', '专业技术深度', '表达清晰度', '业务判断力'].map((item) => (
                <div key={item} className="flex items-center gap-2 text-sm" style={{ color: '#737873' }}>
                  <span style={{ color: '#3E6256' }}>●</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Analysis animation */}
          {isAnalyzing && (
            <div
              className="p-4 rounded-xl space-y-3"
              style={{
                border: '1px solid #3E6256',
                background: '#F5FAF7'
              }}
            >
              <div className="text-sm font-bold flex items-center gap-2" style={{ color: '#3E6256' }}>
                <Sparkles className="w-4 h-4 animate-pulse" />
                AI 深度复盘分析中...
              </div>
              <div className="space-y-2.5">
                {analysisSteps.map((s, i) => (
                  <div key={s} className="flex items-center gap-2.5 text-sm">
                    {i <= analysisStep ? (
                      <CheckCircle2 className="w-4 h-4 shrink-0" style={{ color: '#3E6256' }} />
                    ) : (
                      <div
                        className="w-4 h-4 rounded-full shrink-0"
                        style={{ border: '1.5px solid #D0D2CB' }}
                      />
                    )}
                    <span style={{ color: i <= analysisStep ? '#202421' : '#A8ADA8' }}>
                      {s}
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
    <div className="min-h-full" style={{ background: '#F5F5F2' }}>
      <div className="max-w-[620px] mx-auto px-8 pt-8 pb-16">
        {/* Back button */}
        <button
          onClick={handleBack}
          className="flex items-center gap-2 text-sm mb-6 transition-colors"
          style={{ color: '#737873' }}
        >
          <ArrowLeft className="w-[13px] h-[13px]" />
          <span>{step === 0 ? '返回面试复盘' : '上一步'}</span>
        </button>

        {/* Header */}
        <div className="mb-6">
          <h1
            className="text-2xl font-bold"
            style={{
              color: '#202421',
              letterSpacing: '-0.4px'
            }}
          >
            新建面试复盘
          </h1>
          <p className="text-sm mt-1" style={{ color: '#737873' }}>
            复盘每一次真实面试，让下一次回答更好。
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center mb-7">
          {steps.map((s, i) => (
            <React.Fragment key={s.num}>
              <div className="flex flex-col items-center">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-[13px] font-semibold"
                  style={{
                    background:
                      step > s.num ? '#3E6256' : step === s.num ? '#202421' : '#F0F0EC',
                    color: step >= s.num ? '#FFFFFF' : '#A8ADA8'
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

        {/* Form card */}
        <div
          className="rounded-xl"
          style={{
            background: '#FFFFFF',
            border: '1px solid #E4E5E0',
            padding: '24px'
          }}
        >
          {/* Card header */}
          <div
            className="pb-4 mb-5"
            style={{ borderBottom: '1px solid #F5F5F2' }}
          >
            <h3 className="text-base font-semibold" style={{ color: '#202421' }}>
              步骤 {step + 1}：{steps[step]?.label}
            </h3>
          </div>

          {/* Card content */}
          {renderStepContent()}
        </div>

        {/* Footer */}
        {!isAnalyzing && (
          <div className="flex items-center justify-between mt-5">
            <span className="text-sm" style={{ color: '#A8ADA8' }}>
              第 {step + 1} 步 / 共 {steps.length} 步
            </span>

            <div className="flex items-center gap-3">
              {step < 2 ? (
                <button
                  onClick={handleNext}
                  disabled={!canNext()}
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-xl transition-all"
                  style={{
                    background: canNext() ? '#3E6256' : '#D0D2CB',
                    color: '#FFFFFF',
                    cursor: canNext() ? 'pointer' : 'not-allowed'
                  }}
                >
                  下一步
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <button
                  onClick={handleStartAnalysis}
                  disabled={!transcriptContent.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl transition-all"
                  style={{
                    background: transcriptContent.trim() ? '#3E6256' : '#D0D2CB',
                    color: '#FFFFFF',
                    cursor: transcriptContent.trim() ? 'pointer' : 'not-allowed'
                  }}
                >
                  <Sparkles className="w-4 h-4" />
                  开始分析
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
