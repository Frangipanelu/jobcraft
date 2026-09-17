import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  FileSearch,
  Sparkles,
  Plus,
  Trash2,
  Search,
  CheckCircle2,
  Clock,
  Wand2
} from 'lucide-react';
import { splitJd } from '../../api/job';
import { useJdAnalysesQuery, useDeleteJdAnalysisMutation } from '../../features/jd/hooks';

export const JDAnalysisCenterView: React.FC = () => {
  const { createStructuredJDAnalysis, navigateTo, interviewDraft, showToast, syncJdAnalyses } = useJobCraft();

  const { data: jdAnalyses = [] } = useJdAnalysesQuery();
  const deleteAnalysis = useDeleteJdAnalysisMutation({ onSync: syncJdAnalyses });

  const [activeTab, setActiveTab] = useState<'create' | 'history'>('create');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [dutyText, setDutyText] = useState('');
  const [requirements, setRequirements] = useState<{ text: string; tag: 'hard' | 'required' | 'preferred' }[]>([]);
  const [pastedRaw, setPastedRaw] = useState('');
  const [isSplitting, setIsSplitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const TAG_LABELS: Record<string, string> = {
    hard: '硬性门槛',
    required: '必选',
    preferred: '加分项'
  };

  const sampleJD = `【岗位职责】
1. 主导端侧大模型（On-Device LLM）与个人生产力场景的 AI 交互形态设计与业务落地；
2. 搭建面向轻量化大模型的质量评测基准与自动化 Eval 管线，持续优化上下文感知与意图识别准确率；
3. 与算法及工程团队紧密协同，制定模型微调数据标注标准，推动内存占用与端侧延迟优化；
4. 负责核心业务指标的定义、监控与 AB 实验迭代。

【任职要求】
1. 3 年以上 AI/搜索/推荐产品经验，深入理解 Transformer、端侧计算与 RAG 机制；
2. 具备从 0 到 1 搭建质量评估基准体系的成熟方法论，熟练掌握常用评估指标（NDCG/Faithfulness/Recall 等）；
3. 出色的跨团队推进力与严谨的数据敏感度，有技术背景或能直接与算法架构师对话者优先。`;

  const handleSplitPrefill = async () => {
    if (!pastedRaw.trim()) return;
    setIsSplitting(true);
    try {
      const result = await splitJd(pastedRaw.trim());
      setDutyText(result.duties.join('\n'));
      setRequirements(result.requirements.map((r) => ({
        text: r.text,
        tag: (r.tag === 'hard' || r.tag === 'required' || r.tag === 'preferred') ? r.tag : 'required'
      })));
    } catch (e) {
      console.error('JD 拆分失败:', e);
    } finally {
      setIsSplitting(false);
    }
  };

  const handleUsePreset = async () => {
    setCompany('某头部科技公司');
    setRole('AI 产品经理（端侧与 Agent 方向）');
    setPastedRaw(sampleJD);
    setIsSplitting(true);
    try {
      const result = await splitJd(sampleJD);
      setDutyText(result.duties.join('\n'));
      setRequirements((result.requirements || []).map((r) => ({
        text: r.text,
        tag: (r.tag === 'hard' || r.tag === 'required' || r.tag === 'preferred') ? r.tag : 'required'
      })));
    } catch (e) {
      console.error('JD 拆分失败:', e);
    } finally {
      setIsSplitting(false);
    }
  };

  const handleStartAnalysis = (e: React.FormEvent) => {
    e.preventDefault();
    const duties = dutyText.split('\n').map((d) => d.trim()).filter(Boolean);
    const nonEmptyReqs = requirements.filter((r) => r.text.trim());
    if (!company.trim() || !role.trim() || (duties.length === 0 && nonEmptyReqs.length === 0)) return;

    setIsAnalyzing(true);
    setTimeout(() => {
      const newAnalysisId = createStructuredJDAnalysis({
        company: company.trim(),
        role: role.trim(),
        duties,
        requirements: nonEmptyReqs.map((r) => ({ text: r.text.trim(), tag: r.tag }))
      });
      setIsAnalyzing(false);
      setCompany('');
      setRole('');
      setDutyText('');
      setRequirements([]);
      setPastedRaw('');

      // Navigate to the full JD report to view results and provide return button
      navigateTo('jd_report', { jdId: newAnalysisId });
    }, 800);
  };

  const addRequirement = () => setRequirements((prev) => [...prev, { text: '', tag: 'required' }]);
  const updateRequirement = (idx: number, patch: Partial<{ text: string; tag: 'hard' | 'required' | 'preferred' }>) =>
    setRequirements((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const removeRequirement = (idx: number) => setRequirements((prev) => prev.filter((_, i) => i !== idx));

  const filteredAnalyses = jdAnalyses.filter(
    (a) =>
      a.company.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.role.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-edge pb-4">
        <div>
          <h1 className="text-2xl font-bold text-ink tracking-tight">全局 JD 深度分析中心</h1>
          <p className="text-xs md:text-sm text-muted mt-1">
            前端分好类：公司 / 岗位 / 岗位职责 / 任职要求（逐条打标签），
            仅对职责与要求两块内容做 LLM 细节分析（地址、薪资不纳入分析）
          </p>
        </div>

        {/* Top Tab Switcher */}
        <div className="flex items-center gap-1.5 p-1 bg-page rounded-lg border border-edge shrink-0 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('create')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
              activeTab === 'create'
                ? 'bg-white text-ink shadow-2xs'
                : 'text-muted hover:text-ink'
            }`}
          >
            <Plus className="w-3.5 h-3.5 text-sage" />
            <span>发起新 JD 研判</span>
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
              activeTab === 'history'
                ? 'bg-white text-ink shadow-2xs'
                : 'text-muted hover:text-ink'
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-faint" />
            <span>历史研判报告 ({jdAnalyses.length})</span>
          </button>
        </div>
      </div>

      {/* TAB 1: New Analysis Structured Form */}
      {activeTab === 'create' && (
        <div className="bg-white rounded-xl border border-edge overflow-hidden shadow-2xs">
          <div className="bg-page px-6 py-4 border-b border-edge flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-sage-soft text-sage flex items-center justify-center font-bold">
                <FileSearch className="w-4 h-4 text-sage" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-ink">新建结构化 JD 研判表单</h2>
                <p className="text-[11px] text-muted">职责与任职要求已分栏；任职要求逐条点选标签（硬性门槛/必选/加分项）</p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleUsePreset}
              className="text-xs text-sage hover:text-sage-dim font-semibold flex items-center gap-1 transition self-start sm:self-auto"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>填入高潜 AI 岗位范例</span>
            </button>
          </div>

          <form onSubmit={handleStartAnalysis} className="p-6 md:p-8 space-y-6">
            {/* Meta Fields Table：公司 + 岗位（地址/薪资不再采集） */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-bold text-ink mb-1.5">
                  公司名称 <span className="text-error">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="例如：字节跳动、腾讯、某独角兽"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-white outline-none placeholder:text-faint"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-ink mb-1.5">
                  岗位名称 <span className="text-error">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="例如：AI 产品经理、算法专家"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-white outline-none placeholder:text-faint"
                />
              </div>
            </div>

            {/* 粘贴原文 → 自动拆分预填 */}
            <div>
              <label className="block text-xs font-bold text-ink mb-1.5">
                从招聘原文自动拆分（选填）
              </label>
              <div className="flex flex-col gap-2">
                <textarea
                  rows={4}
                  placeholder="直接粘贴整段 JD 原文，点「拆分预填」后自动把职责/硬性要求/加分项分到下方对应栏，可再手工微调..."
                  value={pastedRaw}
                  onChange={(e) => setPastedRaw(e.target.value)}
                  className="w-full p-4 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-canvas font-mono leading-relaxed outline-none placeholder:text-faint"
                />
                <button
                  type="button"
                  onClick={handleSplitPrefill}
                  disabled={isSplitting || !pastedRaw.trim()}
                  className="self-start flex items-center gap-1.5 px-4 py-2 rounded-lg border border-sage/40 text-sage hover:bg-sage-soft disabled:opacity-40 text-xs font-semibold transition cursor-pointer"
                >
                  <Wand2 className="w-3.5 h-3.5" />
                  {isSplitting ? '拆分中...' : '拆分预填到下方'}
                </button>
              </div>
            </div>

            {/* 岗位职责 */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-ink">
                  岗位职责 <span className="text-error">*</span>
                </label>
                <span className="text-[11px] text-faint">每行一条</span>
              </div>
              <textarea
                rows={5}
                required={requirements.length === 0}
                placeholder={'每行一条职责，例如：\n主导端侧大模型交互形态设计\n搭建自动化 Eval 评测管线'}
                value={dutyText}
                onChange={(e) => setDutyText(e.target.value)}
                className="w-full p-4 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-canvas font-mono leading-relaxed outline-none placeholder:text-faint"
              />
            </div>

            {/* 任职要求 + 标签 */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-ink">
                  任职要求 <span className="text-error">*</span>
                </label>
                <button
                  type="button"
                  onClick={addRequirement}
                  className="flex items-center gap-1 text-xs text-sage hover:text-sage-dim font-semibold transition cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  添加一条
                </button>
              </div>
              <div className="space-y-2">
                {requirements.map((req, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <div className="flex items-center p-0.5 bg-page rounded-lg border border-edge shrink-0">
                      {(['hard', 'required', 'preferred'] as const).map((tag) => (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => updateRequirement(idx, { tag })}
                          className={`px-2 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                            req.tag === tag
                              ? tag === 'hard'
                                ? 'bg-error/10 text-error'
                                : tag === 'preferred'
                                  ? 'bg-info/10 text-info'
                                  : 'bg-white text-ink shadow-2xs'
                              : 'text-faint hover:text-ink'
                          }`}
                        >
                          {TAG_LABELS[tag]}
                        </button>
                      ))}
                    </div>
                    <input
                      type="text"
                      value={req.text}
                      onChange={(e) => updateRequirement(idx, { text: e.target.value })}
                      placeholder={
                        idx === 0
                          ? '例如：本科及以上学历，3 年以上 AI 产品经验'
                          : idx === 1
                            ? '例如：熟悉 Python、Redis（点左侧选必选/加分）'
                            : '输入任职要求条目...'
                      }
                      className="flex-1 px-3.5 py-2 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-white outline-none placeholder:text-faint"
                    />
                    <button
                      type="button"
                      onClick={() => removeRequirement(idx)}
                      className="p-1.5 rounded-lg text-muted hover:text-error hover:bg-error-bg transition cursor-pointer shrink-0"
                      title="删除该条"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {requirements.length === 0 && (
                  <button
                    type="button"
                    onClick={addRequirement}
                    className="w-full py-3 rounded-lg border border-dashed border-edge text-xs text-faint hover:text-sage hover:border-sage transition cursor-pointer"
                  >
                    + 点击添加第一条任职要求（可打 硬性门槛 / 必选 / 加分项 标签）
                  </button>
                )}
              </div>

              {/* 标签打点说明 */}
              <div className="mt-3 p-3 rounded-lg bg-page border border-edge text-[11px] leading-relaxed text-muted">
                <div className="font-bold text-ink mb-1">三档标签怎么区分？核心一问：不满足这条，招聘方会不会直接刷掉？</div>
                <ul className="space-y-1 list-none">
                  <li>
                    <span className="font-semibold text-error">硬性门槛</span>：一眼就刷的真门槛——纯年限（如 5 年以上
                    工作经验）、学历（统招本科）、硬性证书（PMP/注会）。这类你通常投递前已筛掉，表单里基本不出现。
                  </li>
                  <li>
                    <span className="font-semibold text-ink">必选</span>：岗位核心能力，面试重点考察深浅——如「熟练使用
                    Python」「3 年以上 AI 产品经验」（️⚠️ 这种「N 年 + 某领域」是能力型年限，算必选，不是硬性门槛）。
                  </li>
                  <li>
                    <span className="font-semibold text-info">加分项</span>：锦上添花，没有也录用——如「熟悉 XX 者优先」「有多模态经验加分」。
                  </li>
                </ul>
              </div>
            </div>

            {/* Submit Action Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-edge">
              <div className="flex items-center gap-2 text-xs text-muted">
                <CheckCircle2 className="w-4 h-4 text-sage" />
                <span>仅分析职责与要求：ATS 关键词、招聘暗话、D1-D8 维度；学历/年限/薪资/地址不纳入（门槛已由标签表达）</span>
              </div>

              <button
                type="submit"
                disabled={isAnalyzing || !company.trim() || !role.trim() || (dutyText.trim() === '' && requirements.filter((r) => r.text.trim()).length === 0)}
                className="px-6 py-2.5 rounded-lg bg-sage hover:bg-sage-dim disabled:opacity-50 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-xs shrink-0 cursor-pointer"
              >
                {isAnalyzing ? (
                  <>
                    <Sparkles className="w-4 h-4 animate-spin text-sage-dim" />
                    <span>正在进行结构化深度研判...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-sage-dim" />
                    <span>开始结构化深度研判 →</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 2: Historical Analysis Registry Table */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-xl border border-edge overflow-hidden shadow-2xs space-y-4">
          <div className="bg-page px-6 py-4 border-b border-edge flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold text-ink">历史 JD 研判档案库</h2>
              <p className="text-[11px] text-muted">已归档的岗位研判报告，可随时回溯查看或一键调取经历定制简历</p>
            </div>

            {/* Search Filter */}
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-faint absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="搜索公司或岗位名称..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg bg-white border border-edge focus:border-sage focus:outline-none text-ink placeholder:text-faint"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-edge text-muted font-semibold bg-canvas">
                  <th className="p-3.5 w-60">目标公司与岗位</th>
                  <th className="p-3.5 w-28">匹配得分</th>
                  <th className="p-3.5 w-28">推荐指数</th>
                  <th className="p-3.5">核心研判结论摘要</th>
                  <th className="p-3.5 w-28">分析日期</th>
                  <th className="p-3.5 w-60 text-right whitespace-nowrap">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-edge">
                {filteredAnalyses.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-faint">
                      未找到符合条件的研判记录
                    </td>
                  </tr>
                ) : (
                  filteredAnalyses.map((analysis) => (
                    <tr key={analysis.id} className="hover:bg-page/40 transition">
                      <td className="p-3.5 align-top font-bold text-ink">
                        <div className="text-sm font-bold text-ink">{analysis.company}</div>
                        <div className="text-xs text-muted font-normal mt-0.5">{analysis.role}</div>
                        {analysis.salaryRange && (
                          <div className="text-[10px] text-warning font-medium mt-1">
                            {analysis.salaryRange}
                          </div>
                        )}
                      </td>
                      <td className="p-3.5 align-top">
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-sage-soft text-sage border border-sage-soft inline-block">
                          {analysis.matchScore}%
                        </span>
                      </td>
                      <td className="p-3.5 align-top">
                        <span className="text-warning tracking-wider font-bold">
                          {'★'.repeat(analysis.recommendationStars || 5)}
                        </span>
                      </td>
                      <td className="p-3.5 align-top text-ink leading-relaxed max-w-md">
                        <div className="line-clamp-2">{analysis.verdictSummary}</div>
                      </td>
                      <td className="p-3.5 align-top text-faint whitespace-nowrap">
                        {analysis.createdAt}
                      </td>
                      <td className="p-3.5 align-middle text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => navigateTo('jd_report', { jdId: analysis.id })}
                            className="px-3 py-1.5 rounded-lg bg-white hover:bg-page text-ink border border-edge text-xs font-medium transition cursor-pointer shadow-2xs"
                          >
                            查看报告
                          </button>
                          <button
                            onClick={() => navigateTo('resume_editor', { jobId: analysis.jobId })}
                            className="px-3 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition cursor-pointer shadow-2xs"
                          >
                            定制简历
                          </button>
                          <button
                            onClick={() => {
                              deleteAnalysis.mutate(analysis.id, {
                                onSuccess: () => showToast({ type: 'info', title: 'JD 分析已删除' }),
                              });
                            }}
                            className="p-1.5 rounded-lg text-muted hover:text-error hover:bg-error-bg transition cursor-pointer"
                            title="删除记录"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
