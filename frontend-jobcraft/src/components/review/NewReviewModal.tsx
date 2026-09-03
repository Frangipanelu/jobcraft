import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  X,
  RotateCcw,
  Sparkles,
  Upload,
  Mic,
  FileText,
  Building2,
  ArrowRight
} from 'lucide-react';

interface NewReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultInterviewId?: string;
}

export const NewReviewModal: React.FC<NewReviewModalProps> = ({
  isOpen,
  onClose,
  defaultInterviewId
}) => {
  const { interviews, createReviewFromTranscript, navigateTo, showToast } = useJobCraft();

  const [selectedInterviewId, setSelectedInterviewId] = useState<string>(
    defaultInterviewId || interviews[0]?.id || 'int-byte-1'
  );
  const [uploadType, setUploadType] = useState<'text' | 'transcript' | 'audio'>('transcript');
  const [transcriptContent, setTranscriptContent] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const sampleTranscript = `【面试实录片段】
面试官：你之前负责的 LLM 评测项目中，如何解决大模型幻觉率统计不准的问题？
我：我们设计了一套 LLM-as-a-Judge 自动化评测管线，设置了多模型交叉裁判和一致性校验机制。
面试官：具体一致性如何度量？当两个裁判模型打分相反时以谁为准？
我：我们引入了 Kappa 系数度量打分一致性，当分歧率超过阈值时，自动路由给专家人工介入标注，并更新 Benchmark 黄金用例库。`;

  if (!isOpen) return null;

  const currentInterview = interviews.find((i) => i.id === selectedInterviewId);

  const handleStartReview = (e: React.FormEvent) => {
    e.preventDefault();
    const transcript = transcriptContent.trim();
    if (!transcript) return;

    setIsProcessing(true);
    // 调用真实后端创建复盘 + AI 分析，使用返回的真实数据生成复盘（无伪造评分）
    createReviewFromTranscript({
      interviewId: selectedInterviewId,
      transcript
    });

    onClose();
    navigateTo('interview_review_detail', {
      jobId: currentInterview?.jobId,
      interviewId: selectedInterviewId
    });
    setIsProcessing(false);
    showToast({
      type: 'success',
      title: '智能复盘报告已生成',
      message: '已提取考题得失，AI 分析完成后将展示真实复盘。'
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-edge shadow-xl max-w-xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="p-6 border-b border-edge flex items-center justify-between bg-canvas">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sage-soft text-sage flex items-center justify-center">
              <RotateCcw className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-ink">上传面试记录 · 生成智能复盘</h3>
              <p className="text-xs text-muted">
                支持粘贴文字问答、录音转写稿或会议记录，AI 自动完成逐题诊断与得失提炼
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-faint hover:text-ink hover:bg-page transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleStartReview} className="p-6 space-y-4">
          {/* Target Interview selector */}
          <div>
            <label className="block text-xs font-semibold text-ink mb-1">
              关联面试轮次
            </label>
            <select
              value={selectedInterviewId}
              onChange={(e) => setSelectedInterviewId(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage outline-none"
            >
              {interviews.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.company} · {i.role} · {i.roundName} ({i.time})
                </option>
              ))}
            </select>
          </div>

          {/* Mode Switch: Text vs Audio */}
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setUploadType('transcript')}
              className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                uploadType === 'transcript'
                  ? 'bg-sage-soft text-sage border-sage/40'
                  : 'border-edge text-muted hover:bg-page'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>转写文稿 / 录音纪要</span>
            </button>

            <button
              type="button"
              onClick={() => setUploadType('text')}
              className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                uploadType === 'text'
                  ? 'bg-sage-soft text-sage border-sage/40'
                  : 'border-edge text-muted hover:bg-page'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>逐题手动回忆</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setUploadType('audio');
                showToast({
                  type: 'info',
                  title: '支持音频文件或手机录音快速转写'
                });
              }}
              className={`p-2.5 rounded-xl border text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                uploadType === 'audio'
                  ? 'bg-sage-soft text-sage border-sage/40'
                  : 'border-edge text-muted hover:bg-page'
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
              <span>录音文件提取</span>
            </button>
          </div>

          {/* Text Area */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-semibold text-ink">
                面试对话与作答记录
              </label>
              <button
                type="button"
                onClick={() => setTranscriptContent(sampleTranscript)}
                className="text-[11px] text-sage hover:underline font-semibold cursor-pointer"
              >
                填入范例文稿
              </button>
            </div>
            <textarea
              required
              rows={6}
              placeholder="粘贴面试过程中的核心提问与作答记录..."
              value={transcriptContent}
              onChange={(e) => setTranscriptContent(e.target.value)}
              className="w-full p-3 text-xs rounded-xl border border-edge focus:border-sage focus:outline-none font-sans leading-relaxed resize-none bg-page text-ink"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs text-muted hover:bg-page rounded-lg transition cursor-pointer"
            >
              取消
            </button>

            <button
              type="submit"
              disabled={isProcessing}
              className="px-5 py-2 text-xs bg-sage hover:bg-sage-dim disabled:bg-edge-deep text-white font-bold rounded-lg flex items-center gap-1.5 shadow-xs transition cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isProcessing ? 'AI 正在深度复盘分析中...' : '生成智能复盘报告 →'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
