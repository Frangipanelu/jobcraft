import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as authApi from '../../api/auth';
import * as jobApi from '../../api/job';
import type { JDAnalysis } from '../../types/jobcraft';
import { JD_ANALYSES_QUERY_KEY, analysisDetailToJD } from './mappers';

interface JDMutationOptions {
  /** context 镜像写入（过渡期）：cache 更新后同步回 context.jdAnalyses，供未迁移视图读取。 */
  onSync?: (analyses: JDAnalysis[]) => void;
}

/**
 * 查询当前用户的 JD 分析历史（listJobAnalyses → 逐条 getJobAnalysis → analysisDetailToJD）。
 *
 * 与 legacy `JobCraftContext.loadJdAnalyses` 语义一致：先取摘要列表，再并发拉取每条完整详情；
 * 单条详情失败时跳过该条（不外抛），userId 取自已认证用户的 auth profile。
 */
export function useJdAnalysesQuery() {
  return useQuery({
    queryKey: [...JD_ANALYSES_QUERY_KEY],
    queryFn: async () => {
      const user = await authApi.getCurrentUser();
      const data = await jobApi.listJobAnalyses(user.id);
      const summaries = data.analyses || [];
      const fullAnalyses = await Promise.all(
        summaries.map(async (s) => {
          try {
            const summary = s as { id?: number; job_analysis_id?: number };
            const detail = await jobApi.getJobAnalysis(Number(summary.id || summary.job_analysis_id));
            return analysisDetailToJD(detail);
          } catch {
            return null;
          }
        }),
      );
      return fullAnalyses.filter(Boolean) as JDAnalysis[];
    },
  });
}

/**
 * 删除 JD 分析。与 legacy `JobCraftContext.deleteJDAnalysis` 行为等价：
 * 仅从前端状态移除；id 形如 `sub-{number}` 时尝试删除后端 submission（失败忽略）；
 * 后端无 JD 分析删除端点，故真实分析 id（数字串）不产生网络删除请求。
 */
export function useDeleteJdAnalysisMutation(options: JDMutationOptions = {}) {
  const queryClient = useQueryClient();
  const { onSync } = options;

  return useMutation<string, unknown, string>({
    mutationFn: async (id) => {
      const match = id.match(/^sub-(\d+)$/);
      if (match) {
        try {
          await jobApi.deleteSubmission(Number(match[1]));
        } catch {
          /* ignore */
        }
      }
      return id;
    },
    onSuccess: (id) => {
      const prev = queryClient.getQueryData<JDAnalysis[]>([...JD_ANALYSES_QUERY_KEY]) || [];
      const next = prev.filter((a) => a.id !== id);
      queryClient.setQueryData([...JD_ANALYSES_QUERY_KEY], next);
      onSync?.(next);
    },
  });
}
