import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeStep } from '../components/interview/ResumeStep';
import { ToastContainer } from '../components/common/Toast';
import type { BaseResumeRecord } from '../api/job';
import type { ResumeVersionWire } from '../api/types';

const job = vi.hoisted(() => ({
  listBaseResumes: vi.fn(),
  previewResume: vi.fn(),
  confirmUpload: vi.fn(),
  createBaseResume: vi.fn(),
  listResumeVersions: vi.fn(),
}));

vi.mock('../api/job', () => ({ ...job }));

const REC_NEW: BaseResumeRecord = {
  id: 99,
  user_id: 1,
  name: '我的简历.pdf',
  file_size: '1.2 MB',
  format: 'pdf',
  parsed_count: 1,
  tags: ['已解析', 'AI 结构化'],
  is_default: false,
  created_at: '2026-09-30T10:00:00',
  updated_at: null,
};

/** 版本 wire fixture 构造器（补齐 ResumeVersionWire 必填字段，测试只覆写关心的键）。 */
function buildVersion(overrides: Partial<ResumeVersionWire>): ResumeVersionWire {
  return {
    id: 1,
    user_id: 1,
    job_id: 3,
    job_analysis_id: 42,
    direction_id: null,
    version_no: 1,
    version_name: null,
    sections: {},
    resume_markdown: null,
    selected_for_application: false,
    source_expression_refs: [],
    company: null,
    position: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

// 本岗位（job_analysis_id=42）两条版本 + 他岗（99）一条，断言客户端过滤生效
const VER_7 = buildVersion({
  id: 7,
  job_analysis_id: 42,
  version_no: 2,
  version_name: 'AI产品经理 定制版',
  selected_for_application: true,
  company: '字节跳动',
  position: 'AI 产品经理',
  created_at: '2026-09-01T10:00:00',
});
const VER_8 = buildVersion({
  id: 8,
  job_analysis_id: 42,
  version_no: 1,
  version_name: null,
  selected_for_application: false,
  created_at: '2026-08-20T09:00:00',
});
const VER_OTHER = buildVersion({
  id: 9,
  job_analysis_id: 99,
  version_no: 9,
  version_name: '他岗专属版本',
  selected_for_application: true,
  created_at: '2026-07-01T08:00:00',
});

beforeEach(() => {
  vi.resetAllMocks();
  job.listBaseResumes.mockResolvedValue([]);
  job.listResumeVersions.mockResolvedValue([VER_7, VER_8, VER_OTHER]);
  job.previewResume.mockResolvedValue({
    mode: 'structured',
    items: [
      {
        title: '端侧大模型量化评测',
        company: '未来智能实验室',
        role: 'AI 产品经理',
        period: '2025.01 - 2025.08',
        card_type: 'work',
        raw_text: '移动端端侧生成式体验的量产方案。',
        summary: '量产方案',
        selected: true,
      },
    ],
    raw_text: '移动端端侧生成式体验的量产方案。',
  });
  job.confirmUpload.mockResolvedValue({ cards: [{ id: 5 }] });
  job.createBaseResume.mockResolvedValue(REC_NEW);
});

afterEach(() => {
  vi.restoreAllMocks();
});

interface ExistingStepOpts {
  selectedVersionId?: string;
  jobAnalysisId?: number | null;
  onSelectedVersionIdChange?: (id: string) => void;
}

const renderExistingStep = ({
  selectedVersionId = '',
  jobAnalysisId = 42,
  onSelectedVersionIdChange = () => {},
}: ExistingStepOpts = {}) =>
  renderWithProviders(
    <ResumeStep
      stepNumber={3}
      resumeMode="existing"
      onResumeModeChange={() => {}}
      selectedVersionId={selectedVersionId}
      onSelectedVersionIdChange={onSelectedVersionIdChange}
      jobAnalysisId={jobAnalysisId}
    />,
  );

const renderUploadStep = (onSelectedVersionIdChange: (id: string) => void = () => {}) => {
  renderWithProviders(
    <>
      <ResumeStep
        stepNumber={3}
        resumeMode="upload"
        onResumeModeChange={() => {}}
        selectedVersionId=""
        onSelectedVersionIdChange={onSelectedVersionIdChange}
        jobAnalysisId={42}
      />
      <ToastContainer />
    </>,
  );
  return screen.getByText('拖入简历文件').parentElement as HTMLElement;
};

/** 受控 existing 步骤：把回调同时上抛给断言并驱动组件重渲染。 */
const ControlledExistingStep = ({ onChange }: { onChange: (id: string) => void }) => {
  const [id, setId] = useState('7');
  return (
    <ResumeStep
      stepNumber={3}
      resumeMode="existing"
      onResumeModeChange={() => {}}
      selectedVersionId={id}
      onSelectedVersionIdChange={(next) => {
        setId(next);
        onChange(next);
      }}
      jobAnalysisId={42}
    />
  );
};

describe('ResumeStep（H⑪/T-M7-8 关联简历切投递版本）', () => {
  it('existing 渲染本岗位投递版本列表（按 version_no 降序，他岗版本被过滤）', async () => {
    renderExistingStep();

    expect(await screen.findByText('AI产品经理 定制版（v2）')).toBeInTheDocument();
    expect(screen.getByText('版本 v1')).toBeInTheDocument();
    expect(screen.queryByText(/他岗专属版本/)).not.toBeInTheDocument();
    expect(screen.getByText('选择简历版本')).toBeInTheDocument();
  });

  it('选中版本预览名称 + 版本行 + 当前投递版徽标，切换回调收到版本 id 且徽标随选中态消失', async () => {
    let selected = '';
    renderWithProviders(<ControlledExistingStep onChange={(v) => (selected = v)} />);

    expect(await screen.findByText('AI产品经理 定制版')).toBeInTheDocument();
    expect(screen.getByText(/v2 · 2026-09-01 10:00/)).toBeInTheDocument();
    expect(screen.getByText('当前投递版')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: '8' } });
    expect(selected).toBe('8');
    await waitFor(() =>
      expect(screen.queryByText('当前投递版')).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/v1 · 2026-08-20 09:00/)).toBeInTheDocument();
  });

  it('未传 jobAnalysisId / 为 null → 空态文案，不渲染下拉', async () => {
    const first = renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedVersionId=""
        onSelectedVersionIdChange={() => {}}
      />,
    );
    expect(
      await screen.findByText('该岗位暂无简历版本，可先到简历工作台生成'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    first.unmount();

    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedVersionId=""
        onSelectedVersionIdChange={() => {}}
        jobAnalysisId={null}
      />,
    );
    expect(
      await screen.findByText('该岗位暂无简历版本，可先到简历工作台生成'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('版本列表为空时即使传了 jobAnalysisId 也走空态文案', async () => {
    job.listResumeVersions.mockResolvedValue([]);
    renderExistingStep();

    expect(
      await screen.findByText('该岗位暂无简历版本，可先到简历工作台生成'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('自愈：草稿残留/切换岗位的旧选中不属于本岗位列表 → 查询结束后自动清空', async () => {
    const onSelectedVersionIdChange = vi.fn();
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedVersionId="123"
        onSelectedVersionIdChange={onSelectedVersionIdChange}
        jobAnalysisId={42}
      />,
    );

    await waitFor(() => expect(onSelectedVersionIdChange).toHaveBeenCalledWith(''));
  });

  it('自愈不误清：本岗位有效选中保持不变', async () => {
    const onSelectedVersionIdChange = vi.fn();
    renderExistingStep({ selectedVersionId: '7', onSelectedVersionIdChange });

    expect(await screen.findByText('AI产品经理 定制版')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveValue('7');
    expect(onSelectedVersionIdChange).not.toHaveBeenCalled();
  });

  it('无关联简历时展示提示文案', () => {
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="none"
        onResumeModeChange={() => {}}
        selectedVersionId=""
        onSelectedVersionIdChange={() => {}}
        jobAnalysisId={42}
      />,
    );

    expect(screen.getByText('可以稍后在面试准备工作中关联简历')).toBeInTheDocument();
  });
});

describe('FE-UPLOAD-01 ResumeStep 上传路径（真实 preview/confirm/base-resumes 链）', () => {
  it('「浏览文件」按钮接线到隐藏文件输入', () => {
    const zone = renderUploadStep();
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click');
    try {
      fireEvent.click(screen.getByRole('button', { name: '浏览文件' }));
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(zone).toBeTruthy();
    } finally {
      clickSpy.mockRestore();
    }
  });

  it('非法文件拖入 → 报错 toast，不调用解析接口、不选中', async () => {
    const zone = renderUploadStep();
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['x'], '简历.exe', { type: 'application/octet-stream' })] },
    });

    expect(await screen.findByText('简历无法导入')).toBeInTheDocument();
    expect(screen.getByText(/不支持「\.exe」格式/)).toBeInTheDocument();
    expect(job.previewResume).not.toHaveBeenCalled();
    expect(screen.queryByText('简历上传成功')).not.toBeInTheDocument();
  });

  it('合法文件 → preview→confirm→createBaseResume 真实链 + 不回填选择（域隔离）', async () => {
    let selected = '';
    const zone = renderUploadStep((id) => {
      selected = id;
    });
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['简历内容'], '我的简历.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findByText('简历上传成功')).toBeInTheDocument();
    expect(job.previewResume).toHaveBeenCalledTimes(1);
    expect(job.confirmUpload).toHaveBeenCalledTimes(1);
    expect(job.createBaseResume).toHaveBeenCalledTimes(1);
    expect(job.previewResume.mock.invocationCallOrder[0]).toBeLessThan(
      job.confirmUpload.mock.invocationCallOrder[0],
    );
    expect(job.confirmUpload.mock.invocationCallOrder[0]).toBeLessThan(
      job.createBaseResume.mock.invocationCallOrder[0],
    );
    // 成功卡片展示真实解析结果
    expect(screen.getByText('我的简历.pdf')).toBeInTheDocument();
    expect(screen.getAllByText(/已解析 1 段经历/).length).toBeGreaterThanOrEqual(1);
    // T-M7-8：上传成功不回填选中（底座 hr- id 不得流入版本字段）
    expect(selected).toBe('');
  });

  it('断网（preview 失败）→ 报错 toast，无成功提示、不选中、不落元数据', async () => {
    job.previewResume.mockRejectedValue(new Error('Failed to fetch'));
    let selected = 'unchanged';
    const zone = renderUploadStep((id) => {
      selected = id;
    });
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['简历内容'], '我的简历.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findByText('简历上传失败')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument();
    expect(screen.queryByText('简历上传成功')).not.toBeInTheDocument();
    expect(job.createBaseResume).not.toHaveBeenCalled();
    expect(selected).toBe('unchanged');
  });

  it('元数据落库失败（断网第二段）→ 报错 toast，无成功提示、不选中', async () => {
    job.createBaseResume.mockRejectedValue(new Error('Failed to fetch'));
    let selected = 'unchanged';
    const zone = renderUploadStep((id) => {
      selected = id;
    });
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['简历内容'], '我的简历.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findByText('简历上传失败')).toBeInTheDocument();
    expect(screen.queryByText('简历上传成功')).not.toBeInTheDocument();
    expect(selected).toBe('unchanged');
  });
});
