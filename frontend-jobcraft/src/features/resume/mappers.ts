/**
 * 简历域查询键与纯映射。
 * 简历 map 形如 `Record<submissionId, ResumeVersion>`（submissionId 为字符串），
 * 键控 object（区别于其它域的数组，见 FE-RESUME-01 RES1）。
 */
export const RESUMES_QUERY_KEY = ['resumes'] as const;