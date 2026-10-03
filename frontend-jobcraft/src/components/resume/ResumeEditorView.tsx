import React, { useState, useEffect } from 'react';
import { useJobCraft, useToastActions } from '../../context/JobCraftContext';
import { useJobsQuery } from '../../features/jobs/hooks';
import { useExperiencesQuery } from '../../features/experiences/hooks';
import { useCreateExpressionMutation } from '../../features/experiences/expressionHooks';
import {
  useResumesQuery,
  useApplyResumeAiSuggestionMutation,
  useRejectResumeAiSuggestionMutation,
  useApplyAllResumeAiSuggestionsMutation,
  useUpdateResumeBulletTextMutation,
  useDeleteResumeBulletMutation,
  useSaveResumeMutation,
  useGenerateResumeSuggestionsMutation,
  useSyncResumePersonalInfoMutation,
} from '../../features/resume/hooks';
import { useProfileQuery } from '../../features/profile/hooks';
import { ResumePrintPreview } from './ResumePrintPreview';
import {
  Sparkles,
  Check,
  Download,
  Save,
  Trash2,
  Edit2,
  Layers,
  ArrowRight,
  RotateCcw,
  Sparkle,
  RefreshCcw
} from 'lucide-react';

interface ResumeEditorViewProps {
  resumeId?: string;
  jobId?: string;
  embedded?: boolean;
}

