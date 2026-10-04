import React, { useMemo, useState } from 'react';
import { Copy, Database, Loader2, Search } from 'lucide-react';
import type { QuestionBankQaPair } from '../../api/types';
import { useQuestionBankQuery } from '../../features/review/hooks';
import { useToastActions } from '../../context/JobCraftContext';

interface QuestionBankPanelProps {
  /** T-M8-3：按岗位过滤（undefined/null = 本人全量题库） */
  jobAnalysisId?: number | null;
}

interface CopyState {
  key: string;
  ok: boolean;
}

/**
 * T-M8-3 聚合题库（只读）：跨场次列出解析出的面试题目 + 当时的回答与建议。
 *
 * 消费约定：
 * - 数据源为服务端聚合端点（单 JOIN 免 N+1），不按 record 逐个拉详情；
 * - 「复制题目」把题干 + 参考答案要点拼成纯文本交给剪贴板，复制失败如实报错，
 *   不假报成功（FE-FAKE-01：不用假 toast 掩盖失败）；
 * - 只读浏览，不写 prep 数据（「加入备战练习」留后续任务，避免未经确认的静默沉淀）。
 */
export const QuestionBankPanel: React.FC<QuestionBankPanelProps> = ({
  jobAnalysisId,
}) => {
  const { data, isLoading, isError, error, refetch } = useQuestionBankQuery(jobAnalysisId);
  const { showToast } = useToastActions();
  const [searchQuery, setSearchQuery] = useState('');
  const [copyState, setCopyState] = useState<CopyState | null>(null);

  const qaPairs = useMemo(() => data?.qa_pairs || [], [data]);
  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return qaPairs;
    return qaPairs.filter(
      (p) =>
        p.question_text.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.record_company.toLowerCase().includes(q) ||
        p.record_position.toLowerCase().includes(q)
    );
  }, [qaPairs, searchQuery]);

  const handleCopy = async (pair: QuestionBankQaPair) => {
    const key = `${pair.record_id}-${pair.id}`;
    const lines = [
      pair.question_text || pair.content,
      pair.expected_answer ? `参考要点：${pair.expected_answer}` : '',
      `来源：${pair.record_company} ${pair.record_position} ${pair.record_round_type}`.trim(),
    ].filter(Boolean);
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopyState({ key, ok: true });
      showToast({ type: 'success', title: '题目已复制', message: '题干与参考要点已写入剪贴板。' });
    } catch (e) {
      setCopyState({ key, ok: false });
      showToast({
        type: 'error',
        title: '复制失败',
        message: (e as Error).message || '浏览器未授予剪贴板权限，请手动选择文本复制。',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-xs text-muted">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>正在加载题库...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="text-xs font-semibold text-terra">题库加载失败</div>
        <div className="text-[11px] text-muted max-w-md">
          {(error as Error)?.message || '服务端返回异常，请稍后重试。'}
        </div>
        <button
          onClick={() => refetch()}
          className="px-3 py-1.5 rounded-lg border border-edge text-xs font-semibold text-ink hover:border-sage transition cursor-pointer"
        >
          重新加载
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted">
          <Database className="w-4 h-4 text-sage" />
          <span>
            共 {qaPairs.length} 道题
            {searchQuery.trim() && `，匹配 ${filtered.length} 道`}
          </span>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-faint" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索题目 / 公司 / 岗位"
            className="w-full sm:w-64 pl-9 pr-3 py-2 bg-white border border-edge rounded-lg text-xs text-ink placeholder:text-faint focus:outline-none focus:border-sage transition"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center space-y-1">
          <div className="text-xs font-semibold text-ink">
            {qaPairs.length === 0 ? '题库暂无内容' : '没有匹配的题目'}
          </div>
          <div className="text-[11px] text-muted">
            {qaPairs.length === 0
              ? '完成一次面试复盘后，解析出的面试题目会自动沉淀到这里。'
              : '换个关键词试试，或清空搜索查看全部题目。'}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((pair) => {
            const key = `${pair.record_id}-${pair.id}`;
            return (
              <div
                key={key}
                className="bg-white rounded-xl border border-edge p-4 shadow-2xs space-y-2.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-xs font-semibold text-ink leading-relaxed">
                    {pair.question_text || pair.content || '（无题干文本）'}
                  </div>
                  <button
                    onClick={() => handleCopy(pair)}
                    aria-label={`复制题目：${(pair.question_text || pair.content || '').slice(0, 20)}`}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg border border-edge text-[11px] font-semibold text-muted hover:text-sage hover:border-sage transition shrink-0 cursor-pointer"
                  >
                    <Copy className="w-3 h-3" />
                    <span>{copyState?.key === key ? (copyState.ok ? '已复制' : '复制失败') : '复制'}</span>
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                  <span className="px-1.5 py-0.5 rounded bg-page border border-edge">
                    {pair.record_company || '未知公司'} · {pair.record_position || '未知岗位'}
                  </span>
                  {pair.record_round_type && (
                    <span className="px-1.5 py-0.5 rounded bg-page border border-edge">
                      {pair.record_round_type}
                    </span>
                  )}
                  {pair.dimension && (
                    <span className="px-1.5 py-0.5 rounded bg-sage-soft text-sage">{pair.dimension}</span>
                  )}
                  {pair.level && <span>层级 {pair.level}</span>}
                  {pair.intent && <span>考察：{pair.intent}</span>}
                </div>
                {pair.my_answer && (
                  <div className="text-[11px] text-muted leading-relaxed">
                    <span className="font-semibold text-ink">当时回答：</span>
                    {pair.my_answer}
                  </div>
                )}
                {pair.expected_answer && (
                  <div className="text-[11px] text-muted leading-relaxed">
                    <span className="font-semibold text-sage">参考要点：</span>
                    {pair.expected_answer}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};