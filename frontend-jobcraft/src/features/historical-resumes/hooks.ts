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
 * 新增历史简历。与 legacy `addHistoricalResume` 等价：
 * - `createBaseResume` 落库成功 → 回填 `serverId`，onSuccess 前置插入 cache；
 * - 落库失败仅保留内存记录（继承 legacy fire-and-forget 容忍），持久化失败不影响本地列表；
 * - 不写 activities（零消费者）、不打 console（AGENTS 红线）、toast 归视图层。
 * @param mutationFn 入参 Omit<HistoricalResume, 'id' | 'uploadDate'>；resolve 最终入列的 HistoricalResume
 */
export function useAddHistoricalResumeMutation() {
  const queryClient = useQueryClient();

  return useMutation<HistoricalResume, unknown, Omit<HistoricalResume, 'id' | 'uploadDate'>>({
    mutationFn: async (resume) => {
      const id = 'hr-' + Date.now();
      const uploadDate = new Date().toISOString().replace('T', ' ').substring(0, 16);
      const local: HistoricalResume = { ...resume, id, uploadDate };
      try {
        const record = await jobApi.createBaseResume({
          name: resume.name,
          file_size: resume.fileSize,
          format: resume.format,
          parsed_count: resume.parsedExperiencesCount,
          tags: resume.tags,
        });
        return { ...local, serverId: record.id };
      } catch {
        return local;
      }
    },
    onSuccess: (newResume) => {
      writeHistoricalResumes(queryClient, [newResume, ...readHistoricalResumes(queryClient)]);
    },
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