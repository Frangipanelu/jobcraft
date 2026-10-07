import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import type React from 'react';
import { renderWithProviders, createTestQueryClient } from './test-utils';
import { ToastContainer } from '../components/common/Toast';
import { ResumeVersionSwitcher } from '../components/resume/ResumeVersionSwitcher';
import { useResumeVersionsQuery, useSetCurrentVersionMutation } from '../features/resume/hooks';
import type { ResumeVersionWire } from '../api/types';

const auth = vi.hoisted(() => ({
  autoLogin: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
  getSettings: vi.fn(),
}));

const job = vi.hoisted(() => ({
  listResumeVersions: vi.fn(),
  setCurrentResumeVersion: vi.fn(),
}));

vi.mock('../api/auth', async () => ({ ...(await vi.importActual('../api/auth')), ...auth }));
vi.mock('../api/job', async () => ({ ...(await vi.importActual('../api/job')), ...job }));

const AUTH_USER = {
  id: 1,
  username: 'dev',
  display_name: null,
  email: '',
  role: '求职者',
  created_at: '2026-01-01',
};

function versionWire(overrides: Partial<ResumeVersionWire> = {}): ResumeVersionWire {
  return {
    id: 100,
    user_id: 1,
    job_id: null,
    job_analysis_id: null,
    direction_id: null,
    version_no: 1,
    version_name: null,
    sections: null,
    resume_markdown: '# 张三\n',
    selected_for_application: false,
    source_expression_refs: null,
    company: '字节跳动',
    position: 'AI 产品经理',
    created_at: '2026-09-18T08:00:00',
    updated_at: '2026-09-18T08:00:00',
    ...overrides,
  };
}

/** 同组（job_analysis_id=12）两版本 + 跨组（job_analysis_id=99）一版本，API 顺序 version_no DESC。 */
const SAME_GROUP_SELECTED = versionWire({
  id: 102,
  version_no: 2,
  version_name: 'v2 精修',
  job_analysis_id: 12,
  selected_for_application: true,
});
const SAME_GROUP_OTHER = versionWire({
  id: 101,
  version_no: 1,
  version_name: 'v1 初稿',
  job_analysis_id: 12,
  selected_for_application: false,
});
const OTHER_GROUP = versionWire({
  id: 200,
  version_no: 1,
  version_name: '腾讯版',
  job_analysis_id: 99,
});

const ALL_WIRES = [SAME_GROUP_SELECTED, SAME_GROUP_OTHER, OTHER_GROUP];

beforeEach(() => {
  vi.clearAllMocks();
  auth.autoLogin.mockResolvedValue(1);
  auth.getCurrentUser.mockResolvedValue(AUTH_USER);
  job.listResumeVersions.mockResolvedValue(ALL_WIRES);
  job.setCurrentResumeVersion.mockResolvedValue(SAME_GROUP_OTHER);
});

// ---------------------------------------------------------------------------
// hooks
// ---------------------------------------------------------------------------

const VersionsHarness: React.FC = () => {
  const { data, isError } = useResumeVersionsQuery();
  const wires = data ?? [];
  const groups = [...new Set(wires.map((w) => String(w.job_analysis_id ?? w.job_id ?? w.id)))];
  return (
    <div>
      <span data-testid="wire-count">{wires.length}</span>
      <span data-testid="group-keys">{groups.join(',')}</span>
      <span data-testid="query-state">{isError ? 'error' : 'ok'}</span>
    </div>
  );
};

const SetCurrentHarness: React.FC = () => {
  const mutation = useSetCurrentVersionMutation();
  return (
    <button type="button" onClick={() => mutation.mutate(101)} disabled={mutation.isPending}>
      触发设为当前
    </button>
  );
};

