import { describe, expect, it } from 'vitest'

import { getResumeDownloadUrl } from '../api/job'

describe('FE-API-01 简历下载 URL 与后端路由对齐', () => {
  it('拼出 /api/jobcraft/job/resume/download（job_analysis router prefix + /resume/download）', () => {
    expect(getResumeDownloadUrl('/data/output/a.docx')).toBe(
      '/api/jobcraft/job/resume/download?path=%2Fdata%2Foutput%2Fa.docx'
    )
  })

  it('path 做 URL 编码，中文与空格不破坏 query', () => {
    expect(getResumeDownloadUrl('D:\\我的 简历.docx')).toBe(
      `/api/jobcraft/job/resume/download?path=${encodeURIComponent('D:\\我的 简历.docx')}`
    )
  })
})
