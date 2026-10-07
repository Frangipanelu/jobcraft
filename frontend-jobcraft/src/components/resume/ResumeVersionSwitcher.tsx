import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useResumeVersionsQuery, useSetCurrentVersionMutation } from '../../features/resume/hooks';
import { resumeVersionGroupKey } from '../../features/resume/mappers';
import { useToastActions } from '../../context/JobCraftContext';
import type { ResumeVersionWire } from '../../api/types';

interface ResumeVersionSwitcherProps {
  /** 当前查看的简历版本 id（字符串；本地示例/未知 id 不渲染） */
  resumeId: string;
}

/**
 * 行展示名：版本名 → 岗位名 → 兜底「我的简历」（与编辑器标题口径一致）。
 * 用 `||` 而非 `??`：空串版本名同样视为缺省，回退岗位名（不穿透成空标签）。
 */
function versionLabel(wire: ResumeVersionWire): string {
  return (wire.version_name || wire.position) || '我的简历';
}

/**
 * T-M6-7：简历版本下拉列表（同组 v1/v2/v3 + 当前徽标 + 设为当前）。
 * - 只渲染同组版本（组键走 `resumeVersionGroupKey`，与 useResumesQuery 同源锁步，
 *   保持 API 顺序即 version_no DESC）；
 * - `resumeId` 不在 wire 列表（本地示例/未知 id）→ 不渲染；
 * - 加载中/失败：无数据即静默降级（不渲染），不崩不刷屏；
 * - 点击容器外部关闭下拉（仿 TopHeader 既有先例）。
 */
export const ResumeVersionSwitcher: React.FC<ResumeVersionSwitcherProps> = ({ resumeId }) => {
  const { data: wires } = useResumeVersionsQuery();
  const setCurrent = useSetCurrentVersionMutation();
  const { showToast } = useToastActions();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 点击容器外部关闭下拉（浮层 w-60 悬挂在编辑器上，不关会一直挡住正文）
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const mine = wires?.find((w) => String(w.id) === resumeId);
  if (!mine) return null;

  const groupKey = resumeVersionGroupKey(mine);
  const siblings = (wires ?? []).filter((w) => resumeVersionGroupKey(w) === groupKey);

  const handleSetCurrent = (versionId: number) => {
    setCurrent.mutate(versionId, {
      onSuccess: () => {
        showToast({
          type: 'success',
          title: '已设为当前版本',
          message: '投递时将使用该版本的简历快照。',
        });
        setOpen(false);
      },
      onError: (error: unknown) => {
        showToast({
          type: 'error',
          title: '设置失败',
          message: (error as Error).message || '请稍后重试',
        });
      },
    });
  };

  return (
    <div className="relative" data-testid="resume-version-switcher" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="menu"
        title="查看同岗位简历版本并切换当前投递版本"
        className="flex items-center gap-1 px-2 py-0.5 rounded-lg border border-edge bg-white hover:bg-page text-ink text-[11px] font-semibold transition cursor-pointer"
      >
        <span>{versionLabel(mine)}</span>
        <ChevronDown className="w-3.5 h-3.5 text-faint" />
      </button>

      {open && (
        <div
          data-testid="resume-version-list"
          role="menu"
          aria-label="同岗位简历版本"
          className="absolute left-0 top-full mt-1 z-30 w-60 bg-white rounded-lg border border-edge shadow-2xs py-1"
        >
          {siblings.map((w) => (
            <div
              key={w.id}
              role="none"
              className="flex items-center justify-between gap-2 px-3 py-1.5 hover:bg-page"
            >
              <span className="text-xs text-ink truncate">{versionLabel(w)}</span>
              <span className="flex items-center gap-1.5 shrink-0">
                {w.selected_for_application ? (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sage-soft text-sage border border-sage-soft">
                    当前
                  </span>
                ) : (
                  <button
                    type="button"
                    role="menuitem"
                    aria-label={`设为 ${versionLabel(w)} 为当前版本`}
                    onClick={() => handleSetCurrent(w.id)}
                    disabled={setCurrent.isPending}
                    className="px-2 py-0.5 rounded border border-edge bg-white hover:bg-page text-ink text-[10px] font-semibold transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    设为当前
                  </button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
