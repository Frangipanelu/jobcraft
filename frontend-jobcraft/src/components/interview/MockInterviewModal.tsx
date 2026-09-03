import React, { useState, useEffect, useRef } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  X,
  Sparkles,
  Send,
  CheckCircle2
} from 'lucide-react';
import * as interviewApi from '../../api/interview';

interface MockInterviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  interviewId?: string;
}

interface ChatMsg {
  role: 'user' | 'interviewer';
  content: string;
}

function toReviewTranscript(messages: ChatMsg[]): string {
  return messages
    .map((m) => (m.role === 'interviewer' ? `面试官：${m.content}` : `候选人：${m.content}`))
    .join('\n\n');
}

export const MockInterviewModal: React.FC<MockInterviewModalProps> = ({
  isOpen,
  onClose,
  interviewId
}) => {
  const { interviews, navigateTo, showToast } = useJobCraft();
  const currentInterview = interviews.find((i) => i.id === interviewId) || interviews[0];

  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [candidateInput, setCandidateInput] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);

  const company = currentInterview?.company || '';
  const position = currentInterview?.role || '';
  const roundType = currentInterview?.roundName || '技术面';

  // 打开弹窗即向后端发起首轮对话，由 AI 面试官开场
  useEffect(() => {
    if (!isOpen) return;
    if (startedRef.current) return;
    startedRef.current = true;
    setMessages([]);
    setCandidateInput('');
    setIsStarting(true);
    interviewApi
      .mockChat({ messages: [], company, position, round_type: roundType })
      .then((res) => {
        setMessages([{ role: 'interviewer', content: res.reply }]);
      })
      .catch((err) => {
        showToast({
          type: 'error',
          title: '模拟面试启动失败',
          message: (err as Error).message || '请稍后重试'
        });
        setMessages([{ role: 'interviewer', content: '你好，请做一个简短的自我介绍，然后我们开始本场面试。' }]);
      })
      .finally(() => setIsStarting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isStarting, isSending]);

  if (!isOpen) return null;

  const handleSend = async () => {
    const text = candidateInput.trim();
    if (!text || isSending || isStarting) return;

    const nextMessages: ChatMsg[] = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setCandidateInput('');
    setIsSending(true);
    try {
      const res = await interviewApi.mockChat({
        messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
        company,
        position,
        round_type: roundType
      });
      setMessages((prev) => [...prev, { role: 'interviewer', content: res.reply }]);
    } catch (err) {
      showToast({
        type: 'error',
        title: '面试官回复失败',
        message: (err as Error).message || '请稍后重试'
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleComplete = async () => {
    if (isCompleting || messages.length === 0) return;
    setIsCompleting(true);
    try {
      const transcript = toReviewTranscript(messages);
      const result = await interviewApi.createInterviewReview({
        title: `${company || '模拟'} 模拟面试复盘`,
        company,
        position,
        round_type: roundType,
        raw_text: transcript
      });
      showToast({
        type: 'success',
        title: '模拟面试已保存为复盘',
        message: result.qa_pair_count ? `已生成 ${result.qa_pair_count} 条问答复盘。` : '已生成复盘记录。'
      });
      onClose();
      navigateTo('interview_review_center');
    } catch (err) {
      showToast({
        type: 'error',
        title: '保存复盘失败',
        message: (err as Error).message || '请稍后重试'
      });
    } finally {
      setIsCompleting(false);
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
                AI 模拟面试实战 · 实时对话
              </h3>
              <p className="text-[11px] text-muted">
                {currentInterview?.company || '目标公司'} · {roundType}
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

        {/* Chat Body */}
        <div ref={scrollRef} className="p-6 space-y-4 overflow-y-auto flex-1 custom-scrollbar">
          {isStarting ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-ink text-white flex items-center justify-center text-xs font-bold font-mono">
                AI
              </div>
              <span className="text-xs text-muted">面试官正在准备开场...</span>
            </div>
          ) : (
            messages.map((m, idx) =>
              m.role === 'interviewer' ? (
                <div key={idx} className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-ink text-white flex items-center justify-center shrink-0 text-xs font-bold font-mono">
                    AI
                  </div>
                  <div className="space-y-1.5 flex-1">
                    <div className="text-xs font-semibold text-muted">面试官：</div>
                    <div className="p-4 rounded-2xl rounded-tl-none bg-page text-ink text-sm font-medium leading-relaxed shadow-2xs border border-edge whitespace-pre-wrap">
                      {m.content}
                    </div>
                  </div>
                </div>
              ) : (
                <div key={idx} className="flex items-start gap-3 justify-end">
                  <div className="space-y-1.5 flex-1 max-w-[80%]">
                    <div className="text-xs font-semibold text-muted text-right">我：</div>
                    <div className="p-4 rounded-2xl rounded-tr-none bg-sage text-white text-sm font-medium leading-relaxed shadow-2xs whitespace-pre-wrap">
                      {m.content}
                    </div>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-sage-soft text-sage flex items-center justify-center shrink-0 text-xs font-bold">
                    我
                  </div>
                </div>
              )
            )
          )}

          {isSending && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="w-3.5 h-3.5 rounded-full border-2 border-edge border-t-sage animate-spin" />
              面试官正在思考回复...
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-edge bg-canvas space-y-3">
          <textarea
            rows={3}
            placeholder="输入你的现场回答，然后发送..."
            value={candidateInput}
            onChange={(e) => setCandidateInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            className="w-full p-3.5 text-xs rounded-xl border border-edge focus:border-sage focus:outline-none font-sans leading-relaxed resize-none bg-white text-ink"
          />

          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 text-xs text-slate-500 hover:bg-slate-200 rounded-lg transition cursor-pointer"
            >
              退出模拟
            </button>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={handleComplete}
                disabled={isCompleting || messages.length === 0}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 disabled:bg-edge-deep text-white text-xs font-semibold shadow-xs transition cursor-pointer"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{isCompleting ? '正在保存复盘...' : '完成并生成复盘'}</span>
              </button>

              <button
                type="button"
                onClick={handleSend}
                disabled={!candidateInput.trim() || isSending || isStarting}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sage hover:bg-sage-dim disabled:bg-edge-deep text-white text-xs font-semibold shadow-xs transition cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSending ? '发送中…' : '发送回答'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};