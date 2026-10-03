import { useQuery } from '@tanstack/react-query';
import * as directionApi from '../../api/direction';

export const DIRECTION_SUMMARY_QUERY_KEY = ['direction', 'summary'] as const;

/**
 * 方向沉淀汇总（T-M3-6：/workbench 面板——方向列表+计数+高频缺口）。
 *
 * 端点按登录用户服务端过滤，queryFn 无需先取 user id；
 * 缺口段（capability_gap 缺表）由后端降级为空列表，查询本身不失败。
 */
export function useDirectionSummaryQuery() {
  return useQuery({
    queryKey: [...DIRECTION_SUMMARY_QUERY_KEY],
    queryFn: () => directionApi.getDirectionSummary(),
  });
}
