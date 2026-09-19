import type { BaseResumeRecord } from '../../api/job';
import type { HistoricalResume } from '../../types/jobcraft';

export const HISTORICAL_RESUMES_QUERY_KEY = ['historical-resumes'] as const;

/**
 * 后端 BaseResumeRecord → 前端 HistoricalResume 映射。
 * 自 context loadHistoricalResumes 内联映射提取，作为单一事实来源。
 */
export function baseResumeToHistoricalResume(r: BaseResumeRecord): HistoricalResume {
  const format = (r.format === 'pdf' ? 'pdf' : 'docx') as HistoricalResume['format'];
  const formatTags =
    r.tags && r.tags.length > 0 ? r.tags : r.parsed_count > 0 ? ['已解析', 'AI 结构化'] : ['已上传'];
  return {
    id: 'hr-' + r.id,
    serverId: r.id,
    name: r.name || '上传简历',
    uploadDate: (r.created_at || '').replace('T', ' ').substring(0, 16),
    fileSize: r.file_size || '',
    isDefault: !!r.is_default,
    parsedExperiencesCount: r.parsed_count || 0,
    format,
    tags: formatTags,
  };
}