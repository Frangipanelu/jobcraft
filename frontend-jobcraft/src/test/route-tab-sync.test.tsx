import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { AppRoutes } from '../router/AppRouter';
import { useJobCraft } from '../context/JobCraftContext';
import { renderWithProviders } from './test-utils';

/** context 导航态探针：currentTab。 */
const TabProbe = () => {
  const { currentTab } = useJobCraft();
  return <span data-testid="tab">{currentTab}</span>;
};

describe('FE-TAB-01 路由 → currentTab 回填（14 条路由侧栏/面包屑地基）', () => {
  const cases: [string, string][] = [
    ['/workbench', 'workbench'],
    ['/jobs', 'jobs'],
    ['/jobs/job-1', 'job_workspace'],
    ['/jd-analysis', 'jd_analysis_center'],
    ['/jd-report/jd-1', 'jd_report'],
    ['/experiences', 'experiences'],
    ['/experiences/exp-1', 'experiences'],
    ['/resume/job-1', 'resume_editor'],
    ['/prep', 'interview_prep_center'],
    ['/prep/iv-1', 'interview_prep_workspace'],
    ['/interview/new', 'create_interview'],
    ['/review', 'interview_review_center'],
    ['/review/iv-1', 'interview_review_detail'],
    ['/review/new', 'create_review'],
    ['/profile', 'user_profile'],
  ];

  it.each(cases)('%s 回填 currentTab=%s', async (route, expectedTab) => {
    renderWithProviders(
      <>
        <AppRoutes />
        <TabProbe />
      </>,
      { route },
    );

    await waitFor(() => expect(screen.getByTestId('tab').textContent).toBe(expectedTab));
  });

  it('/jd-analysis 侧栏「JD 分析」高亮', async () => {
    renderWithProviders(
      <>
        <AppRoutes />
        <TabProbe />
      </>,
      { route: '/jd-analysis' },
    );

    await waitFor(() => expect(screen.getByTestId('tab').textContent).toBe('jd_analysis_center'));
    const sidebarItem = screen.getByText('JD 分析').closest('button');
    expect(sidebarItem?.className).toContain('bg-sage');
  });
});
