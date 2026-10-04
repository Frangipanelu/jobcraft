import React, { useState } from 'react';
import { Sparkles, Tags } from 'lucide-react';
import * as directionApi from '../../api/direction';
import type { ClassificationSource, ClassificationValue } from '../../features/jd/classification';

/**
 * 结构化表单 · 方向分类区块（T-M4-3，Q4 裁决：手动 + 词典规则，零 LLM）。
 *
 * 交互约定：
 * - 六维 + 方向名全部选填，区块留空 = 本次分析不写分类（提交链整体跳过）；
 * - 「词典建议」按岗位名/职责/要求文本匹配词典，命中回填四维 + 方向名（source=rule）；
 * - 任何手动编辑把 source 翻回 manual（用户确认 → 后端记 confirmed/high）；
 * - 方向名 datalist 首次聚焦时懒加载已有方向（加载失败仅失去补全，不阻断表单）。
 */

const DIM_FIELDS: {
  key: keyof Omit<ClassificationValue, 'directionName'>;
  label: string;
  placeholder: string;
}[] = [
  { key: 'jobFunction', label: '职能', placeholder: '例如：产品、研发、运营' },
  { key: 'primaryRole', label: '主角色', placeholder: '例如：AI 产品经理' },
  { key: 'industry', label: '行业', placeholder: '例如：电商与零售' },
  { key: 'product', label: '产品', placeholder: '例如：交易平台与商家工具' },
  { key: 'scenario', label: '场景', placeholder: '例如：交易履约、商家增长' },
  { key: 'skills', label: '技能', placeholder: '例如：数据分析、跨团队推进' },
];

const INPUT_CLASS =
  'w-full px-3 py-2 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-white outline-none placeholder:text-faint';

export interface JDClassificationSectionProps {
  value: ClassificationValue;
  source: ClassificationSource;
  suggesting: boolean;
  suggestDisabled: boolean;
  onChange: (patch: Partial<ClassificationValue>) => void;
  onSuggest: () => void;
}

export const JDClassificationSection: React.FC<JDClassificationSectionProps> = ({
  value,
  source,
  suggesting,
  suggestDisabled,
  onChange,
  onSuggest,
}) => {
  const [directionNames, setDirectionNames] = useState<string[]>([]);
  const [namesLoaded, setNamesLoaded] = useState(false);

  const handleDirectionFocus = async () => {
    if (namesLoaded) return;
    try {
      const list = await directionApi.listDirections('active');
      setDirectionNames(list.map((d) => d.name));
    } catch {
      // datalist 仅是补全辅助：加载失败静默降级为纯手输，不阻断表单
    } finally {
      setNamesLoaded(true);
    }
  };

  return (
    <div className="p-4 rounded-lg bg-page border border-edge space-y-3" data-testid="jd-classification">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Tags className="w-4 h-4 text-sage" />
          <span className="text-xs font-bold text-ink">方向分类（选填）</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
              source === 'rule'
                ? 'bg-info/10 text-info border-info/30'
                : 'bg-white text-muted border-edge'
            }`}
            data-testid="cf-source-badge"
          >
            {source === 'rule' ? '词典建议 · 低置信' : '手动填写'}
          </span>
        </div>
        <button
          type="button"
          onClick={onSuggest}
          disabled={suggesting || suggestDisabled}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-sage/40 text-sage hover:bg-sage-soft disabled:opacity-40 text-xs font-semibold transition cursor-pointer"
          data-testid="cf-suggest"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {suggesting ? '匹配中...' : '词典建议'}
        </button>
      </div>

      <p className="text-[11px] leading-relaxed text-muted">
        零 LLM 词典规则匹配，按你的岗位名/职责/要求回填行业·产品·场景·技能（低置信，建议核对后再提交）；
        职能与主角色请手动填写。留空则本次分析不记录方向分类。
      </p>

      <div>
        <label className="block text-[11px] font-bold text-ink mb-1">关联方向</label>
        <input
          type="text"
          list="cf-direction-options"
          value={value.directionName}
          onChange={(e) => onChange({ directionName: e.target.value })}
          onFocus={handleDirectionFocus}
          placeholder="选择或输入方向名（同名自动复用已有方向，如：电商零售）"
          className={INPUT_CLASS}
          data-testid="cf-direction-name"
        />
        <datalist id="cf-direction-options">
          {directionNames.map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {DIM_FIELDS.map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="block text-[11px] font-bold text-ink mb-1">{label}</label>
            <input
              type="text"
              value={value[key]}
              onChange={(e) => onChange({ [key]: e.target.value })}
              placeholder={placeholder}
              className={INPUT_CLASS}
              data-testid={`cf-${key}`}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
