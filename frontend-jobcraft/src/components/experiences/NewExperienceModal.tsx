import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import { ExperienceCategory } from '../../types/jobcraft';
import {
  X,
  Layers,
  Sparkles,
  Plus,
  ArrowRight,
  TrendingUp,
  Tag
} from 'lucide-react';

interface NewExperienceModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NewExperienceModal: React.FC<NewExperienceModalProps> = ({ isOpen, onClose }) => {
  const { createExperience, showToast } = useJobCraft();

  const [title, setTitle] = useState('');
  const [category, setCategory] = useState<ExperienceCategory>('project');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [period, setPeriod] = useState('2024.06 - 2025.12');
  const [background, setBackground] = useState('');
  const [responsibility, setResponsibility] = useState('');
  const [actionsInput, setActionsInput] = useState('');
  const [resultsInput, setResultsInput] = useState('');
  const [metricsInput, setMetricsInput] = useState('');
  const [tagsInput, setTagsInput] = useState('');

  if (!isOpen) return null;

  const handleUseTemplate = () => {
    setTitle('端侧轻量化大模型量化评测与交互设计');
    setCompany('未来智能实验室');
    setRole('AI 产品经理');
    setCategory('project');
    setPeriod('2025.01 - 2025.08');
    setBackground('移动端用户在弱网或离线场景下对实时生成式体验需求强烈，但云端请求延迟高且存在隐私泄露顾虑。');
    setResponsibility('主导将 7B 级大模型部署至端侧移动设备的产品方案与评测标准制定。');
    setActionsInput('与算法及工程团队配合定义 4-bit 量化剪枝策略；主导设计了动态分级上下文滑窗机制与端侧流式交互规范；搭建自动化回归测试集。');
    setResultsInput('实现首字响应时间控制在 350ms 内，内存占用降低 42%，在弱网环境下用户留存率提升 22.8%。');
    setMetricsInput('首字延迟 TTFT 350ms, 内存占用 -42%, 留存率 +22.8%');
    setTagsInput('端侧大模型, 量化评测, 交互设计, 性能优化');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    const metrics = metricsInput
      ? metricsInput.split(/[,，]/).map((m) => m.trim()).filter(Boolean)
      : ['核心指标持续提升'];
    const capabilityTags = tagsInput
      ? tagsInput.split(/[,，]/).map((t) => t.trim()).filter(Boolean)
      : ['AI产品', '项目落地'];
    const actions = actionsInput
      ? actionsInput.split(/[\n;；]/).map((a) => a.trim()).filter(Boolean)
      : [actionsInput || '负责端到端方案设计与推进'];
    const results = resultsInput
      ? resultsInput.split(/[\n;；]/).map((r) => r.trim()).filter(Boolean)
      : [resultsInput || '达成预期业务收益'];

    createExperience({
      title: title.trim(),
      category,
      company: company.trim() || '自主研发',
      role: role.trim() || '负责人',
      period: period.trim(),
      background: background.trim(),
      responsibility: responsibility.trim(),
      actions,
      results,
      metrics,
      capabilityTags,
      targetJobs: ['AI 产品经理', '策略产品经理'],
      jdMatches: [{ jdTitle: 'AI 产品经理', stars: 5 }],
      resumeVersionsUsed: ['字节跳动定制版 V2.1']
    });

    showToast({
      type: 'success',
      title: '经历资产创建成功',
      message: '已存入个人核心资产库，支持多版本迭代与一键定制。'
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-edge shadow-xl max-w-2xl w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-5 md:p-6 border-b border-edge flex items-center justify-between bg-canvas">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sage-soft text-sage flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-ink">新建经历资产卡片</h3>
              <p className="text-xs text-muted">
                以 STAR 原则深度结构化你的职业成果，构建可复用的王牌证据库
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleUseTemplate}
              className="text-xs text-sage hover:text-sage font-semibold flex items-center gap-1 cursor-pointer bg-sage-soft px-2.5 py-1 rounded-md border border-sage-soft"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>填入高质范本</span>
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-faint hover:text-ink hover:bg-page transition cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1 custom-scrollbar">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                经历名称 <span className="text-error">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="例如：AI 搜索评测体系建设"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                经历分类
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as ExperienceCategory)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              >
                <option value="project">项目经历</option>
                <option value="work">工作经历</option>
                <option value="internship">实习经历</option>
                <option value="education">教育经历</option>
                <option value="competition">竞赛与开源</option>
                <option value="paper">论文与专利</option>
                <option value="other">其他经历</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                所在机构 / 公司
              </label>
              <input
                type="text"
                placeholder="例如：快知智能科技"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                担任角色
              </label>
              <input
                type="text"
                placeholder="例如：AI 产品专家"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                时间周期
              </label>
              <input
                type="text"
                placeholder="例如：2024.03 - 2025.12"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>
          </div>

          {/* STAR Fields */}
          <div className="p-4 rounded-xl bg-canvas border border-edge space-y-3">
            <div className="text-xs font-bold text-ink flex items-center gap-1.5">
              <span>STAR 结构化拆解</span>
              <span className="text-[10px] text-faint font-normal">（标准化沉淀）</span>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-muted mb-0.5">
                S · 业务背景与痛点 (Situation)
              </label>
              <textarea
                rows={2}
                placeholder="当时面临什么业务挑战、技术瓶颈或痛点？"
                value={background}
                onChange={(e) => setBackground(e.target.value)}
                className="w-full p-2.5 text-xs rounded-lg border border-edge bg-white text-ink resize-none focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-muted mb-0.5">
                T · 任务与目标 (Task / Responsibility)
              </label>
              <textarea
                rows={2}
                placeholder="你的核心职责与设定的定量/定性攻坚目标是什么？"
                value={responsibility}
                onChange={(e) => setResponsibility(e.target.value)}
                className="w-full p-2.5 text-xs rounded-lg border border-edge bg-white text-ink resize-none focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-muted mb-0.5">
                A · 行动与策略 (Actions - 支持多条换行)
              </label>
              <textarea
                rows={3}
                placeholder="具体采取了哪些关键技术、架构设计、产品策略或跨团队推进动作？"
                value={actionsInput}
                onChange={(e) => setActionsInput(e.target.value)}
                className="w-full p-2.5 text-xs rounded-lg border border-edge bg-white text-ink resize-none focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-muted mb-0.5">
                R · 结果与收益 (Results - 支持多条换行)
              </label>
              <textarea
                rows={2}
                placeholder="取得了怎样的业务成果、指标改善或行业认可？"
                value={resultsInput}
                onChange={(e) => setResultsInput(e.target.value)}
                className="w-full p-2.5 text-xs rounded-lg border border-edge bg-white text-ink resize-none focus:border-sage focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                核心量化指标 (英文或中文逗号分隔)
              </label>
              <input
                type="text"
                placeholder="例如：幻觉率 -34.2%, NDCG@5 +18.5%"
                value={metricsInput}
                onChange={(e) => setMetricsInput(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-ink mb-1">
                能力标签 (逗号分隔)
              </label>
              <input
                type="text"
                placeholder="例如：大模型评测, Prompt工程, 质量基准"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-lg border border-edge bg-white text-ink focus:border-sage focus:outline-none"
              />
            </div>
          </div>

          {/* Footer actions */}
          <div className="pt-3 border-t border-edge flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs text-muted hover:bg-page rounded-lg transition cursor-pointer"
            >
              取消
            </button>
            <button
              type="submit"
              className="px-5 py-2 text-xs bg-sage hover:bg-sage-dim text-white font-bold rounded-lg shadow-xs transition cursor-pointer"
            >
              保存至经历资产库
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
