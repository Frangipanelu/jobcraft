import type {
  ExperienceCard,
  ExperienceCardVersion,
} from '../../api/types';
import type {
  Experience,
  ExperienceCategory,
  ExperienceVersionRecord,
} from '../../types/jobcraft';

/** Experiences 查询缓存 key（react-query 唯读源）。 */
export const EXPERIENCES_QUERY_KEY = ['experiences'] as const;

/**
 * 兼容后端 card_type 的前端分类映射（EXPERIENCE_SPEC §30.4.1）。
 * 后端只持久化 work / intern / project；旧数据或未知值回退 project（等价旧「核心经历」归项目）。
 */
export function cardTypeToCategory(cardType?: string | null): ExperienceCategory {
  if (cardType === 'work' || cardType === 'intern' || cardType === 'project') {
    return cardType;
  }
  return 'project';
}

/**
 * 将后端 ExperienceCard 转换为前端 Experience。
 *
 * 自 JobCraftContext 移出，作为映射唯一实现（context 与 hooks 共享，杜绝双份漂移）。
 * 统一字段契约（EXPERIENCE_SPEC §30.4）：
 *   S = background      → 直读响应四槽位，旧数据兜底 raw_text
 *   T = problem         → 直读响应四槽位，旧数据兜底 ai_structured.summary / summary
 *   A = actions[]       → 直读响应四槽位，旧数据兜底 achievements[].action.main
 *   R = results[]       → 直读响应四槽位，旧数据兜底 achievements[].result
 *   card_type           → category 直读
 */
export function cardToExperience(card: ExperienceCard): Experience {
  const structured = card.ai_structured;
  const achievements = structured?.achievements || [];

  return {
    id: String(card.id),
    title: card.title,
    company: card.company || '',
    role: card.role || '',
    period: card.period || '',
    background: card.background || card.raw_text,
    problem: card.problem || structured?.summary || card.summary || card.raw_text,
    actions:
      (card.actions && card.actions.length > 0
        ? card.actions
        : achievements.map((a) => a.action?.main || '').filter(Boolean)),
    results:
      (card.results && card.results.length > 0
        ? card.results
        : achievements.map((a) => a.result || '').filter(Boolean)),
    tags: card.tags,
    category: cardTypeToCategory(card.card_type),
    currentVersion: `V${card.version}`,
    versionHistory: [],
    // EXP-P1-03：草稿状态透传，false 时列表展示「待定稿」标记
    isConfirmed: card.is_confirmed ?? true,
  };
}

/**
 * 后端版本快照 → 前端版本历史（EXP-P1-05 §28 / §34.6）。
 *
 * 后端只存 title/raw_text/tags（表结构固定），无逐字段 diff；
 * 前端据此展示 V 编号、日期、原因与来源，并以 rawText 支持原文回滚。
 * 标签规则：最新快照 = 当前版本 V{current_version}，依序递减到 V1（哨兵基线）。
 */
export function versionsToHistory(
  versions: ExperienceCardVersion[],
  currentVersion: number
): ExperienceVersionRecord[] {
  return versions.map((v, idx) => ({
    version: `V${Math.max(1, currentVersion - idx)}`,
    date: (v.created_at || '').slice(0, 10),
    reason: v.note || versionTypeReason(v.version_type),
    source: versionTypeSource(v.version_type),
    changes: [],
    title: v.title || undefined,
    rawText: v.raw_text,
  }));
}

function versionTypeReason(version_type: string): string {
  switch (version_type) {
    case 'original':
      return 'V1 哨兵基线（定稿原始内容）';
    case 'user_edit':
    case 'card_edit':
      return '编辑保存';
    case 'ai_polish':
      return 'AI 深度润色';
    case 'review_refined':
      return '面试复盘反哺';
    case 'jd_alignment':
      return 'JD 深度对齐';
    case 'standardized':
      return '标准化表达确认（AI 中性化改写）';
    default:
      return '版本快照';
  }
}

function versionTypeSource(
  version_type: string
): ExperienceVersionRecord['source'] {
  switch (version_type) {
    case 'review_refined':
      return 'interview_review';
    case 'jd_alignment':
      return 'jd_alignment';
    case 'ai_polish':
      return 'ai_optimization';
    case 'standardized':
      return 'standardized';
    case 'original':
    case 'user_edit':
    case 'card_edit':
    default:
      return 'manual';
  }
}