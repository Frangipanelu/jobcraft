import React, { useState } from 'react';
import { Check, ChevronDown, ChevronUp, FileText, Sparkles, Ban, Layers } from 'lucide-react';
import { useToastActions } from '../../context/JobCraftContext';
import type { Experience } from '../../types/jobcraft';
import type { Expression } from '../../api/types';
import {
  useExpressionsQuery,
  useGenerateExpressionMutation,
  useActivateExpressionMutation,
  useDeprecateExpressionMutation,
} from '../../features/experiences/expressionHooks';

interface ExpressionPanelProps {
  exp: Experience;
}

/** 前端 Experience.id → 后端 card id（兼容旧 'exp-123' 形式）。 */
function toCardId(id: string): number {
  return parseInt(id.replace('exp-', ''), 10);
}

const STATUS_META: Record<string, { label: string; cls: string }> = {
  candidate: { label: '候选', cls: 'bg-warning-bg text-warning border-warning-bg' },
  active: { label: '已激活', cls: 'bg-sage-soft text-sage border-sage-soft' },
  deprecated: { label: '已弃用', cls: 'bg-page text-muted border-edge' },
};

type DiffLine = { type: 'same' | 'add' | 'del'; text: string };

/** 简易 LCS 行级 diff（无第三方依赖）：原文 vs 表达 content。 */
function diffLines(a: string, b: string): DiffLine[] {
  const aLines = (a || '').split('\n');
  const bLines = (b || '').split('\n');
  const n = aLines.length;
  const m = bLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] =
        aLines[i] === bLines[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (aLines[i] === bLines[j]) {
      out.push({ type: 'same', text: aLines[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: aLines[i] });
      i++;
    } else {
      out.push({ type: 'add', text: bLines[j] });
      j++;
    }
  }
  while (i < n) {
    out.push({ type: 'del', text: aLines[i] });
    i++;
  }
  while (j < m) {
    out.push({ type: 'add', text: bLines[j] });
    j++;
  }
  return out;
}

/**
 * 标准化表达面板（EXP-P2-09，U4 确认闸门）。
 *
 * 展示某张经历卡的表达版本链（同链 version 降序），支持：
 * - AI 生成新表达（手动触发，落为 candidate）
 * - 每条表达「激活（U4 确认）/ 弃用」状态机操作
 * - 原文 vs 表达 content 行级 diff 对比，确认后再激活
 */
