import type { ExperienceCard } from '../../api/types';
import type { Experience, ExperienceCategory } from '../../types/jobcraft';

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