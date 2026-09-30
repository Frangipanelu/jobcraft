import React, { useRef, useState } from 'react';
import { useToastActions } from '../../context/JobCraftContext';
import {
  useHistoricalResumesQuery,
  useUploadResumeMutation,
  resumeFileError,
} from '../../features/historical-resumes/hooks';
import type { HistoricalResume } from '../../types/jobcraft';

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
 * FE-UPLOAD-01：上传接真实链（preview 解析 → confirm 入库 → base-resumes 元数据），
 * 成功后回填真实 id（hr-<serverId>）并选中，失败报错、不出现假成功。
 */
export const ResumeStep: React.FC<ResumeStepProps> = ({
  stepNumber,
  resumeMode,
  onResumeModeChange,
  selectedResumeId,
  onSelectedResumeIdChange,
}) => {
  const { data: historicalResumes = [] } = useHistoricalResumesQuery();
  const { showToast } = useToastActions();
  const uploadResumeMutation = useUploadResumeMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploaded, setUploaded] = useState<HistoricalResume | null>(null);

  const selectedResume = historicalResumes.find((r) => r.id === selectedResumeId);

  const handleUploadFile = async (file: File): Promise<void> => {
    const err = resumeFileError(file);
    if (err) {
      showToast({ type: 'error', title: '简历无法导入', message: err });
      return;
    }
    try {
      const record = await uploadResumeMutation.mutateAsync(file);
      setUploaded(record);
      onSelectedResumeIdChange(record.id);
      showToast({
        type: 'success',
        title: '简历上传成功',
        message:
          record.parsedExperiencesCount > 0
            ? `已解析 ${record.parsedExperiencesCount} 段经历并自动选中「${file.name}」。`
            : `已保存「${file.name}」，未解析出结构化经历。`
      });
    } catch (error) {
      showToast({
        type: 'error',
        title: '简历上传失败',
        message: (error as Error).message || '请检查网络后重试'
      });
    }
  };

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
            const file = e.dataTransfer.files?.[0];
            if (file) void handleUploadFile(file);
          }}
        >
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.docx,.md,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) void handleUploadFile(file);
            }}
          />
          <div className="text-4xl mb-2">📄</div>
          <div className="text-sm font-semibold mb-1" style={{ color: '#202421' }}>
            拖入简历文件
          </div>
          <div className="text-xs mb-3" style={{ color: '#A8ADA8' }}>
            支持 PDF / DOCX / MD / TXT，≤10MB
          </div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadResumeMutation.isPending}
            className="px-4 py-[7px] text-[13px] rounded-lg disabled:opacity-60"
            style={{
              border: '1px solid #C8D8D1',
              background: '#FFFFFF',
              color: '#3E6256'
            }}
          >
            {uploadResumeMutation.isPending ? '解析中...' : '浏览文件'}
          </button>

          {uploaded && (
            <div className="mt-3 p-2 rounded-lg" style={{ background: '#F5FAF7' }}>
              <div className="text-[13px] font-medium" style={{ color: '#202421' }}>
                {uploaded.name}
              </div>
              <div className="text-xs" style={{ color: '#A8ADA8' }}>
                {uploaded.fileSize} ·{' '}
                {uploaded.parsedExperiencesCount > 0
                  ? `已解析 ${uploaded.parsedExperiencesCount} 段经历`
                  : '未解析出结构化经历'}
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