import { describe, expect, it } from 'vitest';
import { resumeVersionGroupKey } from './mappers';

describe('resumeVersionGroupKey 三级回退（useResumesQuery 与版本下拉同源组键）', () => {
  it('job_analysis_id → job_id → 版本 id 依次回退，输出字符串组键', () => {
    // ① 有 job_analysis_id：取 analysis（存量版本的主归组维度）
    expect(resumeVersionGroupKey({ id: 7, job_analysis_id: 12, job_id: 55 })).toBe('12');
    // ② analysis 缺失：回退 job_id
    expect(resumeVersionGroupKey({ id: 7, job_analysis_id: null, job_id: 55 })).toBe('55');
    // ③ 两者皆缺：回退版本 id（单行组）
    expect(resumeVersionGroupKey({ id: 7, job_analysis_id: null, job_id: null })).toBe('7');
  });
});
