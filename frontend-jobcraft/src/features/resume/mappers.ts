import type { ResumeVersionWire } from '../../api/types';

/**
 * 简历域查询键与纯映射。
 * 简历 map 形如 `Record<submissionId, ResumeVersion>`（submissionId 为字符串），
 * 键控 object（区别于其它域的数组，见 FE-RESUME-01 RES1）。
 */
export const RESUMES_QUERY_KEY = ['resumes'] as const;

/**
 * 简历版本全量 wire 列表查询键（T-M6-7：版本下拉列表读源）。
 * 与 RESUMES 分离——RESUMES 为按岗位归组折叠后的编辑 map，本键保留
 * `ResumeVersionWire[]` 原始全量（组件内自行归组）。
 */
export const RESUME_VERSIONS_QUERY_KEY = ['resume-versions'] as const;

/**
 * 简历版本归组键（三级回退：job_analysis_id → job_id → 版本 id）。
 * 与 `useResumesQuery` 的按岗归组**同源**——简历编辑 map 与版本下拉列表必须
 * 得到同一组键（锁步约束），故两处统一调用本函数，禁止各自内联表达式漂移。
 * @param v 版本 wire（只需归组相关三字段）
 * @returns 字符串组键（单版本组即版本 id 本身）
 */
export function resumeVersionGroupKey(
  v: Pick<ResumeVersionWire, 'job_analysis_id' | 'job_id' | 'id'>,
): string {
  return String(v.job_analysis_id ?? v.job_id ?? v.id);
}