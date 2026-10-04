import { describe, it, expect } from 'vitest';
import { resumeToMarkdown, normalizeStructuredSections } from '../utils/resumeParser';
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
