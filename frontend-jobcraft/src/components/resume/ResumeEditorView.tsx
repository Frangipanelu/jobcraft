import React, { useState, useEffect } from 'react';
import { useJobCraft, useToastActions } from '../../context/JobCraftContext';
import { useJobsQuery } from '../../features/jobs/hooks';
import { useExperiencesQuery } from '../../features/experiences/hooks';
import { useCreateExpressionMutation } from '../../features/experiences/expressionHooks';
import {
  useResumesQuery,
  useUpdateResumeBulletTextMutation,
  useDeleteResumeBulletMutation,
  useSaveResumeMutation,
  useRewriteResumeBulletMutation,
  useSyncResumePersonalInfoMutation,
  useReorderResumeMutation,
  useToggleSectionHiddenMutation,
  useAddResumeItemMutation,
  useRenameResumeItemMutation,
  useDeleteResumeItemMutation,
} from '../../features/resume/hooks';
import { useJdAnalysesQuery } from '../../features/jd/hooks';
import { useProfileQuery } from '../../features/profile/hooks';
import { dimensionLabel } from '../../utils/dimensions';
import { resumeToMarkdown } from '../../utils/resumeParser';
import { triggerBlobDownload } from '../../utils/download';
import { ResumePrintPreview } from './ResumePrintPreview';
import { ResumeSectionsEditor } from './ResumeSectionsEditor';
import { ResumeVersionSwitcher } from './ResumeVersionSwitcher';
import type { CapabilityGap } from '../../types/jobcraft';
import {
  Sparkles,
  Download,
  FileDown,
  Save,
  Layers,
  ArrowRight,
  Sparkle,
  RefreshCcw,
  Wand2
} from 'lucide-react';

