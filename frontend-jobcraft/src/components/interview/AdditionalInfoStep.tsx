import React from 'react';
import { CheckCircle2, Loader2, Sparkles } from 'lucide-react';

interface AdditionalInfoStepProps {
  stepNumber: number;
  supplementNotes: string;
  remindUpload: boolean;
  isGenerating: boolean;
  currentAiStep: number;
  onSupplementNotesChange: (value: string) => void;
  onRemindUploadChange: (value: boolean) => void;
}

export const AI_GENERATE_ITEMS = [
  '公司背景及最新动态研究',
  '面试类型策略分析与角色推断',
  '推荐经历与话术方向',
  '高频问题及优化答案',
  '模拟面试题目'
];

/**
 * 补充信息步骤（standalone 第 4 步 / from-job 第 3 步）。
 * 自 NewInterviewModal 抽出：补充说明、复盘提醒勾选、AI 生成预览与加载动画。
 */
export const AdditionalInfoStep: React.FC<AdditionalInfoStepProps> = ({
  stepNumber,
  supplementNotes,
  remindUpload,
  isGenerating,
  currentAiStep,
  onSupplementNotesChange,
  onRemindUploadChange,
}) => {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
          步骤 {stepNumber}：补充信息
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
          onChange={(e) => onSupplementNotesChange(e.target.value)}
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
          onChange={(e) => onRemindUploadChange(e.target.checked)}
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
          {AI_GENERATE_ITEMS.map((item) => (
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
            {AI_GENERATE_ITEMS.map((item, i) => (
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
};