import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  X,
  Sparkles,
  Mic,
  MicOff,
  Send,
  ArrowRight,
  TrendingUp,
  Volume2,
  CheckCircle2,
  RotateCcw
} from 'lucide-react';

interface MockInterviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  interviewId?: string;
}

export const MockInterviewModal: React.FC<MockInterviewModalProps> = ({
  isOpen,
  onClose,
  interviewId = 'int-byte-2'
}) => {
  const { interviews } = useJobCraft();
  const currentInterview = interviews.find((i) => i.id === interviewId) || interviews[0];

  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [candidateInput, setCandidateInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [feedback, setFeedback] = useState<{
    structure: number;
    relevance: number;
    expression: number;
    completeness: number;
    advice: string;
  } | null>(null);

  const mockQuestions = [
    {
      q: '你好，请做个简短自我介绍，重点讲讲你在生成式 AI 搜索和 Eval 质量评测方向的实战成果。',
      sampleAnswer: '面试官你好，我是菁菁。过去 2 年在快知智能主导从 0 到 1 搭建了涵盖 15 个垂类的 LLM-as-a-Judge 自动化评测管线。通过多模型交叉校验与指标量化，推动模型检索幻觉率下降 34.2%，NDCG@5 提升 18.5%，评测周期由 2 周缩短至 4 小时以内。'
    },
    {
      q: '在大模型搜索中，当检索到的 Top-K 文档包含互相冲突的信息时，你作为 PM 会设计怎样的策略处理？',
      sampleAnswer: '分四步处理：首先在检索层对信源进行权威度 Tier 分级；其次引入时效性衰减因子；若无法裁定，在生成层客观呈现多元观点；最后在交互端强制提供溯源出处高亮。'
    },
    {
      q: '如果端到端大模型生成耗时达到了 2.5 秒，而业务要求必须压到 1.2 秒内，你会从哪些环节做裁剪优化？',
      sampleAnswer: '我们从物理耗时与感知耗时双向切入。引入 Semantic Cache 对高频词实现秒开；流水线并行化 Embedding 与 BM25；并在交互层采用打字机流式渲染，将首字延迟 TTFT 压到 400ms 内。'
    }
  ];

  if (!isOpen) return null;

  const currentQ = mockQuestions[currentQIndex] || mockQuestions[0];

  const handleSendAnswer = () => {
    if (!candidateInput.trim()) return;

    setIsEvaluating(true);
    setTimeout(() => {
      setIsEvaluating(false);
      setFeedback({
        structure: Math.floor(78 + Math.random() * 12),
        relevance: Math.floor(84 + Math.random() * 12),
        expression: Math.floor(75 + Math.random() * 14),
        completeness: Math.floor(70 + Math.random() * 18),
        advice:
          '回答逻辑非常严密，直接命中了考点的核心解决路径！建议：在结尾可以再主动提及一次团队协作或监控兜底机制，让方案更具闭环感。'
      });
    }, 1000);
  };

  const handleUsePresetAnswer = () => {
    setCandidateInput(currentQ.sampleAnswer);
  };

  const handleNextQuestion = () => {
    if (currentQIndex < mockQuestions.length - 1) {
      setCurrentQIndex(currentQIndex + 1);
      setCandidateInput('');
      setFeedback(null);
    } else {
      // Completed all mock questions
      setCurrentQIndex(0);
      setCandidateInput('');
      setFeedback(null);
      onClose();
    }
  };

  const handleToggleRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      setTimeout(() => {
        setCandidateInput(currentQ.sampleAnswer);
        setIsRecording(false);
      }, 2500);
    } else {
      setIsRecording(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-edge shadow-xl max-w-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-edge flex items-center justify-between bg-canvas">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sage-soft text-sage flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-ink">
                AI 模拟面试实战 · 第 {currentQIndex + 1} / {mockQuestions.length} 题
              </h3>
              <p className="text-[11px] text-muted">
                {currentInterview.company} · {currentInterview.roundName}
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

        {/* Content Body */}
        <div className="p-6 space-y-6 overflow-y-auto flex-1 custom-scrollbar">
          {/* AI Interviewer Bubble */}
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-ink text-white flex items-center justify-center shrink-0 text-xs font-bold font-mono">
              AI
            </div>
            <div className="space-y-1.5 flex-1">
              <div className="text-xs font-semibold text-muted">面试官：</div>
              <div className="p-4 rounded-2xl rounded-tl-none bg-page text-ink text-sm font-medium leading-relaxed shadow-2xs border border-edge">
                {currentQ.q}
              </div>
            </div>
          </div>

          {/* User Input / Response Area */}
          <div className="space-y-3 pl-11">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-ink">你的回答：</span>
              <button
                type="button"
                onClick={handleUsePresetAnswer}
                className="text-[11px] text-sage hover:underline font-semibold cursor-pointer"
              >
                快速填入参考回答
              </button>
            </div>

            <textarea
              rows={4}
              placeholder="输入你的现场回答，或点击下方麦克风模拟语音录音..."
              value={candidateInput}
              onChange={(e) => setCandidateInput(e.target.value)}
              className="w-full p-3.5 text-xs rounded-xl border border-edge focus:border-sage focus:outline-none font-sans leading-relaxed resize-none bg-white text-ink"
            />

            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={handleToggleRecording}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition cursor-pointer ${
                  isRecording
                    ? 'bg-error-bg text-error border-error/40 animate-pulse'
                    : 'bg-white text-ink border-edge hover:bg-page'
                }`}
              >
                {isRecording ? <MicOff className="w-3.5 h-3.5 text-error" /> : <Mic className="w-3.5 h-3.5 text-muted" />}
                <span>{isRecording ? '正在语音识别录入...' : '语音录入回答'}</span>
              </button>

              <button
                type="button"
                onClick={handleSendAnswer}
                disabled={!candidateInput.trim() || isEvaluating}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sage hover:bg-sage-dim disabled:bg-edge-deep text-white text-xs font-semibold shadow-xs transition cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isEvaluating ? 'AI 正在多维评估...' : '提交评估回答'}</span>
              </button>
            </div>
          </div>

          {/* AI Instant Feedback Evaluation Card (Section 15.9) */}
          {feedback && (
            <div className="pl-11 space-y-3 animate-in fade-in">
              <div className="p-4 rounded-xl bg-page border border-edge space-y-3">
                <div className="flex items-center justify-between border-b border-edge pb-2">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-sage" />
                    <h4 className="text-xs font-bold text-ink">AI 实时作答评分</h4>
                  </div>
                  <span className="text-xs font-bold text-sage">
                    综合得分 {Math.round((feedback.structure + feedback.relevance + feedback.expression + feedback.completeness) / 4)} / 100
                  </span>
                </div>

                {/* 4 Score Metrics */}
                <div className="grid grid-cols-4 gap-2 text-center text-xs">
                  <div className="p-2 bg-white rounded-lg border border-edge">
                    <div className="text-[10px] text-faint">结构逻辑</div>
                    <div className="font-bold text-ink mt-0.5">{feedback.structure}</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-edge">
                    <div className="text-[10px] text-faint">岗位相关性</div>
                    <div className="font-bold text-sage mt-0.5">{feedback.relevance}</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-edge">
                    <div className="text-[10px] text-faint">表达清晰</div>
                    <div className="font-bold text-ink mt-0.5">{feedback.expression}</div>
                  </div>
                  <div className="p-2 bg-white rounded-lg border border-edge">
                    <div className="text-[10px] text-faint">证据完整度</div>
                    <div className="font-bold text-warning mt-0.5">{feedback.completeness}</div>
                  </div>
                </div>

                <div className="text-xs text-ink bg-white p-3 rounded-lg border border-edge leading-relaxed font-medium">
                  <strong className="text-sage font-bold">改进建议：</strong> {feedback.advice}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Next Button */}
        <div className="p-4 border-t border-edge flex items-center justify-between bg-canvas">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs text-slate-500 hover:bg-slate-200 rounded-lg transition"
          >
            退出模拟
          </button>

          <button
            onClick={handleNextQuestion}
            className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-xs transition"
          >
            <span>{currentQIndex < mockQuestions.length - 1 ? '下一题 →' : '完成模拟练习 ✓'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
