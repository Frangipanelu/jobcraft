import React, { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, X } from 'lucide-react';
import { useToastActions } from '../../context/JobCraftContext';
import { JDClassificationSection } from './JDClassificationSection';
import {
  hasClassificationInput,
  saveClassificationEdit,
} from '../../features/jd/classification';
import type {
  ClassificationSource,
  ClassificationValue,
} from '../../features/jd/classification';
import { JD_ANALYSES_QUERY_KEY } from '../../features/jd/mappers';
import * as directionApi from '../../api/direction';
import type { JDAnalysis } from '../../types/jobcraft';

/**
 * 历史表格 · 编辑方向分类弹窗（T-M4-4）。
 *
 * 交互约定（对齐 NewInterviewModal 惯例）：遮罩点击 / 「关闭」按钮 / ESC 关闭；
 * 内容体复用受控组件 JDClassificationSection（含词典建议）；保存链复用
 * classification.saveClassificationEdit（方向名未变保留 direction_id，
 * 变化则 find-or-create）；成功 → 失效 JD_ANALYSES_QUERY_KEY + success toast + 关闭；
 * 失败 → error toast 不静默、弹窗保持打开（同 T-M4-3 分类失败语义）。
 */
export interface JDClassificationEditModalProps {
  /** 待编辑的分析行（预填其 jdClassification） */
  analysis: JDAnalysis;
  onClose: () => void;
}

export const JDClassificationEditModal: React.FC<JDClassificationEditModalProps> = ({
  analysis,
  onClose,
}) => {
  const { showToast } = useToastActions();
  const queryClient = useQueryClient();

  const existing = analysis.jdClassification ?? null;
  const [value, setValue] = useState<ClassificationValue>(() => ({
    directionName: existing?.directionName || '',
    jobFunction: existing?.jobFunction || '',
    primaryRole: existing?.primaryRole || '',
    industry: existing?.industry || '',
    product: existing?.product || '',
    scenario: existing?.scenario || '',
    skills: existing?.skills || '',
  }));
  const [source, setSource] = useState<ClassificationSource>(
    existing?.source === 'rule' ? 'rule' : 'manual',
  );
  const [suggesting, setSuggesting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const handleChange = (patch: Partial<ClassificationValue>) => {
    setValue((prev) => ({ ...prev, ...patch }));
    // 任何手动编辑 → 来源翻回 manual（用户确认，后端记 confirmed/high）
    setSource('manual');
  };

  const handleSuggest = async () => {
    const text = [analysis.role, analysis.rawText].filter((s) => s.trim()).join('\n');
    if (!text.trim()) return;
    setSuggesting(true);
    try {
      const result = await directionApi.suggestDirection(text);
      if (!result.matched) {
        showToast({
          type: 'info',
          title: '词典未命中',
          message: '没有匹配到方向模板，可手动填写分类字段。',
        });
        return;
      }
      setValue((prev) => ({
        ...prev,
        directionName: prev.directionName.trim() || result.direction_name,
        industry: result.industry || prev.industry,
        product: result.product || prev.product,
        scenario: result.scenario || prev.scenario,
        skills: result.skills || prev.skills,
      }));
      setSource('rule');
    } catch (e) {
      showToast({
        type: 'error',
        title: '词典建议失败',
        message: (e as Error).message || '可手动填写分类字段',
      });
    } finally {
      setSuggesting(false);
    }
  };

  const handleSave = async () => {
    const analysisId = Number(analysis.id);
    if (!Number.isInteger(analysisId) || analysisId <= 0) {
      showToast({
        type: 'error',
        title: '方向分类保存失败',
        message: '该记录没有可写入的真实分析 id',
      });
      return;
    }
    if (!hasClassificationInput(value)) {
      showToast({
        type: 'warning',
        title: '方向分类',
        message: '方向分类未保存：请至少填写方向名或一个分类维度',
      });
      return;
    }
    setSaving(true);
    try {
      const result = await saveClassificationEdit(analysisId, value, source, {
        previousDirectionId: existing?.directionId ?? null,
        previousDirectionName: existing?.directionName ?? '',
      });
      if (result.status !== 'saved') {
        showToast({
          type: 'warning',
          title: '方向分类',
          message: result.reason || '方向分类未保存',
        });
        return;
      }
      // 表格行与报告详情共用同一查询缓存 → 一次失效同步刷新
      await queryClient.invalidateQueries({ queryKey: [...JD_ANALYSES_QUERY_KEY] });
      showToast({
        type: 'success',
        title: '方向分类已保存',
        message: `已更新「${analysis.company} · ${analysis.role}」的方向分类。`,
      });
      onClose();
    } catch (e) {
      // 失败不静默：error toast + 弹窗保持打开（可直接重试）
      showToast({
        type: 'error',
        title: '方向分类保存失败',
        message: (e as Error).message || '请稍后重试',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" data-testid="jd-classification-edit-modal">
      {/* 遮罩点击关闭 */}
      <div
        className="absolute inset-0 bg-[rgba(15,20,18,0.55)] backdrop-blur-[4px]"
        onClick={onClose}
      />
      <div className="relative w-full max-w-xl mx-4 rounded-2xl bg-white border border-edge shadow-2xs overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-edge">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              aria-label="关闭"
              className="w-6 h-6 flex items-center justify-center rounded-md text-faint hover:text-ink hover:bg-page transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
            <div>
              <h2 className="text-sm font-bold text-ink">编辑方向分类</h2>
              <p className="text-[11px] text-muted mt-0.5">
                {analysis.company} · {analysis.role}
              </p>
            </div>
          </div>
        </div>

        {/* Body：复用结构化表单的方向分类区块（受控） */}
        <div className="px-6 py-4 max-h-[65vh] overflow-y-auto">
          <JDClassificationSection
            value={value}
            source={source}
            suggesting={suggesting}
            suggestDisabled={!analysis.role.trim() && !analysis.rawText.trim()}
            onChange={handleChange}
            onSuggest={handleSuggest}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-edge bg-canvas/50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-lg border border-edge bg-white text-ink text-xs font-medium hover:bg-page transition cursor-pointer disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            data-testid="cf-edit-save"
            className="px-5 py-2 rounded-lg bg-sage hover:bg-sage-dim disabled:opacity-50 text-white text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{saving ? '保存中...' : '保存分类'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
