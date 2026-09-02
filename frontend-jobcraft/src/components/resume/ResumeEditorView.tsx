import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  FileText,
  Sparkles,
  Check,
  X,
  Download,
  Save,
  Eye,
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
  ExternalLink,
  Layers,
  ArrowRight,
  RotateCcw,
  Sparkle,
  Zap,
  Target,
  FileCheck,
  HelpCircle,
  Clock
} from 'lucide-react';

interface ResumeEditorViewProps {
  resumeId?: string;
  jobId?: string;
  embedded?: boolean;
}

export const ResumeEditorView: React.FC<ResumeEditorViewProps> = ({
  resumeId = 'res-byte-1',
  jobId = 'job-1',
  embedded = false
}) => {
  const {
    resumes,
    experiences,
    applyResumeAISuggestion,
    rejectResumeAISuggestion,
    applyAllResumeAISuggestions,
    updateResumeBulletText,
    addResumeBullet,
    deleteResumeBullet,
    navigateTo,
    showToast
  } = useJobCraft();

  const resume = resumes[resumeId] || resumes['res-byte-1'];
  const [editingBulletId, setEditingBulletId] = useState<string | null>(null);
  const [tempBulletText, setTempBulletText] = useState('');
  const [selectedBulletForSource, setSelectedBulletForSource] = useState<string | null>('bullet-exp1-1');

  if (!resume) {
    return <div className="p-8 text-center text-muted">未找到简历数据</div>;
  }

  const handleStartEditBullet = (bulletId: string, currentText: string) => {
    setEditingBulletId(bulletId);
    setTempBulletText(currentText);
    setSelectedBulletForSource(bulletId);
  };

  const handleSaveBulletEdit = (sectionId: string, itemId: string, bulletId: string) => {
    updateResumeBulletText(sectionId, itemId, bulletId, tempBulletText);
    setEditingBulletId(null);
    showToast({
      type: 'success',
      title: '要点内容已保存'
    });
  };

  const handleExportPDF = () => {
    showToast({
      type: 'success',
      title: '正在生成高保真单页 PDF...',
      message: '已按 1:1 招聘标准排版，导出准备完毕。'
    });
  };

  // Find linked experience for selected bullet
  const allBullets紧 = (resume.sections || []).flatMap((s) => (s.items || []).flatMap((i) => i.bullets || []));
  const activeBullet = allBullets紧.find((b) => b.id === selectedBulletForSource) || allBullets紧[0];
  const linkedExp = activeBullet?.originalExperienceId
    ? experiences.find((e) => e.id === activeBullet.originalExperienceId)
    : experiences[0];

  const pendingSuggestions = (resume.aiSuggestions || []).filter((s) => !s.applied && !s.rejected);

  return (
    <div className="p-6 md:p-8 max-w-[1600px] mx-auto space-y-5 animate-in fade-in duration-300">
      {/* 1. Header Control Bar (Shown only when not embedded, or as a compact toolbar when embedded) */}
      {!embedded ? (
        <div className="bg-white rounded-xl border border-edge px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-bold text-ink">{resume.versionName}</h1>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-sage-soft text-sage border border-sage-soft">
                针对 {resume.company} · {resume.jobTitle} 定制
              </span>
            </div>
            <p className="text-xs text-faint mt-0.5">上次保存：{resume.updatedAt} · 一页纸精炼排版</p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={() => showToast({ type: 'success', title: '简历草稿已保存' })}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" />
              <span>保存草稿</span>
            </button>

            <button
              onClick={handleExportPDF}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>导出 PDF</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-edge px-5 py-2.5 flex items-center justify-between gap-4 shadow-2xs">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-ink">{resume.versionName}</span>
            <span className="text-xs text-muted">·</span>
            <span className="text-xs text-sage font-medium bg-sage-soft px-2 py-0.5 rounded">
              100% 单页自适应布局
            </span>
            <span className="text-xs text-faint">上次同步：刚刚</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => showToast({ type: 'success', title: '简历草稿已保存' })}
              className="flex items-center gap-1 px-3 py-1 rounded-md border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" />
              <span>保存草稿</span>
            </button>

            <button
              onClick={handleExportPDF}
              className="flex items-center gap-1.5 px-3.5 py-1 rounded-md bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>导出 PDF</span>
            </button>
          </div>
        </div>
      )}

      {/* 2. Three-Column Precision Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (3.5 cols): AI Optimization Suggestions */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white rounded-xl border border-edge p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between border-b border-page pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sage" />
                <h3 className="text-sm font-bold text-ink">
                  AI 针对性优化 ({pendingSuggestions.length})
                </h3>
              </div>
              {pendingSuggestions.length > 0 && (
                <button
                  onClick={applyAllResumeAISuggestions}
                  className="text-xs font-semibold text-sage hover:text-sage-dim transition cursor-pointer"
                >
                  全部应用
                </button>
              )}
            </div>

            <div className="space-y-3 max-h-[calc(100vh-230px)] overflow-y-auto pr-1">
              {(resume.aiSuggestions || []).map((sug, idx) => (
                <div
                  key={sug.id}
                  className={`p-3 rounded-xl border text-xs space-y-2 transition ${
                    sug.applied
                      ? 'bg-sage-soft/60 border-sage-soft text-sage'
                      : sug.rejected
                      ? 'bg-page border-edge text-faint opacity-60'
                      : 'bg-white border-edge hover:border-sage/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold text-ink text-xs">
                      {idx + 1}. {sug.title}
                    </span>
                    {sug.applied ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-sage-soft text-sage font-semibold flex items-center gap-1 border border-sage-soft">
                        <Check className="w-3 h-3" /> 已应用
                      </span>
                    ) : sug.rejected ? (
                      <span className="text-[10px] text-faint">已忽略</span>
                    ) : null}
                  </div>

                  <div className="space-y-1">
                    <div className="text-[11px] text-faint">
                      <span className="text-muted font-medium">原表达：</span>
                      <span className="line-through">{sug.originalText}</span>
                    </div>
                    <div className="text-xs text-sage font-medium bg-sage-soft p-2 rounded-lg border border-sage-soft leading-relaxed">
                      <strong className="text-ink">建议改写：</strong> {sug.suggestedText}
                    </div>
                  </div>

                  <p className="text-[11px] text-muted">{sug.reason}</p>

                  {!sug.applied && !sug.rejected && (
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        onClick={() => applyResumeAISuggestion(sug.id)}
                        className="flex-1 py-1 rounded bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition text-center shadow-2xs cursor-pointer"
                      >
                        应用优化
                      </button>
                      <button
                        onClick={() => rejectResumeAISuggestion(sug.id)}
                        className="px-2.5 py-1 rounded bg-page hover:bg-edge text-muted text-xs transition cursor-pointer"
                      >
                        忽略
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center Column (5.5 cols): Editable High-Fidelity A4 Resume Document */}
        <div className="lg:col-span-6 bg-white rounded-xl border border-edge shadow-sm p-8 space-y-6 min-h-[900px]">
          {/* Resume Header */}
          <div className="text-center space-y-1.5 border-b border-edge pb-5">
            <h2 className="text-2xl font-bold text-ink tracking-tight">
              {resume.personalInfo.name}
            </h2>
            <p className="text-xs text-muted font-medium">
              {resume.personalInfo.title} · {resume.personalInfo.location} · {resume.personalInfo.phone} · {resume.personalInfo.email}
            </p>
          </div>

          {/* Personal Summary */}
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-page pb-1">
              个人优势与求职画像
            </h3>
            <p className="text-xs text-ink leading-relaxed text-justify">
              {resume.summary}
            </p>
          </div>

          {/* Sections */}
          {resume.sections.map((section) => (
            <div key={section.id} className="space-y-3">
              <h3 className="text-xs font-bold text-ink uppercase tracking-wider border-b border-page pb-1">
                {section.title}
              </h3>

              <div className="space-y-4">
                {section.items.map((item) => (
                  <div key={item.id} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-ink">{item.title}</span>
                      {item.period && (
                        <span className="text-faint font-mono text-[11px]">{item.period}</span>
                      )}
                    </div>
                    {item.subtitle && (
                      <div className="text-xs font-medium text-muted italic">
                        {item.subtitle}
                      </div>
                    )}

                    {/* Bullet points */}
                    <ul className="space-y-2 pt-1">
                      {item.bullets.map((bullet) => {
                        const isEditing迁移 = editingBulletId === bullet.id;
                        const isSelected = selectedBulletForSource === bullet.id;

                        return (
                          <li
                            key={bullet.id}
                            onClick={() => setSelectedBulletForSource(bullet.id)}
                            className={`text-xs text-ink rounded-lg p-2 transition group relative cursor-pointer border ${
                              isSelected
                                ? 'border-sage bg-sage-soft/30'
                                : 'border-transparent hover:border-edge hover:bg-page'
                            }`}
                          >
                            {isEditing迁移 ? (
                              <div className="space-y-2">
                                <textarea
                                  value={tempBulletText}
                                  onChange={(e) => setTempBulletText(e.target.value)}
                                  rows={3}
                                  className="w-full p-2 text-xs border border-sage rounded-lg focus:outline-none bg-white font-sans leading-relaxed text-ink"
                                />
                                <div className="flex items-center gap-2 justify-end">
                                  <button
                                    onClick={() => setEditingBulletId(null)}
                                    className="px-2 py-1 text-xs text-faint hover:bg-page rounded cursor-pointer"
                                  >
                                    取消
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleSaveBulletEdit(section.id, item.id, bullet.id)
                                    }
                                    className="px-3 py-1 text-xs bg-sage text-white font-semibold rounded hover:bg-sage-dim shadow-2xs cursor-pointer"
                                  >
                                    保存修改
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 leading-relaxed">
                                  <span className="text-sage font-bold mr-1.5">•</span>
                                  <span>{bullet.text}</span>
                                  {bullet.jdMatchTag && (
                                    <span className="ml-2 inline-block text-[10px] px-1.5 py-0.2 rounded bg-warning-bg text-warning font-semibold border border-warning/20">
                                      {bullet.jdMatchTag}
                                    </span>
                                  )}
                                </div>

                                <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 shrink-0 transition">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleStartEditBullet(bullet.id, bullet.text);
                                    }}
                                    className="p-1 text-faint hover:text-sage rounded transition cursor-pointer"
                                    title="直接编辑"
                                  >
                                    <Edit2 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      deleteResumeBullet(section.id, item.id, bullet.id);
                                    }}
                                    className="p-1 text-faint hover:text-error rounded transition cursor-pointer"
                                    title="删除要点"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right Column (3 cols): Evidence Traceability & Structure */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white rounded-xl border border-edge p-5 shadow-2xs space-y-4">
            <div className="flex items-center gap-2 border-b border-page pb-3">
              <Layers className="w-4 h-4 text-sage" />
              <h3 className="text-sm font-bold text-ink">经历资产溯源与证据链</h3>
            </div>

            {linkedExp ? (
              <div className="space-y-3 text-xs animate-in fade-in">
                <div>
                  <div className="text-[11px] text-faint font-medium">关联职业经历资产：</div>
                  <div className="font-bold text-ink mt-0.5 leading-snug">
                    {linkedExp.title}
                  </div>
                </div>

                <div className="p-3 bg-page rounded-lg border border-edge space-y-1.5">
                  <div className="text-[11px] text-muted font-medium">资产版本状态：</div>
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded bg-sage-soft text-sage font-bold border border-sage-soft">
                      当前资产库版本: {linkedExp.currentVersion}
                    </span>
                    <span className="text-[10px] text-faint">
                      {linkedExp.company} · {linkedExp.period}
                    </span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-ink">STAR 原始背景：</div>
                  <div className="p-2.5 rounded-lg bg-canvas border border-edge text-muted leading-relaxed">
                    {linkedExp.background}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-ink">核心动作与攻坚点：</div>
                  <div className="p-2.5 rounded-lg bg-canvas border border-edge text-ink leading-relaxed space-y-1">
                    {(linkedExp.actions || []).map((act, idx) => (
                      <div key={idx} className="flex items-start gap-1.5">
                        <span className="text-sage font-bold">•</span>
                        <span>{act}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-ink">量化业务成果：</div>
                  <div className="flex flex-wrap gap-1.5">
                    {(linkedExp.metrics || []).map((met, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 rounded bg-sage-soft text-sage font-mono text-[11px] font-bold border border-sage/20"
                      >
                        {met}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="pt-2 border-t border-page">
                  <button
                    onClick={() => navigateTo('experiences', { expId: linkedExp.id })}
                    className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-page hover:bg-edge text-ink font-semibold text-xs transition cursor-pointer"
                  >
                    <span>在经历资产库中查看与维护</span>
                    <ArrowRight className="w-3.5 h-3.5 text-sage" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-faint">
                点击中间简历要点，即可在此查看其对应的经历库 STAR 原文与证据链。
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
