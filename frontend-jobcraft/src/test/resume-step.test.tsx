import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeStep } from '../components/interview/ResumeStep';
import { ToastContainer } from '../components/common/Toast';
import type { BaseResumeRecord } from '../api/job';

const job = vi.hoisted(() => ({
  listBaseResumes: vi.fn(),
  previewResume: vi.fn(),
  confirmUpload: vi.fn(),
  createBaseResume: vi.fn(),
}));

vi.mock('../api/job', () => ({ ...job }));

const REC_1: BaseResumeRecord = {
  id: 1,
  user_id: 1,
  name: 'AI产品经理 定制版 V2.1',
  file_size: '96.4 KB',
  format: 'pdf',
  parsed_count: 12,
  tags: ['已解析', 'AI 结构化'],
  is_default: true,
  created_at: '2026-09-01T10:00:00',
  updated_at: null,
};

const REC_2: BaseResumeRecord = {
  id: 2,
  user_id: 1,
  name: '通用产品经理简历 V1.0',
  file_size: '80.1 KB',
  format: 'docx',
  parsed_count: 0,
  tags: [],
  is_default: false,
  created_at: '2026-08-20T09:00:00',
  updated_at: null,
};

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

beforeEach(() => {
  vi.resetAllMocks();
  job.listBaseResumes.mockResolvedValue([REC_1, REC_2]);
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

const renderUploadStep = (onSelectedResumeIdChange: (id: string) => void = () => {}) => {
  renderWithProviders(
    <>
      <ResumeStep
        stepNumber={3}
        resumeMode="upload"
        onResumeModeChange={() => {}}
        selectedResumeId=""
        onSelectedResumeIdChange={onSelectedResumeIdChange}
      />
      <ToastContainer />
    </>,
  );
  return screen.getByText('拖入简历文件').parentElement as HTMLElement;
};

describe('ResumeStep（C-1 拆分 + 真实简历接线）', () => {
  it('选择「从简历库选择」渲染真实底座简历列表，不再展示硬编码假简历', async () => {
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedResumeId=""
        onSelectedResumeIdChange={() => {}}
      />,
    );

    expect(await screen.findByText('AI产品经理 定制版 V2.1')).toBeInTheDocument();
    expect(screen.getByText('通用产品经理简历 V1.0')).toBeInTheDocument();
    expect(screen.queryByText('字节跳动·AI产品经理 定制版 V2.1')).not.toBeInTheDocument();
  });

  it('选中简历后展示真实名称与来源信息', async () => {
    let selected = '';
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedResumeId="hr-1"
        onSelectedResumeIdChange={(id) => {
          selected = id;
        }}
      />,
    );

    expect(await screen.findByText(/2026-09-01 10:00/)).toBeInTheDocument();
    expect(screen.getAllByText('AI产品经理 定制版 V2.1').length).toBeGreaterThan(0);
    expect(screen.getByText(/2026-09-01 10:00 · 已解析 · AI 结构化/)).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'hr-2' } });
    expect(selected).toBe('hr-2');
  });

  it('无关联简历时展示提示文案', () => {
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="none"
        onResumeModeChange={() => {}}
        selectedResumeId=""
        onSelectedResumeIdChange={() => {}}
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

  it('合法文件 → preview→confirm→createBaseResume 真实链，回填 hr-<serverId> 并选中', async () => {
    let selected = '';
    const zone = renderUploadStep((id) => {
      selected = id;
    });
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(['简历内容'], '我的简历.pdf', { type: 'application/pdf' })] },
    });

    expect(await screen.findByText('简历上传成功')).toBeInTheDocument();
    await waitFor(() => expect(selected).toBe('hr-99'));
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
