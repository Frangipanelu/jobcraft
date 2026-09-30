import type { ResumeSuggestionWire } from '../api/types';
import type { AISuggestion, ResumeBullet, ResumeVersion } from '../types/jobcraft';

/**
 * FE-RESUME-02：简历 AI 优化建议 ↔ 前端 ResumeVersion 水合/序列化工具。
 *
 * 索引契约（生成与水合共用，保证双向一致）：
 * - item_index = resume.sections 依次展平后的 item（卡片）全局序号
 * - bullet_index = 该 item 内 bullets 的序号
 * - original_text = 生成时该 bullet 的完整文本（trim 后比对）
 *
 * 定位策略：(item_index, bullet_index) 主定位且文本一致 → 命中；
 * 否则全文检索 original_text 兜底；两者都不中 → stale（pending 建议禁用「应用」）。
 */

interface FlatBullet {
  itemIndex: number;
  bulletIndex: number;
  bullet: ResumeBullet;
}

/** 按索引契约展平全部 bullet。 */
export function flattenResumeBullets(resume: ResumeVersion): FlatBullet[] {
  const flat: FlatBullet[] = [];
  let itemIndex = 0;
  for (const section of resume.sections || []) {
    for (const item of section.items || []) {
      (item.bullets || []).forEach((bullet, bulletIndex) => {
        flat.push({ itemIndex, bulletIndex, bullet });
      });
      itemIndex += 1;
    }
  }
  return flat;
}

/**
 * 构建生成入参 bullets（与 flattenResumeBullets 同一索引契约）。
 * @returns [{item_index, bullet_index, text}]；空简历返回 []
 */
export function buildSuggestionBullets(
  resume: ResumeVersion,
): { item_index: number; bullet_index: number; text: string }[] {
  return flattenResumeBullets(resume)
    .filter((entry) => entry.bullet.text && entry.bullet.text.trim())
    .map((entry) => ({
      item_index: entry.itemIndex,
      bullet_index: entry.bulletIndex,
      text: entry.bullet.text,
    }));
}

/** 定位建议对应的 bullet id；双不中返回 null（调用方标记 stale）。 */
function locateTargetBulletId(resume: ResumeVersion, wire: ResumeSuggestionWire): string | null {
  const expected = (wire.original_text || '').trim();
  if (!expected) return null;

  const flat = flattenResumeBullets(resume);
  const byIndex = flat.find(
    (entry) => entry.itemIndex === wire.item_index && entry.bulletIndex === wire.bullet_index,
  );
  if (byIndex && byIndex.bullet.text.trim() === expected) return byIndex.bullet.id;

  const byText = flat.find((entry) => entry.bullet.text.trim() === expected);
  return byText ? byText.bullet.id : null;
}

/**
 * wire 记录 → 前端 AISuggestion（水合）。
 * pending 且定位失败 → stale=true（保留展示，禁止应用）；applied/rejected 照常展示。
 */
export function hydrateResumeSuggestions(
  resume: ResumeVersion,
  wires: ResumeSuggestionWire[] | null | undefined,
): AISuggestion[] {
  if (!wires || !wires.length) return [];
  return wires.map((wire) => {
    const applied = wire.status === 'applied';
    const rejected = wire.status === 'rejected';
    const targetBulletId = locateTargetBulletId(resume, wire);
    const pending = !applied && !rejected;
    return {
      id: wire.id,
      type: wire.type,
      title: wire.title,
      originalText: wire.original_text,
      suggestedText: wire.suggested_text,
      applied,
      rejected,
      reason: wire.reason,
      targetBulletId: targetBulletId ?? undefined,
      itemIndex: wire.item_index,
      bulletIndex: wire.bullet_index,
      stale: pending && !targetBulletId ? true : undefined,
    };
  });
}

/** 定位 targetBulletId 在展平序中的 (item_index, bullet_index)；找不到返回 null。 */
function indexOfBulletId(
  resume: ResumeVersion,
  bulletId: string | undefined,
): { itemIndex: number; bulletIndex: number } | null {
  if (!bulletId) return null;
  const hit = flattenResumeBullets(resume).find((entry) => entry.bullet.id === bulletId);
  return hit ? { itemIndex: hit.itemIndex, bulletIndex: hit.bulletIndex } : null;
}

/**
 * 前端 AISuggestion → wire 记录（PATCH resume_suggestions 落库用）。
 * 缺失索引时按 targetBulletId 反查；仍无法定位回退 0/0（下次水合按文本兜底或判 stale）。
 */
export function suggestionsToWire(
  suggestions: AISuggestion[],
  resume: ResumeVersion,
): ResumeSuggestionWire[] {
  return suggestions.map((sug) => {
    const located = indexOfBulletId(resume, sug.targetBulletId);
    return {
      id: sug.id,
      type: sug.type,
      title: sug.title,
      original_text: sug.originalText,
      suggested_text: sug.suggestedText,
      reason: sug.reason,
      item_index: sug.itemIndex ?? located?.itemIndex ?? 0,
      bullet_index: sug.bulletIndex ?? located?.bulletIndex ?? 0,
      status: sug.applied
        ? ('applied' as const)
        : sug.rejected
          ? ('rejected' as const)
          : ('pending' as const),
    };
  });
}
