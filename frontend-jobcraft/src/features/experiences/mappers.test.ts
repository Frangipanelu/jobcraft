import { describe, it, expect } from 'vitest';
import type { ExperienceCard } from '../../api/types';
import { cardToExperience, EXPERIENCES_QUERY_KEY } from './mappers';

const STRUCTURED_CARD: ExperienceCard = {
  id: 7,
  user_id: 1,
  title: '端侧大模型量化评测与交互设计',
  raw_text: '移动端弱网场景下生成式体验的端侧化方案。',
  tags: ['端侧大模型', '量化评测'],
  ai_structured: {
    summary: '主导端侧部署方案并建立评测标准。',
    achievements: [
      {
        title: '量化部署',
        action: { main: '定义 4-bit 量化剪枝策略', difficulty: null, resolution: null },
        result: '首字延迟 TTFT 350ms',
      },
      {
        title: '空动作',
        action: { main: '', difficulty: null, resolution: null },
        result: '内存占用 -42%',
      },
    ],
  },
  summary: '旧 summary',
  content: '',
  company: '未来智能实验室',
  role: 'AI 产品经理',
  period: '2025.01 - 2025.08',
  source: 'manual',
  card_type: 'work',
  version: 3,
  is_active: true,
};

describe('cardToExperience', () => {
  it('ai_structured 归一：achievements→actions/results、tags→capabilityTags、id 字符串化', () => {
    const exp = cardToExperience(STRUCTURED_CARD);
    expect(exp.id).toBe('7');
    expect(exp.title).toBe('端侧大模型量化评测与交互设计');
    expect(exp.company).toBe('未来智能实验室');
    expect(exp.role).toBe('AI 产品经理');
    expect(exp.period).toBe('2025.01 - 2025.08');
    expect(exp.background).toBe(STRUCTURED_CARD.raw_text);
    expect(exp.responsibility).toBe('主导端侧部署方案并建立评测标准。');
    expect(exp.actions).toEqual(['定义 4-bit 量化剪枝策略']);
    expect(exp.results).toEqual(['首字延迟 TTFT 350ms', '内存占用 -42%']);
    expect(exp.capabilityTags).toEqual(['端侧大模型', '量化评测']);
    expect(exp.currentVersion).toBe('V3');
    expect(exp.metrics).toEqual([]);
    expect(exp.targetJobs).toEqual([]);
    expect(exp.jdMatches).toEqual([]);
    expect(exp.resumeVersionsUsed).toEqual([]);
    expect(exp.versionHistory).toEqual([]);
  });

  it('ai_structured 为空：responsibility 回退 summary → raw_text；空字段兜底', () => {
    const exp = cardToExperience({ ...STRUCTURED_CARD, ai_structured: null });
    expect(exp.responsibility).toBe('旧 summary');
    expect(exp.actions).toEqual([]);
    expect(exp.results).toEqual([]);

    const bare = cardToExperience({
      ...STRUCTURED_CARD,
      ai_structured: null,
      summary: undefined,
      company: null,
      role: null,
      period: null,
    });
    expect(bare.responsibility).toBe('移动端弱网场景下生成式体验的端侧化方案。');
    expect(bare.company).toBe('');
    expect(bare.role).toBe('');
    expect(bare.period).toBe('');
  });
});

describe('EXPERIENCES_QUERY_KEY', () => {
  it('固定为 experiences', () => {
    expect([...EXPERIENCES_QUERY_KEY]).toEqual(['experiences']);
  });
});