export const ResumeEditorView: React.FC<ResumeEditorViewProps> = ({
  resumeId,
  jobId,
  embedded = false
}) => {
  const { navigateTo } = useJobCraft();
  const { showToast } = useToastActions();
  const { data: jobs = [] } = useJobsQuery();
  const { data: resumes = {} } = useResumesQuery();
  const { data: experiences = [] } = useExperiencesQuery();

  const applySuggestion = useApplyResumeAiSuggestionMutation();
  const rejectSuggestion = useRejectResumeAiSuggestionMutation();
  const applyAllSuggestions = useApplyAllResumeAiSuggestionsMutation();
  const editBullet = useUpdateResumeBulletTextMutation();
  const deleteBullet = useDeleteResumeBulletMutation();
  const saveResume = useSaveResumeMutation();
  const generateSuggestions = useGenerateResumeSuggestionsMutation();
  const saveExpression = useCreateExpressionMutation();
  const { data: profile } = useProfileQuery();
  const syncPersonalInfo = useSyncResumePersonalInfoMutation();

  // FE-RESUME-03：只读 A4 预览 + window.print() 打印导出（产品裁决①）
  const [showPrintPreview, setShowPrintPreview] = useState(false);

  // active 简历 id 为编辑器局部状态（legacy context.activeResumeId 仅本视图消费）
  const [activeResumeId, setActiveResumeId] = useState<string | null>(null);

  // 解析当前编辑的简历 id：优先显式 resumeId，其次由 jobId 定位投递站简历，最后回退第一个真实简历
  const boundResumeId = resumeId
    ?? (jobId
      ? jobs.find((j) => j.id === jobId)?.resumeId
      : undefined)
    ?? Object.keys(resumes)[0];

  useEffect(() => {
    if (boundResumeId) setActiveResumeId(boundResumeId);
  }, [boundResumeId]);

  const activeId = activeResumeId && resumes[activeResumeId] ? activeResumeId : boundResumeId;
  const resume = activeId ? resumes[activeId] : null;
  const [editingBulletId, setEditingBulletId] = useState<string | null>(null);
  const [tempBulletText, setTempBulletText] = useState('');
  const [selectedBulletForSource, setSelectedBulletForSource] = useState<string | null>(null);

  if (!resume) {
    return (
      <div className="p-8 text-center space-y-4">
        <div className="text-muted text-sm">尚未生成简历，请先完成简历生成。</div>
        <p className="text-xs text-muted/70">在「JD 深度分析」页面点击「定制简历」按钮，AI 将根据您的经历卡和岗位要求自动生成匹配简历。</p>
        {jobId ? (
          <button
            onClick={() => navigateTo('job_workspace', { jobId })}
            className="px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            返回岗位工作台
          </button>
        ) : (
          <button
            onClick={() => navigateTo('jd_analysis_center')}
            className="px-4 py-2 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
          >
            去分析岗位
          </button>
        )}
      </div>
    );
  }

  const handleStartEditBullet = (bulletId: string, currentText: string) => {
    setEditingBulletId(bulletId);
    setTempBulletText(currentText);
    setSelectedBulletForSource(bulletId);
  };

  // resume 非空已由上方早退保证 → activeId 必非空（TS 需显式收窄）
  const rid = activeId as string;

  // FE-RESUME-02：保存要点编辑 → 落库 PATCH resume_markdown（失败保留编辑态 + error toast）
  const handleSaveBulletEdit = async (
    sectionId: string,
    itemId: string,
    bulletId: string,
  ) => {
    try {
      const result = await editBullet.mutateAsync({
        resumeId: rid,
        sectionId,
        itemId,
        bulletId,
        newText: tempBulletText,
      });
      setEditingBulletId(null);
      showToast(
        result.synced
          ? { type: 'success', title: '要点已保存', message: '修改已同步到投递记录。' }
          : { type: 'warning', title: '本地示例已更新', message: '该简历为本地示例，未同步后端。' },
      );
    } catch (error: unknown) {
      showToast({
        type: 'error',
        title: '保存失败',
        message: (error as Error).message || '请稍后重试',
      });
    }
  };

  const persistToast = (synced: boolean, title: string, message: string) => {
    showToast(
      synced
        ? { type: 'success', title, message }
        : { type: 'warning', title, message: '本地示例未同步后端。' },
    );
  };

  const handleApplySuggestion = (suggestionId: string) => {
    applySuggestion
      .mutateAsync({ resumeId: rid, suggestionId })
      .then((result) => persistToast(result.synced, '已应用优化', '改写已同步保存。'))
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '应用失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleRejectSuggestion = (suggestionId: string) => {
    rejectSuggestion
      .mutateAsync({ resumeId: rid, suggestionId })
      .then((result) => {
        // T-M6-2：建议状态列已从 submission 剥离，仅本地标记（M6-3 接回前不落库）
        showToast({
          type: 'success',
          title: '已忽略该建议',
          message: result.synced
            ? '状态已同步保存。'
            : '已在本地标记忽略，建议域改版完成后将支持同步。',
        });
      })
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '操作失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleApplyAllSuggestions = () => {
    applyAllSuggestions
      .mutateAsync({ resumeId: rid })
      .then((result) =>
        persistToast(result.synced, '已应用全部优化', `共改写 ${result.appliedCount} 条要点。`),
      )
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '批量应用失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleDeleteBullet = (sectionId: string, itemId: string, bulletId: string) => {
    deleteBullet
      .mutateAsync({ resumeId: rid, sectionId, itemId, bulletId })
      .then((result) => persistToast(result.synced, '要点已删除', '修改已同步到投递记录。'))
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '删除失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  // FE-RESUME-02：生成/重生成 AI 优化建议（fire-and-forget 不阻塞编辑）
  const handleGenerateSuggestions = () => {
    generateSuggestions.mutate(
      { resumeId: rid },
      {
        onSuccess: (result) => {
          if (!result.generated) {
            if (result.reason === 'unavailable') {
              showToast({
                type: 'info',
                title: 'AI 建议待接入',
                message: '建议生成正在改版，当前可继续手动编辑与保存。',
              });
              return;
            }
            showToast(
              result.reason === 'local'
                ? {
                    type: 'warning',
                    title: '本地示例不支持',
                    message: '示例简历没有后端记录，无法生成建议。',
                  }
                : { type: 'info', title: '暂无可优化要点', message: '简历中没有可分析的要点。' },
            );
            return;
          }
          showToast(
            result.count > 0
              ? { type: 'success', title: '优化建议已生成', message: `已生成 ${result.count} 条建议并同步保存。` }
              : { type: 'info', title: '未发现明显问题', message: '当前简历表达已较完善。' },
          );
        },
        onError: (error: unknown) => {
          showToast({
            type: 'error',
            title: '生成失败',
            message: (error as Error).message || '请稍后重试',
          });
        },
      },
    );
  };

  const handleSave = (resumeId: string) => {
    saveResume
      .mutateAsync({ resumeId })
      .then((result) => {
        if (result.saved) {
          showToast({
            type: 'success',
            title: '简历已保存',
            message: '内容已同步到当前投递记录。'
          });
        } else {
          showToast({
            type: 'warning',
            title: '该简历为本地示例',
            message: '暂不支持保存后端。'
          });
        }
      })
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '保存失败',
          message: (error as Error).message || '请稍后重试'
        });
      });
  };

  // FE-RESUME-03：从个人资料同步简历头部（仅覆盖 profile 非空字段，保留手动微调）
  const handleSyncFromProfile = () => {
    if (!profile) return;
    syncPersonalInfo
      .mutateAsync({
        resumeId: rid,
        personalInfo: {
          name: profile.name,
          email: profile.email,
          phone: profile.phone,
          location: profile.city,
          title: profile.role,
          github: profile.github,
        },
      })
      .then(({ applied }) => {
        if (!applied.length) {
          showToast({
            type: 'info',
            title: '暂无可同步内容',
            message: '请先在「个人资料」中完善姓名、邮箱等信息。',
          });
          return;
        }
        showToast({
          type: 'success',
          title: '已同步个人信息',
          message: `从个人资料带入 ${applied.length} 项，已保存到简历。`,
        });
      })
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '同步失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleExportPDF = () => {
    setShowPrintPreview(true);
  };

  // U2b「存为表达」：把选中 bullet 的定制文本保存为目标经历卡的标准化表达（candidate 态）
  const handleSaveExpression = () => {
    if (!activeBullet || !linkedExp) return;
    const targetCardId = parseInt(String(linkedExp.id), 10);
    if (!Number.isFinite(targetCardId)) {
      showToast({
        type: 'error',
        title: '保存失败',
        message: '目标经历资产 ID 无效'
      });
      return;
    }
    saveExpression
      .mutateAsync({
        cardId: targetCardId,
        content: activeBullet.text,
        source_refs: [
          {
            id: rid,
            source_type: 'resume',
            source_id: rid,
            locator: activeBullet.id
          }
        ]
      })
      .then(() => {
        showToast({
          type: 'success',
          title: '已保存为候选表达',
          message: `已存入「${linkedExp?.title}」表达库，可在经历资产库中激活。`
        });
      })
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '保存失败',
          message: (error as Error).message || '请稍后重试'
        });
      });
  };

  // Find linked experience for selected bullet
  const allBullets = (resume.sections || []).flatMap((s) => (s.items || []).flatMap((i) => i.bullets || []));
  const activeBullet = allBullets.find((b) => b.id === selectedBulletForSource) || allBullets[0];
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
              onClick={handleSyncFromProfile}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
              title="从个人资料带入姓名、联系方式、GitHub 等头部信息"
            >
              <RefreshCcw className="w-3.5 h-3.5" />
              <span>同步资料</span>
            </button>

            <button
              onClick={() => handleSave(rid)}
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
              onClick={handleSyncFromProfile}
              className="flex items-center gap-1 px-3 py-1 rounded-md border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
              title="从个人资料带入姓名、联系方式、GitHub 等头部信息"
            >
              <RefreshCcw className="w-3.5 h-3.5" />
              <span>同步资料</span>
            </button>

            <button
              onClick={() => handleSave(rid)}
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
              <div className="flex items-center gap-3">
                {(resume.aiSuggestions || []).length > 0 && (
                  <button
                    onClick={handleGenerateSuggestions}
                    disabled={generateSuggestions.isPending}
                    title="结合岗位 JD 分析结论，根据当前简历重新生成优化建议"
                    className="flex items-center gap-1 text-xs font-semibold text-sage hover:text-sage-dim transition disabled:opacity-50 cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>{generateSuggestions.isPending ? '生成中…' : '重新生成'}</span>
                  </button>
                )}
                {pendingSuggestions.length > 0 && (
                  <button
                    onClick={handleApplyAllSuggestions}
                    className="text-xs font-semibold text-sage hover:text-sage-dim transition cursor-pointer"
                  >
                    全部应用
                  </button>
                )}
              </div>
            </div>

            <div className="space-y-3 max-h-[calc(100vh-230px)] overflow-y-auto pr-1">
              {(resume.aiSuggestions || []).length === 0 ? (
                <div className="text-center py-6 space-y-2.5">
                  <Sparkle className="w-5 h-5 text-sage mx-auto" />
                  <p className="text-xs text-muted">尚未生成优化建议</p>
                  <button
                    onClick={handleGenerateSuggestions}
                    disabled={generateSuggestions.isPending}
                    className="mx-auto flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-2xs transition disabled:opacity-50 cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>
                      {generateSuggestions.isPending ? '正在生成…' : '生成 AI 优化建议'}
                    </span>
                  </button>
                  <p className="text-[11px] text-faint">逐条给出可直接应用的改写建议</p>
                </div>
              ) : (
                (resume.aiSuggestions || []).map((sug, idx) => (
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
                    ) : sug.stale ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning-bg text-warning font-semibold border border-warning/20">
                        已失效
                      </span>
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
                        onClick={() => handleApplySuggestion(sug.id)}
                        disabled={sug.stale || applySuggestion.isPending}
                        title={
                          sug.stale
                            ? '对应要点已变更或删除，点击「重新生成」刷新建议'
                            : undefined
                        }
                        className="flex-1 py-1 rounded bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition text-center shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                      >
                        应用优化
                      </button>
                      <button
                        onClick={() => handleRejectSuggestion(sug.id)}
                        disabled={rejectSuggestion.isPending}
                        className="px-2.5 py-1 rounded bg-page hover:bg-edge text-muted text-xs transition disabled:opacity-40 cursor-pointer"
                      >
                        忽略
                      </button>
                    </div>
                  )}
                </div>
                ))
              )}
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
                        const isEditing = editingBulletId === bullet.id;
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
                            {isEditing ? (
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
                                      handleDeleteBullet(section.id, item.id, bullet.id);
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
                    {linkedExp.results && linkedExp.results.length > 0 ? (
                      linkedExp.results.map((met, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded bg-sage-soft text-sage font-mono text-[11px] font-bold border border-sage/20"
                        >
                          {met}
                        </span>
                      ))
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-page text-faint font-mono text-[11px]">
                        暂无量化数据
                      </span>
                    )}
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
                  <button
                    onClick={handleSaveExpression}
                    disabled={saveExpression.isPending || !linkedExp}
                    className="mt-2 w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-sage/20 bg-sage-soft hover:bg-sage/10 text-sage font-semibold text-xs transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    title={`把当前要点另存为「${linkedExp?.title ?? ''}」的候选表达（可在经历资产库中激活复用）`}
                  >
                    {saveExpression.isPending ? (
                      <span>正在保存…</span>
                    ) : (
                      <>
                        <Save className="w-3.5 h-3.5" />
                        <span>存为候选表达</span>
                      </>
                    )}
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

      <ResumePrintPreview
        resume={resume}
        isOpen={showPrintPreview}
        onClose={() => setShowPrintPreview(false)}
      />
    </div>
  );
};
