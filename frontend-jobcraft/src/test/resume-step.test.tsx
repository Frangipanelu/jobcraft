import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from './test-utils';
import { ResumeStep } from '../components/interview/ResumeStep';
import type { HistoricalResume } from '../types/jobcraft';

const historicalResumesApi = vi.hoisted(() => ({
  useHistoricalResumesQuery: vi.fn(),
}));

vi.mock('../features/historical-resumes/hooks', () => historicalResumesApi);

const RESUMES: HistoricalResume[] = [
  {
    id: 'hr-1',
    serverId: 1,
    name: 'AI产品经理 定制版 V2.1',
    uploadDate: '2026-09-01 10:00',
    fileSize: '96.4 KB',
    isDefault: true,
    parsedExperiencesCount: 12,
    format: 'pdf',
    tags: ['已解析', 'AI 结构化'],
  },
  {
    id: 'hr-2',
    serverId: 2,
    name: '通用产品经理简历 V1.0',
    uploadDate: '2026-08-20 09:00',
    fileSize: '80.1 KB',
    isDefault: false,
    parsedExperiencesCount: 0,
    format: 'docx',
    tags: ['已上传'],
  },
];

beforeEach(() => {
  vi.resetAllMocks();
  historicalResumesApi.useHistoricalResumesQuery.mockReturnValue({ data: RESUMES });
});

describe('ResumeStep（C-1 拆分 + 真实简历接线）', () => {
  it('选择「从简历库选择」渲染真实底座简历列表，不再展示硬编码假简历', () => {
    renderWithProviders(
      <ResumeStep
        stepNumber={3}
        resumeMode="existing"
        onResumeModeChange={() => {}}
        selectedResumeId=""
        onSelectedResumeIdChange={() => {}}
      />,
    );

    expect(screen.getByText('AI产品经理 定制版 V2.1')).toBeInTheDocument();
    expect(screen.getByText('通用产品经理简历 V1.0')).toBeInTheDocument();
    expect(screen.queryByText('字节跳动·AI产品经理 定制版 V2.1')).not.toBeInTheDocument();
  });

  it('选中简历后展示真实名称与来源信息', () => {
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