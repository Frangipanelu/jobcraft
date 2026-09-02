import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  FileSearch,
  Sparkles,
  Plus,
  ArrowRight,
  Trash2,
  Building2,
  Calendar,
  Layers,
  Search,
  ExternalLink,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  FileText,
  Clock
} from 'lucide-react';

export const JDAnalysisCenterView: React.FC = () => {
  const { jdAnalyses, createJDAnalysis, deleteJDAnalysis, navigateTo, interviewDraft } = useJobCraft();

  const [activeTab, setActiveTab] = useState<'create' | 'history'>('create');
  const [company, setCompany] = useState('');
  const [role, setRole] = useState('');
  const [salaryRange, setSalaryRange] = useState('');
  const [rawText, setRawText] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const sampleJD = `【岗位职责】
1. 主导端侧大模型（On-Device LLM）与个人生产力场景的 AI 交互形态设计与业务落地；
2. 搭建面向轻量化大模型的质量评测基准与自动化 Eval 管线，持续优化上下文感知与意图识别准确率；
3. 与算法及工程团队紧密协同，制定模型微调数据标注标准，推动内存占用与端侧延迟优化；
4. 负责核心业务指标的定义、监控与 AB 实验迭代。

【任职要求】
1. 3 年以上 AI/搜索/推荐产品经验，深入理解 Transformer、端侧计算与 RAG 机制；
2. 具备从 0 到 1 搭建质量评估基准体系的成熟方法论，熟练掌握常用评估指标（NDCG/Faithfulness/Recall 等）；
3. 出色的跨团队推进力与严谨的数据敏感度，有技术背景或能直接与算法架构师对话者优先。`;

  const handleStartAnalysis = (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim() || !role.trim() || !rawText.trim()) return;

    setIsAnalyzing(true);
    setTimeout(() => {
      const newAnalysisId = createJDAnalysis({
        company: company.trim(),
        role: role.trim(),
        rawText: rawText.trim()
      });
      setIsAnalyzing(false);
      setCompany('');
      setRole('');
      setSalaryRange('');
      setRawText('');

      // Navigate to the full JD report to view results and provide return button
      navigateTo('jd_report', { jdId: newAnalysisId });
    }, 800);
  };

  const handleUsePreset = () => {
    setCompany('某头部科技公司');
    setRole('AI 产品经理（端侧与 Agent 方向）');
    setSalaryRange('40K-60K · 16薪');
    setRawText(sampleJD);
  };

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
            仅依赖真实 JD 原文进行全景结构化研判，穿透 ATS 关键词、隐藏招聘意图与能力缺口，指导后续简历定制与面试应答
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
                <h2 className="text-sm font-bold text-ink">新建 JD 全景研判表单</h2>
                <p className="text-[11px] text-muted">填写岗位基本信息并粘贴 JD 原文，系统将自动拆解分析维度</p>
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
            {/* Meta Fields Table */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div>
                <label className="block text-xs font-bold text-ink mb-1.5">
                  目标公司名称 <span className="text-error">*</span>
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
                  应聘岗位名称 <span className="text-error">*</span>
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

              <div>
                <label className="block text-xs font-bold text-ink mb-1.5">
                  预期薪酬范围 (选填)
                </label>
                <input
                  type="text"
                  placeholder="例如：35K-50K · 16薪"
                  value={salaryRange}
                  onChange={(e) => setSalaryRange(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-white outline-none placeholder:text-faint"
                />
              </div>
            </div>

            {/* Raw JD Text Field */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-ink">
                  岗位招聘要求原文 (JD Text) <span className="text-error">*</span>
                </label>
                <span className="text-[11px] text-faint">
                  已输入 {rawText.length} 字 · 包含职责与要求即可
                </span>
              </div>
              <textarea
                required
                rows={10}
                placeholder="直接从招聘网站或猎头渠道复制粘贴岗位的职位描述、任职要求与加分项..."
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                className="w-full p-4 rounded-lg border border-edge focus:border-sage focus:ring-1 focus:ring-sage text-xs text-ink bg-canvas font-mono leading-relaxed outline-none placeholder:text-faint"
              />
            </div>

            {/* Submit Action Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-edge">
              <div className="flex items-center gap-2 text-xs text-muted">
                <CheckCircle2 className="w-4 h-4 text-sage" />
                <span>分析将自动生成：ATS 关键词库、招聘暗话潜台词、能力缺口审计与经历匹配清单</span>
              </div>

              <button
                type="submit"
                disabled={isAnalyzing || !company.trim() || !role.trim() || !rawText.trim()}
                className="px-6 py-2.5 rounded-lg bg-sage hover:bg-sage-dim disabled:opacity-50 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-xs shrink-0 cursor-pointer"
              >
                {isAnalyzing ? (
                  <>
                    <Sparkles className="w-4 h-4 animate-spin text-sage-dim" />
                    <span>正在进行全景深度研判...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-sage-dim" />
                    <span>开始全景深度研判 →</span>
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
                            onClick={() => deleteJDAnalysis(analysis.id)}
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