export const ExpressionPanel: React.FC<ExpressionPanelProps> = ({ exp }) => {
  const { showToast } = useToastActions();
  const cardId = toCardId(exp.id);
  const { data: expressions = [], isLoading } = useExpressionsQuery(cardId);
  const generate = useGenerateExpressionMutation(cardId);
  const activate = useActivateExpressionMutation(cardId);
  const deprecate = useDeprecateExpressionMutation(cardId);
  const [diffExpanded, setDiffExpanded] = useState<Record<number, boolean>>({});

  // 原文基线：与 handleAIRefine 同构（四槽位拼接），作为 diff 左侧
  const rawTextBaseline = [
    exp.background,
    exp.problem,
    ...(exp.actions || []),
    ...(exp.results || []),
  ]
    .filter(Boolean)
    .join('\n');

  const handleGenerate = async () => {
    try {
      await generate.mutateAsync(undefined);
      showToast({
        type: 'success',
        title: '标准化表达已生成',
        message: `新表达已进入「候选」状态，确认 diff 后可激活。`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '生成失败';
      showToast({ type: 'error', title: '生成失败', message: msg });
    }
  };

  const handleActivate = async (expressionId: number) => {
    try {
      const out = await activate.mutateAsync(expressionId);
      showToast({
        type: 'success',
        title: `已激活 V${out.version}`,
        message: '同版本链其余表达已自动降级为候选，保证唯一激活表达。',
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '激活失败';
      showToast({ type: 'error', title: '激活失败', message: msg });
    }
  };

  const handleDeprecate = async (expressionId: number) => {
    try {
      const out = await deprecate.mutateAsync(expressionId);
      showToast({ type: 'info', title: `已弃用 V${out.version}`, message: '该表达已停用，不再参与消费。' });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '弃用失败';
      showToast({ type: 'error', title: '弃用失败', message: msg });
    }
  };

  const toggleDiff = (id: number) => {
    setDiffExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const renderRow = (expr: Expression) => {
    const meta = STATUS_META[expr.status] || STATUS_META.candidate;
    const expanded = !!diffExpanded[expr.id];
    const canActivate = expr.status !== 'active';
    const canDeprecate = expr.status !== 'deprecated';
    const diff = expanded ? diffLines(rawTextBaseline, expr.content) : [];

    return (
      <div key={expr.id} className="p-3.5 rounded-lg border border-edge bg-canvas space-y-2">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-ink text-xs font-mono">V{expr.version}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${meta.cls}`}>
              {meta.label}
            </span>
            <span className="text-[11px] text-faint">
              {(expr.updated_at || expr.created_at || '').slice(0, 10) || '最近'}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => toggleDiff(expr.id)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border text-[11px] font-semibold cursor-pointer ${
                expanded ? 'bg-ink text-white border-ink' : 'bg-white text-ink border-edge hover:bg-page'
              }`}
            >
              <FileText className="w-3 h-3" />
              <span>对比原文</span>
              {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>

            {canActivate && (
              <button
                onClick={() => handleActivate(expr.id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sage-soft text-sage border border-sage-soft text-[11px] font-bold cursor-pointer hover:bg-edge-deep"
                title="确认使用该表达（U4 确认闸门）"
              >
                <Check className="w-3 h-3" />
                <span>激活</span>
              </button>
            )}

            {canDeprecate && (
              <button
                onClick={() => handleDeprecate(expr.id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white text-muted border border-edge text-[11px] font-semibold cursor-pointer hover:bg-page"
                title="停用该表达"
              >
                <Ban className="w-3 h-3" />
                <span>弃用</span>
              </button>
            )}
          </div>
        </div>

        <p className="text-ink text-xs leading-relaxed font-medium whitespace-pre-line line-clamp-3">
          {expr.content}
        </p>

        {expanded && (
          <div className="rounded-lg border border-edge bg-white overflow-hidden animate-in fade-in">
            <div className="px-3 py-1.5 bg-page border-b border-edge flex items-center gap-1.5 text-[11px] font-semibold text-muted">
              <Layers className="w-3 h-3" />
              <span>行级 diff（绿 + 新增 / 红 − 删除 / 灰 = 保留）</span>
            </div>
            <div className="max-h-56 overflow-auto text-[11px] leading-relaxed">
              {diff.map((line, idx) => (
                <div
                  key={idx}
                  className={`px-3 py-0.5 whitespace-pre-wrap ${
                    line.type === 'add'
                      ? 'bg-sage-soft/40 text-sage'
                      : line.type === 'del'
                        ? 'bg-error-bg/50 text-error line-through'
                        : 'text-faint'
                  }`}
                >
                  {line.type === 'add' ? '+ ' : line.type === 'del' ? '− ' : '  '}
                  {line.text || '（空行）'}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-5 bg-sage-soft/20 border-b border-sage-soft space-y-3 animate-in fade-in">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-sage" />
          <span className="text-xs font-bold text-sage">
            标准化表达（EXP-P2-09 · {expressions.length} 条版本链）
          </span>
        </div>
        <span className="text-[11px] text-faint">
          候选表达经 diff 对比确认后激活，激活表达即消费链首选
        </span>
      </div>

      {isLoading ? (
        <p className="text-xs text-muted">加载表达中...</p>
      ) : expressions.length === 0 ? (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-dashed border-sage-soft bg-white p-4">
          <div className="text-xs space-y-1">
            <div className="font-bold text-ink">暂无标准化表达</div>
            <div className="text-muted">
              基于当前经历原文通过大模型生成中性化表达，生成后为候选态，需 diff 确认后激活。
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generate.isPending}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-bold shadow-xs transition cursor-pointer disabled:opacity-50"
          >
            <Sparkles className="w-4 h-4" />
            <span>{generate.isPending ? '生成中...' : 'AI 生成标准化表达'}</span>
          </button>
        </div>
      ) : (
        <div className="space-y-3 pt-1">
          <div className="flex items-center justify-end">
            <button
              onClick={handleGenerate}
              disabled={generate.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-bold shadow-xs transition cursor-pointer disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{generate.isPending ? '生成中...' : '生成新表达'}</span>
            </button>
          </div>
          <div className="space-y-2">{expressions.map(renderRow)}</div>
        </div>
      )}
    </div>
  );
};