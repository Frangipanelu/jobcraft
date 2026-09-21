import React, { useState } from 'react';
import { useToastActions } from '../../context/JobCraftContext';
import { useCreateJdAnalysisMutation } from '../../features/jd/hooks';
import { useCreateJobMutation } from '../../features/jobs/hooks';
import type { Job } from '../../types/jobcraft';

interface JobSelectionStepProps {
  jobs: Job[];
  selectedJobId: string;
  onSelectJob: (id: string) => void;
  onOpenJDAnalysis: () => void;
}

/**
 * 步骤 1（standalone 模式）：关联岗位。
 * 自 NewInterviewModal 抽出：岗位下拉 + 「新建岗位」内联表单（含 JD 分析双写回填）。
 */
export const JobSelectionStep: React.FC<JobSelectionStepProps> = ({
  jobs,
  selectedJobId,
  onSelectJob,
  onOpenJDAnalysis,
}) => {
  const { showToast } = useToastActions();
  const createJobMutation = useCreateJobMutation();
  const createJdAnalysis = useCreateJdAnalysisMutation();

  const [newJobCompany, setNewJobCompany] = useState('');
  const [newJobRole, setNewJobRole] = useState('');
  const [newJobJD, setNewJobJD] = useState('');
  const [showNewJobForm, setShowNewJobForm] = useState(false);

  const handleCreateJob = async () => {
    if (!newJobCompany.trim() || !newJobRole.trim()) {
      showToast({
        type: 'warning',
        title: '请填写完整信息',
        message: '公司名称和岗位名称不能为空'
      });
      return;
    }

    // Create job directly
    const newJob = await createJobMutation.mutateAsync({
      company: newJobCompany.trim(),
      role: newJobRole.trim(),
    });

    // Create JD analysis record (fire-and-forget，完成后回填岗位 jdAnalysisId)
    createJdAnalysis.mutate(
      {
        company: newJobCompany.trim(),
        role: newJobRole.trim(),
        rawText: newJobJD.trim() || '待补充JD内容',
        jobId: newJob.id
      },
      {
        onSuccess: (analysis) => {
          showToast({
            type: 'success',
            title: 'JD 分析报告已生成',
            message: `已解析「${analysis.company} · ${analysis.role}」，匹配度达 ${analysis.matchScore || 0}%。`
          });
        },
        onError: (error) => {
          console.error('JD analysis failed:', error);
          showToast({
            type: 'error',
            title: 'JD 分析失败',
            message: (error as Error).message || '请稍后重试'
          });
        }
      }
    );

    // Select the new job
    onSelectJob(newJob.id);
    setShowNewJobForm(false);
    setNewJobCompany('');
    setNewJobRole('');
    setNewJobJD('');

    showToast({
      type: 'success',
      title: '岗位已创建',
      message: '已自动创建岗位和JD记录，请继续完善信息'
    });
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold" style={{ color: '#202421' }}>
          步骤 1：关联岗位
        </h3>
        <p className="text-xs mt-1" style={{ color: '#737873' }}>
          选择要关联的岗位，或新建一个岗位。
        </p>
      </div>

      {/* Job dropdown */}
      <div>
        <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
          选择岗位
        </label>
        <select
          value={selectedJobId}
          onChange={(e) => {
            onSelectJob(e.target.value);
            setShowNewJobForm(false);
          }}
          className="w-full px-3 py-[9px] text-[13.5px] rounded-lg outline-none"
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
        <div className="flex gap-2">
          <button
            onClick={() => setShowNewJobForm(true)}
            className="flex-1 py-2.5 px-3.5 rounded-lg text-[13px] font-medium transition-all"
            style={{
              border: '1px dashed #C8D8D1',
              background: 'transparent',
              color: '#3E6256'
            }}
          >
            + 新建岗位
          </button>
          <button
            onClick={onOpenJDAnalysis}
            className="py-2.5 px-4 rounded-lg text-[13px] font-medium transition-all"
            style={{
              border: '1px solid #3E6256',
              background: '#FFFFFF',
              color: '#3E6256'
            }}
          >
            去JD分析页面创建
          </button>
        </div>
      ) : (
        <div
          className="p-4 rounded-[10px] space-y-3"
          style={{
            border: '1.5px solid #3E6256',
            background: '#F5FAF7'
          }}
        >
          <div className="text-[13px] font-semibold" style={{ color: '#202421' }}>
            新建岗位
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="公司名称"
              value={newJobCompany}
              onChange={(e) => setNewJobCompany(e.target.value)}
              className="px-3 py-2 text-[13px] rounded-lg outline-none"
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
              className="px-3 py-2 text-[13px] rounded-lg outline-none"
              style={{
                border: '1px solid #E4E5E0',
                background: '#FFFFFF',
                color: '#202421'
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-[5px]" style={{ color: '#737873' }}>
              JD详情（可选）
            </label>
            <textarea
              rows={4}
              placeholder="粘贴岗位描述JD内容，用于AI分析..."
              value={newJobJD}
              onChange={(e) => setNewJobJD(e.target.value)}
              className="w-full px-3 py-2 text-[13px] rounded-lg outline-none resize-none"
              style={{
                border: '1px solid #E4E5E0',
                background: '#FFFFFF',
                color: '#202421',
                lineHeight: 1.6
              }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setShowNewJobForm(false);
                setNewJobCompany('');
                setNewJobRole('');
                setNewJobJD('');
              }}
              className="flex-1 py-2 text-[13px] rounded-lg transition-all"
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
              className="flex-1 py-2 text-[13px] font-medium rounded-lg transition-all"
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
    </div>
  );
};