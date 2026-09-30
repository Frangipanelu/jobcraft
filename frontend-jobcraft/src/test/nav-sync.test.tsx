import { describe, expect, it } from 'vitest';
import { useEffect, useState } from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { QueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { AppRoutes } from '../router/AppRouter';
import { useJobCraft } from '../context/JobCraftContext';
import { JD_ANALYSES_QUERY_KEY } from '../features/jd/mappers';
import { JDAnalysisCenterView } from '../components/jd/JDAnalysisCenterView';
import { CreateReview } from '../pages/CreateReview';
import type { JDAnalysis } from '../types/jobcraft';
import { renderWithProviders } from './test-utils';

/** 当前 URL pathname 探针（MemoryRouter 不写 window.location，用它断言跳转结果）。 */
const PathProbe = () => {
  const location = useLocation();
  return <span data-testid="path">{location.pathname}</span>;
};

/** context 导航态探针：currentTab + jdAnalysisReturnTarget。 */
const NavStateProbe = () => {
  const { currentTab, jdAnalysisReturnTarget } = useJobCraft();
  return (
    <>
      <span data-testid="tab">{currentTab}</span>
      <span data-testid="return-target">{jdAnalysisReturnTarget ?? 'none'}</span>
    </>
  );
};

/** 直接驱动 context 导航入口的测试挂具。 */
const NavHarness = () => {
  const { navigateTo, syncTabState } = useJobCraft();
  return (
    <div>
      <button onClick={() => navigateTo('jd_analysis_center')}>去JD分析</button>
      <button onClick={() => navigateTo('jd_report', { jdId: 'jd-9' })}>去JD报告</button>
      <button onClick={() => navigateTo('job_workspace', { jobId: 'job-7' })}>去岗位空间</button>
      <button onClick={() => syncTabState('jd_report', { jdId: 'jd-9' })}>仅回填</button>
    </div>
  );
};

/** FE-STATE-01 挂具：先置位返回意图，再挂载复盘向导。 */
const FlagWizardHarness = () => {
  const { setJdAnalysisReturnTarget } = useJobCraft();
  const [showWizard, setShowWizard] = useState(false);
  useEffect(() => {
    setJdAnalysisReturnTarget('create_review');
  }, [setJdAnalysisReturnTarget]);
  if (!showWizard) {
    return <button onClick={() => setShowWizard(true)}>打开复盘向导</button>;
  }
  return <CreateReview />;
};

function buildJdAnalysis(): JDAnalysis {
  return {
    id: '12',
    jobId: 'job-1',
    company: '字节跳动',
    role: 'AI 产品经理',
    salaryRange: '面议',
    rawText: '原始 JD 文本',
    createdAt: '2026-09-01',
    matchScore: 82,
    recommendationStars: 4,
    verdictSummary: '匹配度良好',
    whyMatch: '',
    keyRisks: '',
    resumeAdvice: [],
    coreRequirements: [],
    atsKeywords: { hardSkills: [], softSkills: [], expKeywords: [], coveragePercent: 0 },
    subtextAnalysis: [],
    skillGaps: [],
    recommendedExperiences: [],
  };
}

describe('FE-NAV-01 navigateTo 真实导航（此前只改 state 不改 URL）', () => {
  it('navigateTo 触发 URL 跳转并同步 currentTab', async () => {
    const ui = renderWithProviders(
      <>
        <NavHarness />
        <PathProbe />
        <NavStateProbe />
      </>,
      { route: '/workbench' },
    );

    fireEvent.click(screen.getByText('去JD分析'));
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/jd-analysis'));
    expect(screen.getByTestId('tab').textContent).toBe('jd_analysis_center');

    fireEvent.click(screen.getByText('去JD报告'));
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/jd-report/jd-9'));

    fireEvent.click(screen.getByText('去岗位空间'));
    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/jobs/job-7'));
    expect(screen.getByTestId('tab').textContent).toBe('job_workspace');
    ui.unmount();
  });

  it('JD 分析中心「查看报告」死按钮 → /jd-report/:jdId', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData([...JD_ANALYSES_QUERY_KEY], [buildJdAnalysis()]);

    const ui = renderWithProviders(
      <>
        <JDAnalysisCenterView />
        <PathProbe />
      </>,
      { route: '/jd-analysis', queryClient },
    );

    fireEvent.click(await screen.findByText(/历史研判报告/));
    fireEvent.click(await screen.findByText('查看报告'));

    await waitFor(() => expect(screen.getByTestId('path').textContent).toBe('/jd-report/12'));
    ui.unmount();
  });

  it('syncTabState 只回填状态、不改 URL（供 useSyncRouteTab 使用）', async () => {
    renderWithProviders(
      <>
        <NavHarness />
        <PathProbe />
        <NavStateProbe />
      </>,
      { route: '/workbench' },
    );

    fireEvent.click(screen.getByText('仅回填'));

    expect(screen.getByTestId('tab').textContent).toBe('jd_report');
    expect(screen.getByTestId('path').textContent).toBe('/workbench');
  });

  it('useSyncRouteTab 在 /jobs/:jobId/jd/:jdId 别名上不反向重定向', async () => {
    renderWithProviders(
      <>
        <AppRoutes />
        <PathProbe />
        <NavStateProbe />
      </>,
      { route: '/jobs/job-1/jd/jd-1' },
    );

    await waitFor(() => expect(screen.getByTestId('tab').textContent).toBe('jd_report'));
    expect(screen.getByTestId('path').textContent).toBe('/jobs/job-1/jd/jd-1');
  });
});

describe('FE-STATE-01 jdAnalysisReturnTarget 重新进向导即作废', () => {
  it('残留返回意图在挂载复盘向导时被清理', async () => {
    renderWithProviders(
      <>
        <FlagWizardHarness />
        <NavStateProbe />
      </>,
    );

    await waitFor(() => expect(screen.getByTestId('return-target').textContent).toBe('create_review'));

    fireEvent.click(screen.getByText('打开复盘向导'));

    await waitFor(() => expect(screen.getByTestId('return-target').textContent).toBe('none'));
    expect(await screen.findByText('新建复盘')).toBeInTheDocument();
  });
});
