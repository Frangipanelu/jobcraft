import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

// jsdom 未实现 scrollTo，遗留 navigateTo 依赖它
window.scrollTo = () => {};
Element.prototype.scrollTo = () => {};

// 测试环境默认禁止真实网络：任何未 mock 的 fetch 都返回 HTTP 500（业务代码需自行 catch）
vi.stubGlobal(
  'fetch',
  vi.fn(async () =>
    new Response(
      JSON.stringify({
        error: { code: 'TEST_NETWORK_DISABLED', message: '网络请求在测试中默认禁用' },
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } },
    ),
  ),
);