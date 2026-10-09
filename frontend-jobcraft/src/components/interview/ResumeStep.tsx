import React, { useEffect, useRef, useState } from 'react';
import { useToastActions } from '../../context/JobCraftContext';
import {
  useUploadResumeMutation,
  resumeFileError,
} from '../../features/historical-resumes/hooks';
import { useResumeVersionsQuery } from '../../features/resume/hooks';
import type { ResumeVersionWire } from '../../api/types';

export type ResumeMode = 'existing' | 'upload' | 'none';

interface ResumeStepProps {
  stepNumber: number;
  resumeMode: ResumeMode;
  onResumeModeChange: (mode: ResumeMode) => void;
  /** T-M7-8：向导显式选中的投递版本 id（字符串化数字版本 id，非底座 hr- id） */
  selectedVersionId: string;
  onSelectedVersionIdChange: (id: string) => void;
  /** 当前岗位的 job_analysis_id（版本列表客户端过滤键；缺省时列表视为空） */
  jobAnalysisId?: number | null;
  /** T-M7-8 遗留 A：空列表「去简历工作台生成」CTA 回调（由 modal 注入保存草稿+跳转逻辑） */
  onGoGenerate?: () => void;
}

/**
 * 关联简历步骤（standalone 第 3 步 / from-job 第 2 步）。
 * H⑪/T-M7-8「关联简历」切投递版本（方案 1，零 DDL/零后端改动）：
 * - 数据源 = 投递版本（useResumeVersionsQuery，与简历工作台共享缓存、不改查询 key），
 *   按当前岗位 job_analysis_id 客户端过滤，只列本岗位版本；
 * - 向导显式选中的版本经 onSelectedVersionIdChange 上交，创建时覆盖派生值；
 *   none/upload/未选则维持 mutation 内既有派生逻辑；
 * - 上传成功不再回填选中（底座 hr-<serverId> 不得流入版本字段，域隔离）；
 * - 遗留 A（2026-10-08）：空列表提供「去简历工作台生成」CTA，跳转/存草稿逻辑
 *   经 onGoGenerate 由 modal 注入（本组件不依赖路由）；
 * - FE-UPLOAD-01 上传链（preview 解析 → confirm 入库 → base-resumes 元数据）
 *   保持不变：失败报错、不出现假成功。
 */
export const ResumeStep: React.FC<ResumeStepProps> = ({
  stepNumber,
  resumeMode,
  onResumeModeChange,
  selectedVersionId,
  onSelectedVersionIdChange,
  jobAnalysisId,
  onGoGenerate,
}) => {
  const { data: allVersions = [], isPending } = useResumeVersionsQuery();
  const { showToast } = useToastActions();
  const uploadResumeMutation = useUploadResumeMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploaded, setUploaded] = useState<
    Awaited<ReturnType<typeof uploadResumeMutation.mutateAsync>> | null
  >(null);

  const versions: ResumeVersionWire[] = allVersions
    .filter(
      (v) =>
        jobAnalysisId != null &&
        v.job_analysis_id != null &&
        v.job_analysis_id === jobAnalysisId,
    )
    .sort((a, b) => b.version_no - a.version_no);
  const selected = versions.find((v) => String(v.id) === selectedVersionId);

  // T-M7-8 自愈：切换岗位或草稿残留的旧选中不属于本岗位版本列表时自动清空，
  // 防止显式覆盖把他岗版本 id 透传进场次；查询未结束前不动，避免误清。
  useEffect(() => {
    if (
      !isPending &&
      selectedVersionId &&
      !versions.some((v) => String(v.id) === selectedVersionId)
    ) {
      onSelectedVersionIdChange('');
    }
  }, [isPending, selectedVersionId, versions, onSelectedVersionIdChange]);

  const handleUploadFile = async (file: File): Promise<void> => {
    const err = resumeFileError(file);
    if (err) {
      showToast({ type: 'error', title: '简历无法导入', message: err });
      return;
    }
    try {
      const record = await uploadResumeMutation.mutateAsync(file);
      setUploaded(record);
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
          选择用于本次面试的简历版本，同一方向可沿用已有版本。
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
            {mode === 'existing' ? '选择简历版本' : mode === 'upload' ? '上传简历' : '暂不关联'}
          </button>
        ))}
      </div>

      {/* Existing resume versions（本岗位投递版本，按 version_no 降序） */}
      {resumeMode === 'existing' && (
        <div className="space-y-3">
          {versions.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-[13px]" style={{ color: '#A8ADA8' }}>
                该岗位暂无简历版本，可先到简历工作台生成
              </p>
              {onGoGenerate && (
                <button
                  type="button"
                  onClick={onGoGenerate}
                  className="mt-3 px-4 py-[7px] text-[13px] rounded-lg"
                  style={{
                    border: '1px solid #C8D8D1',
                    background: '#FFFFFF',
                    color: '#3E6256'
                  }}
                >
                  去简历工作台生成
                </button>
              )}
            </div>
          ) : (
            <>
              <select
                value={selectedVersionId}
                onChange={(e) => onSelectedVersionIdChange(e.target.value)}
                className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
                style={{
                  border: '1px solid #E4E5E0',
                  background: '#FFFFFF',
                  color: '#202421'
                }}
              >
                <option value="">请选择简历版本</option>
                {versions.map((v) => (
                  <option key={v.id} value={String(v.id)}>
                    {v.version_name
                      ? `${v.version_name}（v${v.version_no}）`
                      : `版本 v${v.version_no}`}
                  </option>
                ))}
              </select>

              {selected && (
                <div
                  className="p-3 rounded-lg"
                  style={{ background: '#FAFAF8', border: '1px solid #E4E5E0' }}
                >
                  <div className="text-[13px] font-medium" style={{ color: '#202421' }}>
                    {selected.version_name || `版本 v${selected.version_no}`}
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#A8ADA8' }}>
                    {`v${selected.version_no} · ${
                      selected.created_at
                        ? selected.created_at.slice(0, 16).replace('T', ' ')
                        : ''
                    }`}
                    {selected.selected_for_application && (
                      <span
                        className="ml-2 inline-block"
                        style={{
                          padding: '1px 6px',
                          borderRadius: '6px',
                          background: '#E5EEE9',
                          color: '#3E6256',
                          fontSize: '11px',
                          fontWeight: 500
                        }}
                      >
                        当前投递版
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
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
