import React from 'react';
import { createPortal } from 'react-dom';
import { Printer, X } from 'lucide-react';
import type { ResumeVersion } from '../../types/jobcraft';

interface ResumePrintPreviewProps {
  resume: ResumeVersion;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * FE-RESUME-03：简历只读 A4 预览 + 浏览器打印导出（产品裁决①）。
 * - 只读渲染，不做就地编辑（markdown 编辑模型单一真相源，无双源漂移）；
 * - 「打印 / 另存 PDF」调用 `window.print()`，A4 版式由 index.css 的
 *   `@page { size: A4; margin: 0 }` + 组件内边距控制；打印时应用壳（#root）隐藏，
 *   本组件经 portal 直挂 body，不受影响；
 * - 屏幕态：遮罩 + 工具栏（print:hidden），内容区可滚动。
 */
export const ResumePrintPreview: React.FC<ResumePrintPreviewProps> = ({
  resume,
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const { personalInfo, summary, sections } = resume;
  const contactParts = [
    personalInfo.phone && `电话：${personalInfo.phone}`,
    personalInfo.email && `邮箱：${personalInfo.email}`,
    personalInfo.location && `城市：${personalInfo.location}`,
    personalInfo.title && `职位：${personalInfo.title}`,
    personalInfo.github && `GitHub/作品：${personalInfo.github}`,
  ].filter(Boolean) as string[];

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col"
      data-testid="resume-print-preview"
    >
      <div
        className="absolute inset-0 bg-black/60 print:hidden"
        aria-hidden="true"
        onClick={onClose}
      />

      <div className="relative z-10 flex items-center justify-end gap-2 px-4 py-3 print:hidden">
        <button
          type="button"
          onClick={onClose}
          data-testid="print-preview-close"
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-xs font-semibold transition cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
          <span>关闭</span>
        </button>
        <button
          type="button"
          onClick={() => window.print()}
          data-testid="print-action"
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-sage hover:bg-sage-dim text-white text-xs font-semibold shadow-xs transition cursor-pointer"
        >
          <Printer className="w-3.5 h-3.5" />
          <span>打印 / 另存 PDF</span>
        </button>
      </div>

      <div className="relative z-10 flex-1 overflow-y-auto px-4 pb-6 print:overflow-visible print:px-0 print:pb-0">
        <article
          className="mx-auto w-full max-w-[210mm] bg-white p-[12mm] shadow-2xs text-ink print:max-w-none print:shadow-none print:p-0"
          data-testid="resume-a4-page"
        >
          <h1 className="text-xl font-bold leading-tight">
            {personalInfo.name || resume.versionName}
          </h1>
          {contactParts.length > 0 && (
            <p className="mt-1 text-[11px] text-muted">{contactParts.join(' | ')}</p>
          )}
          <p className="mt-0.5 text-[11px] text-muted">
            求职意向：{resume.jobTitle}
            {resume.company ? ` · ${resume.company}` : ''}
          </p>

          {summary && (
            <section className="mt-4">
              <h2 className="text-sm font-bold border-b border-edge pb-1">核心能力</h2>
              <p className="mt-1.5 text-[11px] leading-relaxed whitespace-pre-wrap">
                {summary}
              </p>
            </section>
          )}

          {sections.map((sec) => (
            <section key={sec.id} className="mt-4">
              <h2 className="text-sm font-bold border-b border-edge pb-1">
                {sec.title}
              </h2>
              {(sec.items || []).map((item) => (
                <div key={item.id} className="mt-2.5">
                  <h3 className="text-xs font-semibold text-ink">
                    {item.title}
                    {item.period ? ` · ${item.period}` : ''}
                  </h3>
                  {(item.bullets || []).map((b) => (
                    <p
                      key={b.id}
                      className="mt-1 text-[11px] leading-relaxed whitespace-pre-wrap pl-3 border-l border-edge"
                    >
                      {b.text}
                    </p>
                  ))}
                </div>
              ))}
            </section>
          ))}
        </article>
      </div>
    </div>,
    document.body,
  );
};
