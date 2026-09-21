import React from 'react';
import type { InterviewRoundType, InterviewFormat, Job } from '../../types/jobcraft';

interface InterviewDetailsStepProps {
  stepNumber: number;
  currentJob?: Job;
  roundNumber: number;
  roundType: InterviewRoundType;
  interviewTime: string;
  interviewFormat: InterviewFormat;
  platform: string;
  interviewer: string;
  onRoundChange: (num: number, name: string) => void;
  onRoundTypeChange: (value: InterviewRoundType) => void;
  onTimeChange: (value: string) => void;
  onFormatChange: (value: InterviewFormat) => void;
  onPlatformChange: (value: string) => void;
  onInterviewerChange: (value: string) => void;
}

/**
 * 面试详情步骤（standalone 第 2 步 / from-job 第 1 步）。
 * 自 NewInterviewModal 抽出：轮次/类型/时间/形式/平台/面试官表单。
 */
export const InterviewDetailsStep: React.FC<InterviewDetailsStepProps> = ({
  stepNumber,
  currentJob,
  roundNumber,
  roundType,
  interviewTime,
  interviewFormat,
  platform,
  interviewer,
  onRoundChange,
  onRoundTypeChange,
  onTimeChange,
  onFormatChange,
  onPlatformChange,
  onInterviewerChange,
}) => {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
          步骤 {stepNumber}：面试详情
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
              onRoundChange(
                rNum,
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
            onChange={(e) => onRoundTypeChange(e.target.value as InterviewRoundType)}
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
              onTimeChange(`${e.target.value} ${interviewTime.split(' ')[1] || '14:00'}`)
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
              onTimeChange(`${interviewTime.split(' ')[0] || '2026-09-02'} ${e.target.value}`)
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
            onChange={(e) => onFormatChange(e.target.value as InterviewFormat)}
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
            onChange={(e) => onPlatformChange(e.target.value)}
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
          onChange={(e) => onInterviewerChange(e.target.value)}
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
};