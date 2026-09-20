import type { ExperienceCard } from '../../api/types';
import type { Experience } from '../../types/jobcraft';

/** Experiences 查询缓存 key（react-query 唯读源）。 */
export const EXPERIENCES_QUERY_KEY = ['experiences'] as const;

/**
 * 将后端 ExperienceCard 转换为前端 Experience。
 *
 * 自 JobCraftContext 移出，作为映射唯一实现（context 与 hooks 共享，杜绝双份漂移）。
 * 前端扩展字段（targetJobs / jdMatches / resumeVersionsUsed / versionHistory / metrics）
 * 后端不持久化，聚合时置为默认空值。
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
    background: card.raw_text,
    responsibility: structured?.summary || card.summary || card.raw_text,
    actions: achievements.map((a) => a.action?.main || '').filter(Boolean),
    results: achievements.map((a) => a.result || '').filter(Boolean),
    metrics: [],
    capabilityTags: card.tags,
    targetJobs: [],
    jdMatches: [],
    resumeVersionsUsed: [],
    currentVersion: `V${card.version}`,
    versionHistory: [],
  };
}