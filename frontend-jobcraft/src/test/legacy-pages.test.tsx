import { describe, expect, it } from 'vitest';
import { renderWithProviders } from './test-utils';
import { WorkbenchView } from '../components/workbench/WorkbenchView';
import { JobsListView } from '../components/jobs/JobsListView';
import { ExperiencesView } from '../components/experiences/ExperiencesView';
import { UserProfileView } from '../components/user/UserProfileView';

describe('遗留视图可独立渲染', () => {
  it('WorkbenchView 渲染', async () => {
    const ui = renderWithProviders(<WorkbenchView onOpenNewJob={() => {}} />);
    expect(await ui.findByText('正在推进')).toBeInTheDocument();
  });

  it('JobsListView 渲染', async () => {
    const ui = renderWithProviders(<JobsListView onOpenNewJob={() => {}} />);
    expect(await ui.findByText('我的岗位申请')).toBeInTheDocument();
  });

  it('ExperiencesView 渲染', () => {
    const ui = renderWithProviders(<ExperiencesView />);
    expect(ui.getByText('经历资产库')).toBeInTheDocument();
  });

  it('UserProfileView 渲染', () => {
    const ui = renderWithProviders(<UserProfileView />);
    expect(ui.getByText('账号设置')).toBeInTheDocument();
  });
});