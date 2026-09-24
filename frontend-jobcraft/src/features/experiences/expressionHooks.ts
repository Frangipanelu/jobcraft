/**
 * Expression 数据层 hooks（EXP-P2-08）
 *
 * 标准化表达（标准经历表达）按经历卡维度组织：
 * - useExpressionsQuery(cardId)：拉取某张卡的表达（候选/激活/弃用，同链 version 降序）
 * - useGenerateExpressionMutation(cardId)：AI 生成并入库（手动触发，返回 candidate）
 * - useActivateExpressionMutation / useDeprecateExpressionMutation：状态机切换
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as experienceApi from '../../api/experience';
import type { Expression } from '../../api/types';

/** 某张经历卡的表达列表缓存 key。 */
export const expressionQueryKey = (cardId: number) => ['expressions', cardId] as const;

/** 拉取某张经历卡的标准化表达（§8.1，同链按 version 降序）。 */
export function useExpressionsQuery(cardId: number) {
  return useQuery<Expression[]>({
    queryKey: expressionQueryKey(cardId),
    queryFn: async () => {
      const res = await experienceApi.listExpressions(cardId);
      return res.items || [];
    },
  });
}

/**
 * AI 生成标准化表达并入库（EXP-P2-04 §8.2，手动触发 = 1 次 LLM）。
 * 成功返回新表达行（status=candidate），并使该卡表达列表失活刷新。
 */
export function useGenerateExpressionMutation(cardId: number) {
  const queryClient = useQueryClient();

  return useMutation<Expression, unknown, void>({
    mutationFn: async () => experienceApi.generateExpression(cardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expressionQueryKey(cardId) });
    },
  });
}

/** 激活指定表达（EXP-P2-06：同链其它 active 自动降级 candidate，保证唯一 active）。 */
export function useActivateExpressionMutation(cardId: number) {
  const queryClient = useQueryClient();

  return useMutation<Expression, unknown, number>({
    mutationFn: async (expressionId) => experienceApi.activateExpression(expressionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expressionQueryKey(cardId) });
    },
  });
}

/** 弃用指定表达（EXP-P2-06：active/candidate → deprecated，不可复用）。 */
export function useDeprecateExpressionMutation(cardId: number) {
  const queryClient = useQueryClient();

  return useMutation<Expression, unknown, number>({
    mutationFn: async (expressionId) => experienceApi.deprecateExpression(expressionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: expressionQueryKey(cardId) });
    },
  });
}