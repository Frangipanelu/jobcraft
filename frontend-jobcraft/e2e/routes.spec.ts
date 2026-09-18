import { test, expect } from '@playwright/test';
import { registerUser, loginUser, injectAuthToken, uniqueUser } from './helpers';

const PASSWORD = 'Test1234!';

let authToken: string;

test.beforeAll(async () => {
  const username = uniqueUser();
  await registerUser(username, PASSWORD);
  authToken = await loginUser(username, PASSWORD);
});

test.describe('FE-ROUTE-03 E2E 路由验证', () => {
  test.describe('认证与重定向', () => {
    test('未登录访问 /workbench 重定向到登录页', async ({ page }) => {
      await page.goto('/workbench');
      await expect(page.getByText('欢迎回来').first()).toBeVisible({ timeout: 15_000 });
    });

    test('登录后进入工作台', async ({ page }) => {
      await page.goto('/workbench');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('正在推进').first()).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('职业资产').first()).toBeVisible();
    });
  });

  test.describe('侧边栏导航', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/workbench');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('正在推进').first()).toBeVisible({ timeout: 15_000 });
    });

    test('点击「我的经历」→ /experiences', async ({ page }) => {
      await page.getByText('我的经历').first().click();
      await expect(page).toHaveURL(/\/experiences/);
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 10_000 });
    });

    test('点击「我的岗位」→ /jobs', async ({ page }) => {
      await page.getByText('我的岗位').first().click();
      await expect(page).toHaveURL(/\/jobs/);
      await expect(page.getByText('我的岗位申请').first()).toBeVisible({ timeout: 10_000 });
    });

    test('点击「JD 分析」→ /jd-analysis', async ({ page }) => {
      await page.getByText('JD 分析').first().click();
      await expect(page).toHaveURL(/\/jd-analysis/);
      await expect(page.getByText('全局 JD 深度分析中心').first()).toBeVisible({ timeout: 10_000 });
    });

    test('点击「面试准备」→ /prep', async ({ page }) => {
      await page.getByText('面试准备').first().click();
      await expect(page).toHaveURL(/\/prep/);
      await expect(page.getByText('面试准备中心').first()).toBeVisible({ timeout: 10_000 });
    });

    test('点击「面试复盘」→ /review', async ({ page }) => {
      await page.getByText('面试复盘').first().click();
      await expect(page).toHaveURL(/\/review/);
      await expect(page.getByText('已沉淀 0 场复盘').first()).toBeVisible({ timeout: 10_000 });
    });
  });

  test.describe('工作台卡片跳转', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/workbench');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('正在推进').first()).toBeVisible({ timeout: 15_000 });
    });

    test('「待面试」卡片 → /prep 面试准备中心', async ({ page }) => {
      await page.getByText('待面试').first().click();
      await expect(page).toHaveURL(/\/prep/);
      await expect(page.getByText('面试准备中心').first()).toBeVisible({ timeout: 10_000 });
    });

    test('「查看建议」→ /experiences 经历资产库', async ({ page }) => {
      await page.getByText('查看建议 >').click();
      await expect(page).toHaveURL(/\/experiences/);
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 10_000 });
    });
  });

  test.describe('详情路由直连', () => {
    test('直连 /experiences → 渲染经历资产库', async ({ page }) => {
      await page.goto('/experiences');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 15_000 });
    });

    test('直连 /jd-report/test-123 → 渲染 JD 报告（加载态）', async ({ page }) => {
      await page.goto('/jd-report/test-123');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('正在生成 JD 分析报告').first()).toBeVisible({ timeout: 15_000 });
    });

    test('直连 /resume → 渲染简历编辑器空态', async ({ page }) => {
      await page.goto('/resume');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('尚未生成简历').first()).toBeVisible({ timeout: 15_000 });
    });

    test('直连 /review/test-iv → 渲染复盘详情（空态）', async ({ page }) => {
      await page.goto('/review/test-iv');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('暂无本场面试的复盘报告').first()).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe('刷新保持路由', () => {
    test('刷新后仍在同一页面', async ({ page }) => {
      await page.goto('/experiences');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 15_000 });

      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/experiences/);
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 15_000 });
    });
  });

  test.describe('AppShell 内导航生效', () => {
    test('工作台两步跳转：工作台→经历资产库→刷新仍在经历资产库', async ({ page }) => {
      // 1. 进入工作台
      await page.goto('/workbench');
      await injectAuthToken(page, authToken);
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText('正在推进').first()).toBeVisible({ timeout: 15_000 });

      // 2. 跳转到经历资产库
      await page.getByText('查看建议 >').click();
      await expect(page).toHaveURL(/\/experiences/);
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 10_000 });

      // 3. 刷新后仍在经历资产库
      await page.reload();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/experiences/);
      await expect(page.getByText('经历资产库').first()).toBeVisible({ timeout: 10_000 });
    });
  });
});
