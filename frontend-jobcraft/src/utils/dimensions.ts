/**
 * D1-D8 能力维度中文词表（Q3-a：与 JD 要求侧同一把尺子）。
 *
 * 与后端 `app/agents/jd_ats_agent.py` 的 DIMENSION_DESCRIPTIONS 前缀同源；
 * EXT = 门槛/格式类非能力缺口扩展码（Q3-a 定稿）。
 * 消费方：JD 报告页任务清单、面试准备维度标题（原地内联词表已收敛至此）。
 */
export const DIMENSION_LABELS: Record<string, string> = {
  D1: '技术深度',
  D2: '业务理解',
  D3: '问题拆解',
  D4: '方案设计',
  D5: '落地执行',
  D6: '数据复盘',
  D7: '协作沟通',
  D8: '职业规划',
};

/** 维度编码 → 展示名（如 D6 → "D6 数据复盘"；EXT/未知原样返回）。 */
export function dimensionLabel(code: string): string {
  const key = (code || '').trim().toUpperCase();
  if (!key) return '—';
  const name = DIMENSION_LABELS[key];
  return name ? `${key} ${name}` : key;
}
