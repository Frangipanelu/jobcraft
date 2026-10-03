/**
 * 方向沉淀面板（T-M3-6 / 矩阵 Q1「方向知识沉淀 → /workbench」）。
 *
 * Workbench 底部区块：方向列表（DIR-n + 表达计数）+ 高频能力缺口
 * （capability_gap 按维度计数，D1-D8/EXT 词表复用 utils/dimensions）。
 * 接口失败静默隐藏——增值区块不阻断工作台主体。
 */
import React from 'react';
import { useDirectionSummaryQuery } from '../../features/direction/hooks';
import { dimensionLabel } from '../../utils/dimensions';

export const DirectionInsightPanel: React.FC = () => {
  const { data, isLoading, isError } = useDirectionSummaryQuery();

  if (isError) {
    return null;
  }

  if (isLoading) {
    return (
      <div
        data-testid="direction-insight"
        className="bg-white rounded-2xl border border-[#E2E8E4] p-5 shadow-xs"
      >
        <div className="text-xs text-muted">正在加载方向沉淀…</div>
      </div>
    );
  }

  const directions = data?.directions ?? [];
  const topGaps = data?.top_gaps ?? [];

  return (
    <section
      data-testid="direction-insight"
      className="bg-white rounded-2xl border border-[#E2E8E4] p-5 shadow-xs space-y-4"
    >
      <div>
        <div className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-wider">
          DIRECTIONS
        </div>
        <h2 className="text-[15px] font-bold text-[#111814] mt-0.5">方向沉淀</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* 方向列表 + 计数 */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold text-[#4B5563]">我的方向</div>
          {directions.length === 0 && (
            <div className="text-[11px] text-faint">
              尚无方向，完成一次 JD 分析后将自动沉淀。
            </div>
          )}
          {directions.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between gap-2 text-xs"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="shrink-0 inline-block text-[10px] font-bold px-1.5 py-0.5 rounded bg-sage-soft text-sage border border-sage/20">
                  {d.code || 'DIR-?'}
                </span>
                <span className="truncate font-medium text-[#111814]">{d.name}</span>
                {d.status === 'archived' && (
                  <span className="shrink-0 text-[10px] text-[#9CA3AF]">已归档</span>
                )}
              </div>
              <span
                data-testid={`direction-${d.id}-expressions`}
                className="shrink-0 text-[#6B7280]"
              >
                <strong className="font-bold text-[#111814]">
                  {d.expression_count}
                </strong>{' '}
                条表达
              </span>
            </div>
          ))}
        </div>

        {/* 高频能力缺口 */}
        <div className="space-y-2.5">
          <div className="text-xs font-semibold text-[#4B5563]">高频能力缺口</div>
          {topGaps.length === 0 && (
            <div className="text-[11px] text-faint">
              暂无缺口数据，完成一次 JD 分析后这里会显示待补齐的能力项。
            </div>
          )}
          {topGaps.map((g) => (
            <div
              key={g.dimension}
              className="flex items-center justify-between gap-2 text-xs"
            >
              <span className="truncate text-[#111814]">
                {dimensionLabel(g.dimension)}
              </span>
              <span
                data-testid={`gap-${g.dimension}`}
                className="shrink-0 inline-block text-[11px] font-semibold px-2 py-0.5 rounded-md bg-[#FFF4E5] text-[#B45309] border border-[#F5D9AE]"
              >
                缺口 {g.count}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