/** T-M6-3：缺口严重度 → 徽标样式与文案。 */
const SEVERITY_BADGE: Record<CapabilityGap['severity'], { label: string; cls: string }> = {
  high: { label: '高', cls: 'bg-warning-bg text-warning border-warning/20' },
  medium: { label: '中', cls: 'bg-sage-soft text-sage border-sage-soft' },
  low: { label: '低', cls: 'bg-page text-faint border-edge' },
};

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

  const editBullet = useUpdateResumeBulletTextMutation();
  const deleteBullet = useDeleteResumeBulletMutation();
  const saveResume = useSaveResumeMutation();
  const rewriteBullet = useRewriteResumeBulletMutation();
  const saveExpression = useCreateExpressionMutation();
  const { data: profile } = useProfileQuery();
  const syncPersonalInfo = useSyncResumePersonalInfoMutation();
  const { data: jdAnalyses = [] } = useJdAnalysesQuery();
  const reorder = useReorderResumeMutation();
  const toggleHidden = useToggleSectionHiddenMutation();
  const addItem = useAddResumeItemMutation();
  const renameItem = useRenameResumeItemMutation();
  const deleteItem = useDeleteResumeItemMutation();

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

  // resume 非空已由上方早退保证 → activeId 必非空（TS 需显式收窄）
  const rid = activeId as string;

  // T-M6-4：双击直编保存 → 双写落库（失败已 toast 后上抛，组件保留编辑态）
  const handleSaveBulletEdit = async (args: {
    sectionId: string;
    itemId: string;
    bulletId: string;
    newText: string;
  }) => {
    try {
      const result = await editBullet.mutateAsync({
        resumeId: rid,
        ...args,
      });
      persistToast(result.synced, '要点已保存', '修改已同步到简历版本。');
    } catch (error: unknown) {
      showToast({
        type: 'error',
        title: '保存失败',
        message: (error as Error).message || '请稍后重试',
      });
      throw error;
    }
  };

  const persistToast = (synced: boolean, title: string, message: string) => {
    showToast(
      synced
        ? { type: 'success', title, message }
        : { type: 'warning', title, message: '本地示例未同步后端。' },
    );
  };

  // T-M6-3：缺口任务列 → AI 改写选中要点（中栏点选为改写目标，1 次 LLM 后落库）
  const handleRewriteFromGap = (gap: CapabilityGap) => {
    if (!selectedBulletForSource) {
      showToast({
        type: 'info',
        title: '请先点选要点',
        message: '在中间栏点选要改写的要点后，再点击「AI 改写」。',
      });
      return;
    }
    rewriteBullet
      .mutateAsync({
        resumeId: rid,
        bulletId: selectedBulletForSource,
        gap: {
          dimension: gap.dimension,
          current: gap.current,
          jdEvidence: gap.jdEvidence,
          rewriteHint: gap.rewriteHint,
        },
      })
      .then((result) => persistToast(result.synced, '已 AI 改写', '改写结果已同步保存。'))
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '改写失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  // T-M6-3：evidence 缺口 → 按锚点经历卡跳经历资产库补强
  const handleEvidenceJump = (gap: CapabilityGap) => {
    if (!gap.cardId) {
      showToast({
        type: 'info',
        title: '未锚定经历卡',
        message: '该缺口未关联具体经历，请先在经历资产库补充对应素材。',
      });
      return;
    }
    navigateTo('experiences', { expId: gap.cardId });
  };

  const handleDeleteBullet = (sectionId: string, itemId: string, bulletId: string) => {
    deleteBullet
      .mutateAsync({ resumeId: rid, sectionId, itemId, bulletId })
      .then((result) => persistToast(result.synced, '要点已删除', '修改已同步到简历版本。'))
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '删除失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  // ---------------------------------------------------------------------------
  // T-M6-4：结构化布局编辑（两级重排 / 显隐 / 条目增删改名，双写落库）
  // ---------------------------------------------------------------------------

  const runLayoutEdit = (
    promise: Promise<{ synced: boolean }>,
    okTitle: string,
    failTitle: string,
  ) => {
    promise
      .then((result) => persistToast(result.synced, okTitle, '修改已同步到简历版本。'))
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: failTitle,
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleReorderSection = ({ fromId, toId }: { fromId: string; toId: string }) => {
    runLayoutEdit(
      reorder.mutateAsync({ resumeId: rid, scope: 'section', fromId, toId }),
      '模块顺序已调整',
      '调整失败',
    );
  };

  const handleReorderItem = (args: { sectionId: string; fromId: string; toId: string }) => {
    runLayoutEdit(
      reorder.mutateAsync({ resumeId: rid, scope: 'item', ...args }),
      '条目顺序已调整',
      '调整失败',
    );
  };

  const handleToggleHidden = ({ sectionId }: { sectionId: string }) => {
    toggleHidden
      .mutateAsync({ resumeId: rid, sectionId })
      .then((result) =>
        persistToast(
          result.synced,
          result.hidden ? '模块已隐藏' : '模块已显示',
          result.hidden
            ? '隐藏模块不会出现在导出与面试准备内容中。'
            : '修改已同步到简历版本。',
        ),
      )
      .catch((error: unknown) => {
        showToast({
          type: 'error',
          title: '操作失败',
          message: (error as Error).message || '请稍后重试',
        });
      });
  };

  const handleAddItem = async ({ sectionId, title }: { sectionId: string; title: string }) => {
    try {
      const result = await addItem.mutateAsync({ resumeId: rid, sectionId, title });
      persistToast(result.synced, '条目已添加', '修改已同步到简历版本。');
    } catch (error: unknown) {
      showToast({
        type: 'error',
        title: '添加失败',
        message: (error as Error).message || '请稍后重试',
      });
      throw error;
    }
  };

  const handleRenameItem = async (args: { sectionId: string; itemId: string; title: string }) => {
    try {
      const result = await renameItem.mutateAsync({ resumeId: rid, ...args });
      persistToast(result.synced, '条目已更新', '修改已同步到简历版本。');
    } catch (error: unknown) {
      showToast({
        type: 'error',
        title: '重命名失败',
        message: (error as Error).message || '请稍后重试',
      });
      throw error;
    }
  };

  const handleDeleteItem = (args: { sectionId: string; itemId: string; itemTitle: string }) => {
    if (
      !window.confirm(
        `确定要删除条目「${args.itemTitle}」及其全部要点吗？此操作不可撤销。`,
      )
    ) {
      return;
    }
    runLayoutEdit(
      deleteItem.mutateAsync({ resumeId: rid, sectionId: args.sectionId, itemId: args.itemId }),
      '条目已删除',
      '删除失败',
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

  // T-M6-5：真下载——把当前编辑态导出为 .md（前端态即权威，磁盘生成文件编辑后已过期）
  const handleDownloadMd = () => {
    const md = resumeToMarkdown(resume);
    const base = (resume.personalInfo.name || resume.versionName).replace(
      /[\\/:*?"<>|]/g,
      '',
    );
    triggerBlobDownload(md, `${base}-求职简历.md`, 'text/markdown;charset=utf-8');
    showToast({
      type: 'success',
      title: '已下载 Markdown',
      message: '当前编辑态内容已导出为 .md 文件',
    });
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

  // T-M6-3：缺口任务清单（版本关联的 JD 分析 capability_gaps；存量版本未关联则空态）
  const capabilityGaps = resume.jobAnalysisId
    ? jdAnalyses.find((a) => a.id === resume.jobAnalysisId)?.capabilityGaps || []
    : [];

  return (
    <div className="p-6 md:p-8 max-w-[1600px] mx-auto space-y-5 animate-in fade-in duration-300">
      {/* 1. Header Control Bar (Shown only when not embedded, or as a compact toolbar when embedded) */}
      {!embedded ? (
        <div className="bg-white rounded-xl border border-edge px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-lg font-bold text-ink">{resume.versionName}</h1>
              <ResumeVersionSwitcher resumeId={rid} />
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
              onClick={handleDownloadMd}
              data-testid="download-md-action"
              title="把当前编辑态导出为 Markdown 文件"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>下载 MD</span>
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
            <ResumeVersionSwitcher resumeId={rid} />
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
              onClick={handleDownloadMd}
              data-testid="download-md-action"
              title="把当前编辑态导出为 Markdown 文件"
              className="flex items-center gap-1 px-3 py-1 rounded-md border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>下载 MD</span>
            </button>

            <button
              onClick={handleExportPDF}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>导出 PDF</span>
            </button>
          </div>
        </div>
      )}

      {/* 2. Three-Column Precision Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (3 cols): JD 能力缺口任务清单（T-M6-3） */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white rounded-xl border border-edge p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between border-b border-page pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sage" />
                <h3 className="text-sm font-bold text-ink">
                  缺口任务 ({capabilityGaps.length})
                </h3>
              </div>
              <span className="text-[11px] text-faint">按 JD 能力缺口</span>
            </div>

            <p className="text-[11px] text-faint leading-relaxed">
              中栏点选一条要点，点「AI 改写」按缺口方向改写；证据缺口跳经历资产库补强。
            </p>

            <div className="space-y-3 max-h-[calc(100vh-270px)] overflow-y-auto pr-1">
              {capabilityGaps.length === 0 ? (
                <div className="text-center py-6 space-y-2.5">
                  <Sparkle className="w-5 h-5 text-sage mx-auto" />
                  <p className="text-xs text-muted">暂无缺口任务</p>
                  <p className="text-[11px] text-faint leading-relaxed">
                    {resume.jobAnalysisId
                      ? '该岗位分析未产出能力缺口清单，或分析版本较早。'
                      : '该简历未关联 JD 分析；从「JD 深度分析」生成的简历会自动带出缺口任务。'}
                  </p>
                </div>
              ) : (
                capabilityGaps.map((gap) => {
                  const isEvidence = gap.kind === 'evidence';
                  const severity = SEVERITY_BADGE[gap.severity] || SEVERITY_BADGE.low;
                  return (
                    <div
                      key={gap.id}
                      className="p-3 rounded-xl border border-edge bg-white space-y-2 text-xs transition hover:border-sage/50"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-ink text-xs">
                          {dimensionLabel(gap.dimension)}
                        </span>
                        <span className="flex items-center gap-1">
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold border ${severity.cls}`}
                          >
                            {severity.label}
                          </span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold border ${
                              isEvidence
                                ? 'bg-warning-bg text-warning border-warning/20'
                                : 'bg-sage-soft text-sage border-sage-soft'
                            }`}
                          >
                            {isEvidence ? '需补强' : '可改写'}
                          </span>
                        </span>
                      </div>

                      <p className="text-[11px] text-muted leading-relaxed">{gap.jdEvidence}</p>

                      {!isEvidence && gap.rewriteHint && (
                        <p className="text-[11px] text-sage bg-sage-soft p-2 rounded-lg border border-sage-soft leading-relaxed">
                          <strong className="text-ink">改写方向：</strong>
                          {gap.rewriteHint}
                        </p>
                      )}

                      {isEvidence ? (
                        <button
                          onClick={() => handleEvidenceJump(gap)}
                          disabled={!gap.cardId}
                          title={gap.cardId ? undefined : '该缺口未锚定经历卡，暂无法跳转'}
                          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-page hover:bg-edge text-ink font-semibold text-xs transition shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                        >
                          <span>去经历资产库补强</span>
                          <ArrowRight className="w-3.5 h-3.5 text-sage" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleRewriteFromGap(gap)}
                          disabled={rewriteBullet.isPending}
                          className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold transition shadow-2xs disabled:opacity-50 cursor-pointer"
                        >
                          <Wand2 className="w-3.5 h-3.5" />
                          <span>{rewriteBullet.isPending ? 'AI 改写中…' : 'AI 改写选中要点'}</span>
                        </button>
                      )}
                    </div>
                  );
                })
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

          {/* Sections（T-M6-4：结构化编辑器——两级拖拽/↑↓/增删/显隐/双击直编） */}
          <ResumeSectionsEditor
            resume={resume}
            selectedBulletId={selectedBulletForSource}
            onSelectBullet={setSelectedBulletForSource}
            onSaveBulletEdit={handleSaveBulletEdit}
            onDeleteBullet={(args) => handleDeleteBullet(args.sectionId, args.itemId, args.bulletId)}
            onReorderSection={handleReorderSection}
            onReorderItem={handleReorderItem}
            onToggleHidden={handleToggleHidden}
            onAddItem={handleAddItem}
            onRenameItem={handleRenameItem}
            onDeleteItem={handleDeleteItem}
          />
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
