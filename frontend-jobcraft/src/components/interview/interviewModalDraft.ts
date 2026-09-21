import type { InterviewDraft } from '../../types/jobcraft';

export const INTERVIEW_DRAFT_KEY = 'interviewDraft';

/**
 * 读取并消费 localStorage 中的面试草稿（一次性，读后删除，
 * 与 legacy NewInterviewModal 行为一致：仅在同一次打开会话内恢复）。
 * @returns 草稿数据；无草稿或解析失败时返回 null
 */
export function loadInterviewModalDraft(): Partial<InterviewDraft> | null {
  try {
    const saved = localStorage.getItem(INTERVIEW_DRAFT_KEY);
    if (saved) {
      localStorage.removeItem(INTERVIEW_DRAFT_KEY);
      return JSON.parse(saved);
    }
  } catch {
    // 损坏或无法解析的草稿直接丢弃，不阻断打开弹窗
  }
  return null;
}

/**
 * 持久化当前表单数据到 localStorage（用于跳转 JD 分析页后回填草稿）。
 * @param data 待持久化的表单片段
 */
export function saveInterviewModalDraft(data: Partial<InterviewDraft>): void {
  localStorage.setItem(INTERVIEW_DRAFT_KEY, JSON.stringify(data));
}

/** 清除面试草稿（弹窗关闭 / 创建成功时调用）。 */
export function clearInterviewModalDraft(): void {
  localStorage.removeItem(INTERVIEW_DRAFT_KEY);
}