import { describe, it, expect } from 'vitest';
import type { ExperienceCard, ExperienceCardVersion } from '../../api/types';
import {
  cardToExperience,
  cardTypeToCategory,
  EXPERIENCES_QUERY_KEY,
  versionsToHistory,
} from './mappers';

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
  is_confirmed: true,
};

describe('cardToExperience', () => {
  it('统一字段契约：直读响应四槽位，id 字符串化、tags 透传、card_type→category', () => {
    const card: ExperienceCard = {
      ...STRUCTURED_CARD,
      background: '背景直读',
      problem: '问题直读',
      actions: ['行动直读1', '行动直读2'],
      results: ['结果直读1'],
    };
    const exp = cardToExperience(card);
    expect(exp.id).toBe('7');
    expect(exp.title).toBe('端侧大模型量化评测与交互设计');
    expect(exp.company).toBe('未来智能实验室');
    expect(exp.role).toBe('AI 产品经理');
    expect(exp.period).toBe('2025.01 - 2025.08');
    expect(exp.background).toBe('背景直读');
    expect(exp.problem).toBe('问题直读');
    expect(exp.actions).toEqual(['行动直读1', '行动直读2']);
    expect(exp.results).toEqual(['结果直读1']);
    expect(exp.tags).toEqual(['端侧大模型', '量化评测']);
    expect(exp.category).toBe('work');
    expect(exp.currentVersion).toBe('V3');
    expect(exp.versionHistory).toEqual([]);
  });

  it('无四槽位直读时：从 ai_structured 聚合 A/R、problem 回退 summary / raw_text、background 回退 raw_text', () => {
    const card: ExperienceCard = { ...STRUCTURED_CARD, background: undefined, problem: undefined };
    const exp = cardToExperience(card);
    expect(exp.background).toBe(STRUCTURED_CARD.raw_text);
    expect(exp.problem).toBe('主导端侧部署方案并建立评测标准。');
    expect(exp.actions).toEqual(['定义 4-bit 量化剪枝策略']);
    expect(exp.results).toEqual(['首字延迟 TTFT 350ms', '内存占用 -42%']);
  });

  it('ai_structured 为空：problem 回退 summary → raw_text；空字段兜底', () => {
    const exp = cardToExperience({ ...STRUCTURED_CARD, ai_structured: null });
    expect(exp.problem).toBe('旧 summary');
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
    expect(bare.problem).toBe('移动端弱网场景下生成式体验的端侧化方案。');
    expect(bare.company).toBe('');
    expect(bare.role).toBe('');
    expect(bare.period).toBe('');
  });

  it('card_type 收敛：work/intern/project 直读，未知回退 project', () => {
    expect(cardTypeToCategory('work')).toBe('work');
    expect(cardTypeToCategory('intern')).toBe('intern');
    expect(cardTypeToCategory('project')).toBe('project');
    expect(cardTypeToCategory('education')).toBe('project');
    expect(cardTypeToCategory(null)).toBe('project');
  });

  it('EXP-P1-03：is_confirmed 草稿态透传，缺省视为已定稿', () => {
    expect(cardToExperience({ ...STRUCTURED_CARD }).isConfirmed).toBe(true);
    expect(cardToExperience({ ...STRUCTURED_CARD, is_confirmed: false }).isConfirmed).toBe(false);
  });
});

describe('EXPERIENCES_QUERY_KEY', () => {
  it('固定为 experiences', () => {
    expect([...EXPERIENCES_QUERY_KEY]).toEqual(['experiences']);
  });
});

describe('versionsToHistory（EXP-P1-06b 后端版本回流）', () => {
  const SNAPSHOTS: ExperienceCardVersion[] = [
    {
      id: 3, card_id: 7, version_type: 'user_edit', source_type: 'card_edit',
      source_id: 0, title: '端侧大模型量化评测', raw_text: 'V3 原文',
      tags: ['端侧大模型'], note: '编辑保存 V3', created_at: '2026-09-23T10:00:00',
    },
    {
      id: 2, card_id: 7, version_type: 'review_refined', source_type: 'interview_review',
      source_id: 9, title: '端侧大模型量化评测', raw_text: 'V2 原文',
      tags: ['端侧大模型'], note: '面试复盘反哺', created_at: '2026-09-21T08:00:00',
    },
    {
      id: 1, card_id: 7, version_type: 'original', source_type: 'original',
      source_id: 0, title: '端侧大模型量化评测', raw_text: 'V1 原文',
      tags: ['端侧大模型'], note: 'V1 哨兵基线（确认定稿）', created_at: '2026-09-18T09:00:00',
    },
  ];

  it('新→旧映射：V 编号从 currentVersion 递减，reason/date/source/rawText 来自后端快照，changes 置空', () => {
    const history = versionsToHistory(SNAPSHOTS, 3);

    expect(history).toHaveLength(3);
    expect(history.map((v) => v.version)).toEqual(['V3', 'V2', 'V1']);
    expect(history[0].reason).toBe('编辑保存 V3');
    expect(history[0].date).toBe('2026-09-23');
    expect(history[0].source).toBe('manual');
    expect(history[0].rawText).toBe('V3 原文');
    expect(history[0].title).toBe('端侧大模型量化评测');
    expect(history[0].changes).toEqual([]);
    expect(history[1].source).toBe('interview_review');
    expect(history[2].reason).toBe('V1 哨兵基线（确认定稿）');
    expect(history[2].source).toBe('manual');
  });

  it('version_type 识别：ai_polish→ai_optimization、jd_alignment→jd_alignment、original→manual', () => {
    const history = versionsToHistory(
      [
        { ...SNAPSHOTS[0], id: 5, version_type: 'ai_polish', note: null, created_at: '2026-09-22' },
        { ...SNAPSHOTS[0], id: 4, version_type: 'jd_alignment', note: null, created_at: '2026-09-22' },
        { ...SNAPSHOTS[0], id: 3, version_type: 'original', note: null, created_at: '2026-09-22' },
      ],
      3,
    );
    expect(history[0].source).toBe('ai_optimization');
    expect(history[0].reason).toBe('AI 深度润色');
    expect(history[1].source).toBe('jd_alignment');
    expect(history[1].reason).toBe('JD 深度对齐');
    expect(history[2].source).toBe('manual');
    expect(history[2].reason).toBe('V1 哨兵基线（定稿原始内容）');
  });

  it('EXP-P2-10：version_type=standardized → source standardized / reason 标准化表达', () => {
    const history = versionsToHistory(
      [
        { ...SNAPSHOTS[0], id: 6, version_type: 'standardized', note: null, created_at: '2026-09-24' },
      ],
      4,
    );
    expect(history[0].source).toBe('standardized');
    expect(history[0].reason).toBe('标准化表达确认（AI 中性化改写）');
  });

  it('snapshots 数超过 currentVersion 时 V 编号下限收敛在 V1', () => {
    const history = versionsToHistory(SNAPSHOTS, 1);
    expect(history.map((v) => v.version)).toEqual(['V1', 'V1', 'V1']);
  });
});