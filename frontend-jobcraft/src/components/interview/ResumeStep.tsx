import React, { useState } from 'react';
import { useHistoricalResumesQuery } from '../../features/historical-resumes/hooks';

export type ResumeMode = 'existing' | 'upload' | 'none';

interface ResumeStepProps {
  stepNumber: number;
  resumeMode: ResumeMode;
  onResumeModeChange: (mode: ResumeMode) => void;
  selectedResumeId: string;
  onSelectedResumeIdChange: (id: string) => void;
}

/**
 * 关联简历步骤（standalone 第 3 步 / from-job 第 2 步）。
 * 自 NewInterviewModal 抽出并去除硬编码假简历：
 * 「从简历库选择」接真实底座简历（useHistoricalResumesQuery）；
 * 上传/暂不关联为纯本地 UI 态，保持原行为。
 */
export const ResumeStep: React.FC<ResumeStepProps> = ({
  stepNumber,
  resumeMode,
  onResumeModeChange,
  selectedResumeId,
  onSelectedResumeIdChange,
}) => {
  const { data: historicalResumes = [] } = useHistoricalResumesQuery();
  const [isDragging, setIsDragging] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: string } | null>(null);

  const selectedResume = historicalResumes.find((r) => r.id === selectedResumeId);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
          步骤 {stepNumber}：关联简历
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
            onClick={() => onResumeModeChange(mode)}
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
            onChange={(e) => onSelectedResumeIdChange(e.target.value)}
            className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
            style={{
              border: '1px solid #E4E5E0',
              background: '#FFFFFF',
              color: '#202421'
            }}
          >
            <option value="">请选择简历</option>
            {historicalResumes.map((resume) => (
              <option key={resume.id} value={resume.id}>
                {resume.name}
              </option>
            ))}
          </select>

          {selectedResume && (
            <div
              className="p-3 rounded-lg"
              style={{ background: '#FAFAF8', border: '1px solid #E4E5E0' }}
            >
              <div className="text-[13px] font-medium" style={{ color: '#202421' }}>
                {selectedResume.name}
              </div>
              <div className="text-xs mt-1" style={{ color: '#A8ADA8' }}>
                {[selectedResume.uploadDate, ...selectedResume.tags].filter(Boolean).join(' · ')}
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
};