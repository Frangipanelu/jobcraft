import { describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { AppRoutes } from '../router/AppRouter';
import { tabToPath } from '../router/tabPaths';
import { renderWithProviders } from './test-utils';

describe('FE-ROUTE-03 tabToPath 映射', () => {
  it('无参 tab 映射到稳定 URL', () => {
    expect(tabToPath('workbench')).toBe('/workbench');
    expect(tabToPath('jobs')).toBe('/jobs');
    expect(tabToPath('jd_analysis')).toBe('/jd-analysis');
    expect(tabToPath('jd_analysis_center')).toBe('/jd-analysis');
    expect(tabToPath('interview_prep_center')).toBe('/prep');
    expect(tabToPath('create_interview')).toBe('/interview/new');
    expect(tabToPath('interview_review_center')).toBe('/review');
    expect(tabToPath('create_review')).toBe('/review/new');
    expect(tabToPath('user_profile')).toBe('/profile');
  });

  it('带参 tab 映射到对应详情 URL', () => {
    expect(tabToPath('job_workspace', { jobId: 'j1' })).toBe('/jobs/j1');
    expect(tabToPath('jd_report', { jdId: 'jd1' })).toBe('/jd-report/jd1');
    expect(tabToPath('experiences', { expId: 'e1' })).toBe('/experiences/e1');
    expect(tabToPath('experiences')).toBe('/experiences');
    expect(tabToPath('resume_editor', { jobId: 'j1' })).toBe('/resume/j1');
    expect(tabToPath('resume_editor')).toBe('/resume');
    expect(tabToPath('interview_prep_workspace', { interviewId: 'iv1' })).toBe('/prep/iv1');
    expect(tabToPath('interview_review_detail', { interviewId: 'iv1' })).toBe('/review/iv1');
  });
});

describe('FE-ROUTE-03 路由补全', () => {
  it('/experiences 与 /experiences/:id 渲染经历资产库', async () => {
    const list = renderWithProviders(<AppRoutes />, { route: '/experiences' });
    expect(await list.findByText('经历资产库')).toBeInTheDocument();
    list.unmount();

    const detail = renderWithProviders(<AppRoutes />, { route: '/experiences/exp-1' });
    expect(await detail.findByText('经历资产库')).toBeInTheDocument();
  });

  it('/jd-analysis 渲染 JD 分析中心（遗留视图 + URL）', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/jd-analysis' });
    expect(await ui.findByText('全局 JD 深度分析中心')).toBeInTheDocument();
  });

  it('/prep 渲染面试准备中心', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/prep' });
    expect(await ui.findByText('面试准备中心')).toBeInTheDocument();
  });

  it('/prep/:interviewId 渲染面试准备空间', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/prep/iv-1' });
    expect(await ui.findByText('返回面试准备中心')).toBeInTheDocument();
  });

  it('/review 渲染面试复盘中心', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/review' });
    expect(await ui.findByText('已沉淀 0 场复盘')).toBeInTheDocument();
  });

  it('/review/:interviewId 渲染复盘详情', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/review/iv-1' });
    expect(await ui.findByText('暂无本场面试的复盘报告')).toBeInTheDocument();
  });

  it('/jd-report/:jdId 渲染 JD 报告路由页', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/jd-report/jd-1' });
    expect(await ui.findByText('正在生成 JD 分析报告...')).toBeInTheDocument();
  });

  it('/jobs/:jobId/jd/:jdId 别名同样渲染 JD 报告路由页', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/jobs/job-1/jd/jd-1' });
    expect(await ui.findByText('正在生成 JD 分析报告...')).toBeInTheDocument();
  });

  it('/interview/new 渲染新建面试，/review/new 渲染新建复盘', async () => {
    const createInterview = renderWithProviders(<AppRoutes />, { route: '/interview/new' });
    expect(await createInterview.findByText('新建面试')).toBeInTheDocument();
    createInterview.unmount();

    const createReview = renderWithProviders(<AppRoutes />, { route: '/review/new' });
    expect(await createReview.findByText('新建复盘')).toBeInTheDocument();
  });

  it('/resume 渲染简历编辑器空态', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/resume' });
    expect(await ui.findByText(/尚未生成简历/)).toBeInTheDocument();
  });

  it('未知路径重定向到 /workbench', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/definitely-missing' });
    expect(await ui.findByText('正在推进')).toBeInTheDocument();
  });
});

describe('FE-ROUTE-03 AppShell 内导航生效（真实路由跳转）', () => {
  it('工作台「待面试」卡片 → /prep 面试准备中心', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/workbench' });

    fireEvent.click(await ui.findByText('待面试'));

    expect(await ui.findByText('面试准备中心')).toBeInTheDocument();
  });

  it('工作台「查看建议」→ /experiences 经历资产库', async () => {
    const ui = renderWithProviders(<AppRoutes />, { route: '/workbench' });

    fireEvent.click(await ui.findByText('查看建议 >'));

    await waitFor(() => expect(ui.getByText('经历资产库')).toBeInTheDocument());
  });
});
