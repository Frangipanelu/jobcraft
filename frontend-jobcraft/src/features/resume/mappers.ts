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