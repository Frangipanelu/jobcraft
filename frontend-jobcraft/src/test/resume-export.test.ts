import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  resumeToMarkdown,
  normalizeStructuredSections,
} from '../utils/resumeParser';
import { triggerBlobDownload, downloadElementAsHtml } from '../utils/download';
import type { ResumeVersion } from '../types/jobcraft';

function baseResume(sections: ResumeVersion['sections']): ResumeVersion {
  return {
    id: '100',
    jobTitle: 'AI 产品经理',
    company: '字节跳动',
    versionName: 'v1',
    updatedAt: '刚刚',
    personalInfo: {
      name: '张三',
      email: 'z@x.com',
      phone: '13812345678',
      title: '产品经理',
      location: '北京',
    },
    summary: 'A、B、C',
    sections,
  };
}

const WORK = {
  id: 'sec-work',
  title: '工作经历',
  items: [
    {
      id: 'item-a',
      title: '字节跳动 · 产品经理 · 2022.04-至今',
      bullets: [{ id: 'b1', text: '主导 RAG 评测体系搭建' }],
    },
  ],
};

const EDU = {
  id: 'sec-edu',
  title: '教育经历',
  items: [
    {
      id: 'item-b',
      title: '北京大学 · 计算机 · 2015-2019',
      bullets: [{ id: 'b2', text: '理学学士' }],
    },
  ],
};

describe('resumeToMarkdown 导出（T-M6-4：可见模块语义）', () => {
  it('多模块全部导出（教育经历不再被单模块截断）', () => {
    const md = resumeToMarkdown(baseResume([WORK, EDU]));
    expect(md).toContain('## 工作经历');
    expect(md).toContain('## 教育经历');
    expect(md).toContain('理学学士');
  });

  it('hidden 模块跳过导出（LLM/下载天然干净）', () => {
    const md = resumeToMarkdown(
      baseResume([{ ...EDU, hidden: true }, { ...WORK, hidden: true }]),
    );
    expect(md).not.toContain('教育经历');
    expect(md).not.toContain('工作经历内容');
    expect(md).not.toContain('主导 RAG');
  });

  it('全部隐藏时保底空骨架，markdown 仍可回读头部', () => {
    const md = resumeToMarkdown(baseResume([{ ...WORK, hidden: true }]));
    expect(md).toContain('## 工作经历');
    expect(md).not.toContain('主导 RAG 评测体系搭建');
    expect(md).toContain('# 张三');
  });
});

describe('normalizeStructuredSections（DB sections JSON 归一化）', () => {
  it('非数组 / 空数组 → null（调用方回退 markdown 解析）', () => {
    expect(normalizeStructuredSections(null)).toBeNull();
    expect(normalizeStructuredSections('{}')).toBeNull();
    expect(normalizeStructuredSections([])).toBeNull();
  });

  it('关键字段缺失（title 非字符串）→ null', () => {
    expect(normalizeStructuredSections([{ id: 'x', items: [] }])).toBeNull();
    expect(normalizeStructuredSections([{ title: '工作经历', items: [{ title: 1 }] }])).toBeNull();
  });

  it('归一化：隐藏标记仅认 true，缺 id 按位置兜底', () => {
    const out = normalizeStructuredSections([
      {
        title: '工作经历',
        hidden: 1,
        items: [{ title: '字节 · 产品经理', bullets: [{ text: '要点' }] }],
      },
      {
        id: 'sec-2',
        title: '教育经历',
        hidden: true,
        items: [{ id: 'i-2', title: '北大 · 计算机', bullets: [{ id: 'b-2', text: '学士' }] }],
      },
    ]);
    expect(out).not.toBeNull();
    expect(out?.[0].hidden).toBeUndefined();
    expect(out?.[0].id).toBeTruthy();
    expect(out?.[0].items[0].bullets[0].id).toBeTruthy();
    expect(out?.[1].hidden).toBe(true);
  });

  it('脏数据（title 缺失）→ null，不静默丢内容', () => {
    expect(
      normalizeStructuredSections([{ id: 'x', title: '工作经历', items: [{ bullets: [] }] }]),
    ).toBeNull();
  });

  it('合法结构：hidden===true 保留，id 透传', () => {
    const out = normalizeStructuredSections([
      { id: 'sec-edu', title: '教育经历', hidden: true, items: [] },
    ]);
    expect(out).toHaveLength(1);
    expect(out?.[0]).toMatchObject({ id: 'sec-edu', title: '教育经历', hidden: true });
  });
});

describe('triggerBlobDownload / downloadElementAsHtml（T-M6-5 真下载工具）', () => {
  /** jsdom 的 Blob 无 .text()，统一走 FileReader 读文本。 */
  function blobText(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blob);
    });
  }

  const createUrlSpy = vi.fn((_content: Blob | string) => 'blob:mock-url');
  const revokeUrlSpy = vi.fn();
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      value: createUrlSpy,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      value: revokeUrlSpy,
      writable: true,
      configurable: true,
    });
    createUrlSpy.mockClear();
    revokeUrlSpy.mockClear();
    clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);
  });

  afterEach(() => {
    clickSpy.mockRestore();
    Reflect.deleteProperty(URL, 'createObjectURL');
    Reflect.deleteProperty(URL, 'revokeObjectURL');
  });

  it('triggerBlobDownload：Blob 类型/内容 → ObjectURL → a.click → revoke', async () => {
    triggerBlobDownload('# 张三\n求职意向', '张三-求职简历.md', 'text/markdown;charset=utf-8');

    expect(createUrlSpy).toHaveBeenCalledTimes(1);
    const blob = createUrlSpy.mock.calls[0][0] as Blob;
    expect(blob.type).toContain('text/markdown');
    expect(await blobText(blob)).toContain('# 张三');
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeUrlSpy).toHaveBeenCalledWith('blob:mock-url');
  });

  it('downloadElementAsHtml：包装独立 HTML 文档并内联页面 style 文本', async () => {
    const style = document.createElement('style');
    style.textContent = '@page { size: A4; margin: 0; }';
    document.head.appendChild(style);

    const el = document.createElement('article');
    el.setAttribute('data-testid', 'resume-a4-page');
    el.innerHTML = '<h1>张三</h1>';
    document.body.appendChild(el);

    try {
      const ok = await downloadElementAsHtml(el, '张三-简历.html');
      expect(ok).toBe(true);
      const blob = createUrlSpy.mock.calls[0][0] as Blob;
      expect(blob.type).toContain('text/html');
      const text = await blobText(blob);
      expect(text).toContain('<!DOCTYPE html>');
      expect(text).toContain('@page { size: A4');
      expect(text).toContain('data-testid="resume-a4-page"');
      expect(text).toContain('张三');
    } finally {
      style.remove();
      el.remove();
    }
  });

  it('downloadElementAsHtml：元素不存在 → 返回 false 且不触发下载', async () => {
    const ok = await downloadElementAsHtml(null, '缺失.html');
    expect(ok).toBe(false);
    expect(createUrlSpy).not.toHaveBeenCalled();
  });
});
