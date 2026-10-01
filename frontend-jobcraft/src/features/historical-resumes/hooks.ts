import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as jobApi from '../../api/job';
import type { HistoricalResume } from '../../types/jobcraft';
import { HISTORICAL_RESUMES_QUERY_KEY, baseResumeToHistoricalResume } from './mappers';

/** 读取当前历史简历 cache，缺失时回退空数组。 */
function readHistoricalResumes(
  queryClient: ReturnType<typeof useQueryClient>,
): HistoricalResume[] {
  return queryClient.getQueryData<HistoricalResume[]>([...HISTORICAL_RESUMES_QUERY_KEY]) || [];
}

/** 写入历史简历 cache。 */
function writeHistoricalResumes(
  queryClient: ReturnType<typeof useQueryClient>,
  next: HistoricalResume[],
): void {
  queryClient.setQueryData([...HISTORICAL_RESUMES_QUERY_KEY], next);
}

/**
 * 查询底座简历历史版本列表。与 legacy `loadHistoricalResumes` 等价（listBaseResumes → 映射）。
 * @returns HistoricalResume[]（空数组兜底）
 */
export function useHistoricalResumesQuery() {
  return useQuery({
    queryKey: [...HISTORICAL_RESUMES_QUERY_KEY],
    queryFn: async () => {
      const records = await jobApi.listBaseResumes();
      return records.map(baseResumeToHistoricalResume);
    },
  });
}

/**
 * 新增历史简历（FE-UPLOAD-01 硬化）：
 * - `createBaseResume` 落库失败必须上抛，由视图层报错——不再静默容忍假成功；
 * - 成功后 id 与 `baseResumeToHistoricalResume` 回源映射一致（`hr-<serverId>`），
 *   选中态在列表 refetch 后不悬空；onSuccess 前置插入 cache；
 * - 不写 activities（零消费者）、不打 console（AGENTS 红线）、toast 归视图层。
 * @param mutationFn 入参 Omit<HistoricalResume, 'id' | 'uploadDate'>；resolve 最终入列的 HistoricalResume
 */
export function useAddHistoricalResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<HistoricalResume, unknown, Omit<HistoricalResume, 'id' | 'uploadDate'>>({
    mutationFn: async (resume) => {
      const record = await jobApi.createBaseResume({
        name: resume.name,
        file_size: resume.fileSize,
        format: resume.format,
        parsed_count: resume.parsedExperiencesCount,
        tags: resume.tags,
      });
      const mapped = baseResumeToHistoricalResume(record);
      return { ...resume, id: mapped.id, serverId: mapped.serverId, uploadDate: mapped.uploadDate };
    },
    onSuccess: (newResume) => {
      writeHistoricalResumes(queryClient, [newResume, ...readHistoricalResumes(queryClient)]);
    },
  });
}

/** 简历文件大小展示（<1MB 显示 KB，否则 MB，一位小数）。 */
function formatFileSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * 简历文件格式/体积校验（与后端 `/experience/upload/preview` 同契约：
 * PDF / DOCX / MD / TXT，≤10MB）。合法返回 null，非法返回错误文案。
 */
export function resumeFileError(file: File): string | null {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!['pdf', 'docx', 'md', 'txt'].includes(ext)) {
    return `不支持「${ext ? '.' + ext : '无后缀'}」格式，请使用 PDF / DOCX / MD / TXT。`;
  }
  if (file.size > 10 * 1024 * 1024) {
    return `文件过大（${(file.size / 1024 / 1024).toFixed(1)}MB > 10MB）。`;
  }
  return null;
}

/**
 * 简历完整上传链（FE-UPLOAD-01）：
 * `previewResume`（真实解析）→ `confirmUpload`（真实入库）→ `createBaseResume`（元数据），
 * 任一步失败均向上抛，由视图层报错——断网/非法文件下不得出现成功提示。
 * @returns 入列的 HistoricalResume（id 与列表回源后的 `hr-<serverId>` 一致，选中态不悬空）
 */
export function useUploadResumeMutation() {
  const addMutation = useAddHistoricalResumeMutation();

  return useMutation<HistoricalResume, unknown, File>({
    mutationFn: async (file) => {
      const preview = await jobApi.previewResume(file);
      const confirmed = await jobApi.confirmUpload(preview.items, preview.raw_text || undefined);
      const count = confirmed.cards?.length || 0;
      return addMutation.mutateAsync({
        name: file.name,
        fileSize: formatFileSize(file.size),
        isDefault: false,
        parsedExperiencesCount: count,
        format: file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'docx',
        tags: count > 0 ? ['已解析', 'AI 结构化'] : ['已上传'],
      });
    },
  });
}

/**
 * 简历解析预览（两阶段上传第一阶段，FE-LAYER-01）：
 * 组件层不再直调 `jobApi.previewResume`——解析结果由视图以预览态呈现，失败上抛由视图报错。
 */
export function usePreviewResumeMutation() {
  return useMutation<Awaited<ReturnType<typeof jobApi.previewResume>>, unknown, File>({
    mutationFn: (file) => jobApi.previewResume(file),
  });
}

/**
 * 简历确认入库（两阶段上传第二阶段，FE-LAYER-01）：
 * 组件层不再直调 `jobApi.confirmUpload`——预览用户确认后提交所选条目。
 */
export function useConfirmUploadMutation() {
  return useMutation<
    Awaited<ReturnType<typeof jobApi.confirmUpload>>,
    unknown,
    { items: jobApi.PreviewItem[]; rawText?: string }
  >({
    mutationFn: ({ items, rawText }) => jobApi.confirmUpload(items, rawText || undefined),
  });
}

/**
 * 删除历史简历。与 legacy `deleteHistoricalResume` 等价但语义更稳：
 * `await deleteBaseResume(serverId)` 成功后才从 cache 过滤（对齐 experiences delete；
 * legacy 无条件本地删除 + 失败 console）。无 serverId（本地未落库记录）直接移除。
 * @param mutationFn 入参 HistoricalResume.id
 */
export function useDeleteHistoricalResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, string>({
    mutationFn: async (id) => {
      const list = readHistoricalResumes(queryClient);
      const target = list.find((r) => r.id === id);
      if (target?.serverId) {
        await jobApi.deleteBaseResume(target.serverId);
      }
    },
    onSuccess: (_data, id) => {
      writeHistoricalResumes(
        queryClient,
        readHistoricalResumes(queryClient).filter((r) => r.id !== id),
      );
    },
  });
}

/**
 * 设定默认底座简历。与 legacy `setDefaultHistoricalResume` 等价；
 * `await setDefaultBaseResume(serverId)` 成功后 cache 置唯一 isDefault（失败不动 cache）。
 * @param mutationFn 入参 HistoricalResume.id
 */
export function useSetDefaultHistoricalResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<unknown, unknown, string>({
    mutationFn: async (id) => {
      const list = readHistoricalResumes(queryClient);
      const target = list.find((r) => r.id === id);
      if (target?.serverId) {
        await jobApi.setDefaultBaseResume(target.serverId);
      }
    },
    onSuccess: (_data, id) => {
      writeHistoricalResumes(
        queryClient,
        readHistoricalResumes(queryClient).map((r) => ({ ...r, isDefault: r.id === id })),
      );
    },
  });
}