describe('T-M6-7 简历版本 hooks', () => {
  it('useResumeVersionsQuery 返回全量 wire（不归组折叠，跨组共存）', async () => {
    renderWithProviders(<VersionsHarness />);
    expect(await screen.findByText('3')).toBeInTheDocument();
    expect(screen.getByTestId('group-keys').textContent).toBe('12,99');
    expect(screen.getByTestId('query-state').textContent).toBe('ok');
  });

  it('useSetCurrentVersionMutation：以正确 id 调 API，成功后失效 resumes/jobs/resume-versions 各一次', async () => {
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');

    renderWithProviders(<SetCurrentHarness />, { queryClient: qc });

    fireEvent.click(screen.getByRole('button', { name: '触发设为当前' }));

    await waitFor(() => expect(job.setCurrentResumeVersion).toHaveBeenCalledWith(101));

    const keyCallCount = (key: readonly unknown[]) =>
      invalidateSpy.mock.calls.filter(
        (call) =>
          JSON.stringify((call[0] as { queryKey?: unknown }).queryKey) === JSON.stringify(key),
      ).length;
    await waitFor(() => {
      expect(keyCallCount(['resumes'])).toBe(1);
      expect(keyCallCount(['jobs'])).toBe(1);
      expect(keyCallCount(['resume-versions'])).toBe(1);
    });
    expect(invalidateSpy.mock.calls).toHaveLength(3);
  });

  it('列表加载失败：静默降级（无版本切换器、不崩）', async () => {
    job.listResumeVersions.mockRejectedValue(new Error('服务不可用'));
    renderWithProviders(
      <>
        <ResumeVersionSwitcher resumeId="102" />
        <ToastContainer />
      </>,
    );
    await waitFor(() => expect(job.listResumeVersions).toHaveBeenCalled());
    expect(screen.queryByTestId('resume-version-switcher')).toBeNull();
    expect(screen.queryByText('服务不可用')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 组件行为
// ---------------------------------------------------------------------------

function renderSwitcher(resumeId: string) {
  return renderWithProviders(
    <>
      <ResumeVersionSwitcher resumeId={resumeId} />
      <ToastContainer />
    </>,
  );
}

async function openList() {
  const switcher = await screen.findByTestId('resume-version-switcher');
  fireEvent.click(within(switcher).getByRole('button'));
  return screen.findByTestId('resume-version-list');
}

describe('ResumeVersionSwitcher', () => {
  it('同组两版本进列表，「当前」徽标在 selected 行，跨组版本不出现', async () => {
    renderSwitcher('102');
    expect(await screen.findByTestId('resume-version-switcher')).toBeTruthy();

    const list = await openList();
    expect(within(list).getByText('v1 初稿')).toBeInTheDocument();
    expect(within(list).getByText('v2 精修')).toBeInTheDocument();
    expect(within(list).queryByText('腾讯版')).toBeNull();

    const selectedRow = within(list).getByText('v2 精修').closest('div');
    expect(within(selectedRow as HTMLElement).getByText('当前')).toBeInTheDocument();

    const otherRow = within(list).getByText('v1 初稿').closest('div');
    expect(
      within(otherRow as HTMLElement).getByRole('button', { name: '设为当前' }),
    ).toBeInTheDocument();
    expect(within(selectedRow as HTMLElement).queryByRole('button')).toBeNull();
  });

  it('点击另一版本「设为当前」→ setCurrentResumeVersion 以该行 id 调用并成功提示', async () => {
    renderSwitcher('102');
    const list = await openList();

    fireEvent.click(within(list).getByRole('button', { name: '设为当前' }));

    await waitFor(() => expect(job.setCurrentResumeVersion).toHaveBeenCalledWith(101));
    expect(await screen.findByText('已设为当前版本')).toBeInTheDocument();
  });

  it('设为当前失败：error toast，不伪造成功提示', async () => {
    job.setCurrentResumeVersion.mockRejectedValue(new Error('版本不存在'));
    renderSwitcher('102');
    const list = await openList();

    fireEvent.click(within(list).getByRole('button', { name: '设为当前' }));

    expect(await screen.findByText('设置失败')).toBeInTheDocument();
    expect(screen.queryByText('已设为当前版本')).toBeNull();
  });

  it('resumeId 不在 wires（未知 id / 非数字本地示例）→ 不渲染', async () => {
    renderSwitcher('999');
    await waitFor(() => expect(job.listResumeVersions).toHaveBeenCalled());
    expect(screen.queryByTestId('resume-version-switcher')).toBeNull();

    renderSwitcher('local-demo');
    await waitFor(() => expect(job.listResumeVersions).toHaveBeenCalled());
    expect(screen.queryByTestId('resume-version-switcher')).toBeNull();
  });

  it('触发按钮展示当前查看版本名（version_name 缺失回退 position）', async () => {
    job.listResumeVersions.mockResolvedValue([
      versionWire({ id: 101, job_analysis_id: 12, version_name: null }),
      versionWire({ id: 103, job_analysis_id: 12, version_name: 'v3 岗位定制' }),
    ]);
    renderSwitcher('103');

    const switcher = await screen.findByTestId('resume-version-switcher');
    expect(within(switcher).getByRole('button').textContent).toContain('v3 岗位定制');
  });
});
