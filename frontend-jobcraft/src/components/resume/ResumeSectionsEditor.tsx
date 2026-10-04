import React, { useRef, useState } from 'react';
import type { ResumeVersion } from '../../types/jobcraft';
import {
  GripVertical,
  ChevronUp,
  ChevronDown,
  Eye,
  EyeOff,
  Plus,
  Edit2,
  Trash2,
  Check,
  X,
} from 'lucide-react';

/**
 * T-M6-4：简历中栏「结构化编辑器」。
 *
 * 交互基准（Q6 裁决 A，参照用户示例 HTML，架构改造为结构化 sections）：
 * - 单击要点 = 选中（T-M6-3 AI 改写目标）；**双击文字 / 铅笔图标 = 进入直编**（textarea 内联，规避 contenteditable IME 风险）；
 * - 模块（section）与条目（item）**两级拖拽（原生 HTML5，零依赖）+ ↑↓ 备用**；
 * - 条目增删（删除经视图 confirm）、模块显隐开关（隐藏模块灰色折叠展示，导出 markdown 跳过）；
 * - 所有变更经视图回调落库（sections JSON 权威 + markdown 双写）。
 *
 * 本组件只持有编辑 UI 态（直编/改名/添加行/拖拽指示），业务变更与 toast 在视图层。
 */

export interface BulletEditArgs {
  sectionId: string;
  itemId: string;
  bulletId: string;
  newText: string;
}

export interface BulletRefArgs {
  sectionId: string;
  itemId: string;
  bulletId: string;
}

export interface ResumeSectionsEditorProps {
  resume: ResumeVersion;
  /** T-M6-3：中栏点选的要点（左栏 AI 改写目标） */
  selectedBulletId: string | null;
  onSelectBullet(bulletId: string): void;
  /** 双击直编保存：resolve=成功（组件清编辑态）；reject=视图已 toast（保留编辑态） */
  onSaveBulletEdit(args: BulletEditArgs): Promise<void>;
  onDeleteBullet(args: BulletRefArgs): void;
  onReorderSection(args: { fromId: string; toId: string }): void;
  onReorderItem(args: { sectionId: string; fromId: string; toId: string }): void;
  onToggleHidden(args: { sectionId: string }): void;
  /** 添加条目行确认：reject=视图已 toast（保留输入行） */
  onAddItem(args: { sectionId: string; title: string }): Promise<void>;
  onRenameItem(args: { sectionId: string; itemId: string; title: string }): Promise<void>;
  /** 删除条目（视图层先 confirm） */
  onDeleteItem(args: { sectionId: string; itemId: string; itemTitle: string }): void;
}

type DragState = { scope: 'section' | 'item'; id: string; sectionId?: string } | null;

export const ResumeSectionsEditor: React.FC<ResumeSectionsEditorProps> = ({
  resume,
  selectedBulletId,
  onSelectBullet,
  onSaveBulletEdit,
  onDeleteBullet,
  onReorderSection,
  onReorderItem,
  onToggleHidden,
  onAddItem,
  onRenameItem,
  onDeleteItem,
}) => {
  const [editingBulletId, setEditingBulletId] = useState<string | null>(null);
  const [tempBulletText, setTempBulletText] = useState('');
  const [renamingItemId, setRenamingItemId] = useState<string | null>(null);
  const [renameTemp, setRenameTemp] = useState('');
  const [addingSectionId, setAddingSectionId] = useState<string | null>(null);
  const [addItemTemp, setAddItemTemp] = useState('');
  const [dragOverKey, setDragOverKey] = useState<string | null>(null);
  const dragRef = useRef<DragState>(null);

  const startEditBullet = (args: { bulletId: string; text: string }) => {
    setTempBulletText(args.text);
    setEditingBulletId(args.bulletId);
    onSelectBullet(args.bulletId);
  };

  const saveBulletEdit = async (sectionId: string, itemId: string, bulletId: string) => {
    try {
      await onSaveBulletEdit({ sectionId, itemId, bulletId, newText: tempBulletText });
      setEditingBulletId(null);
    } catch {
      /* 视图已 error toast；保留编辑态供重试 */
    }
  };

  const beginRename = (itemId: string, title: string) => {
    setRenameTemp(title);
    setRenamingItemId(itemId);
  };

  const commitRename = async (sectionId: string, itemId: string) => {
    try {
      await onRenameItem({ sectionId, itemId, title: renameTemp });
      setRenamingItemId(null);
    } catch {
      /* 视图已 error toast；保留输入 */
    }
  };

  const commitAdd = async (sectionId: string) => {
    try {
      await onAddItem({ sectionId, title: addItemTemp });
      setAddingSectionId(null);
      setAddItemTemp('');
    } catch {
      /* 视图已 error toast；保留输入 */
    }
  };

  const beginDrag =
    (scope: 'section' | 'item', id: string, sectionId?: string) =>
    (e: React.DragEvent) => {
      dragRef.current = { scope, id, sectionId };
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', id);
      }
    };

  const endDrag = () => {
    dragRef.current = null;
    setDragOverKey(null);
  };

  const allowDrop =
    (scope: 'section' | 'item', id: string, sectionId?: string) =>
    (e: React.DragEvent) => {
      const drag = dragRef.current;
      if (!drag || drag.scope !== scope) return;
      // 条目仅允许同模块内拖拽；自我不响应
      if (scope === 'item' && (drag.sectionId !== sectionId || drag.id === id)) return;
      if (scope === 'section' && drag.id === id) return;
      e.preventDefault();
      setDragOverKey(scope === 'section' ? id : `item:${id}`);
    };

  const dropOn =
    (scope: 'section' | 'item', targetId: string, sectionId?: string) =>
    (e: React.DragEvent) => {
      e.preventDefault();
      const drag = dragRef.current;
      endDrag();
      if (!drag || drag.scope !== scope || drag.id === targetId) return;
      if (scope === 'section') {
        onReorderSection({ fromId: drag.id, toId: targetId });
        return;
      }
      if (drag.sectionId === sectionId) {
        onReorderItem({ sectionId: sectionId as string, fromId: drag.id, toId: targetId });
      }
    };

  return (
    <div className="space-y-3">
      {resume.sections.map((section, sectionIdx) => {
        const isHidden = section.hidden === true;
        return (
          <div
            key={section.id}
            data-testid={`resume-section-${section.id}`}
            onDragOver={allowDrop('section', section.id)}
            onDrop={dropOn('section', section.id)}
            className={
              isHidden
                ? `rounded-lg border border-dashed border-edge bg-page/60 p-3 space-y-3 ${
                    dragOverKey === section.id ? 'ring-1 ring-sage' : ''
                  }`
                : `space-y-3 ${dragOverKey === section.id ? 'border-t-2 border-sage' : ''}`
            }
          >
            <div className="flex items-center gap-1.5 border-b border-page pb-1">
              <span
                draggable
                onDragStart={beginDrag('section', section.id)}
                onDragEnd={endDrag}
                title="拖动调整模块顺序"
                className="text-faint hover:text-sage cursor-grab active:cursor-grabbing"
              >
                <GripVertical className="w-3.5 h-3.5" />
              </span>
              <h3 className="text-xs font-bold text-ink uppercase tracking-wider flex-1">
                {section.title}
              </h3>
              {isHidden && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-page text-faint border border-edge">
                  已隐藏
                </span>
              )}
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => onToggleHidden({ sectionId: section.id })}
                  title={isHidden ? '显示模块' : '隐藏模块'}
                  className="p-1 text-faint hover:text-sage transition cursor-pointer"
                >
                  {isHidden ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
                <button
                  onClick={() => {
                    if (sectionIdx === 0) return;
                    onReorderSection({ fromId: section.id, toId: resume.sections[sectionIdx - 1].id });
                  }}
                  disabled={sectionIdx === 0}
                  title="上移模块"
                  className="p-1 text-faint hover:text-sage transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronUp className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => {
                    if (sectionIdx >= resume.sections.length - 1) return;
                    onReorderSection({ fromId: section.id, toId: resume.sections[sectionIdx + 1].id });
                  }}
                  disabled={sectionIdx >= resume.sections.length - 1}
                  title="下移模块"
                  className="p-1 text-faint hover:text-sage transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="space-y-4">
              {section.items.map((item, itemIdx) => {
                const itemDragKey = `item:${item.id}`;
                const isRenaming = renamingItemId === item.id;
                return (
                  <div
                    key={item.id}
                    data-testid={`resume-item-${item.id}`}
                    onDragOver={allowDrop('item', item.id, section.id)}
                    onDrop={dropOn('item', item.id, section.id)}
                    className={`space-y-1.5 rounded-lg p-1 ${
                      dragOverKey === itemDragKey ? 'border-t-2 border-sage bg-sage-soft/20' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs group/item">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span
                          draggable
                          onDragStart={beginDrag('item', item.id, section.id)}
                          onDragEnd={endDrag}
                          title="拖动调整条目顺序"
                          className="text-faint hover:text-sage cursor-grab active:cursor-grabbing shrink-0"
                        >
                          <GripVertical className="w-3.5 h-3.5" />
                        </span>
                        {isRenaming ? (
                          <input
                            value={renameTemp}
                            onChange={(e) => setRenameTemp(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                void commitRename(section.id, item.id);
                              } else if (e.key === 'Escape') {
                                setRenamingItemId(null);
                              }
                            }}
                            onBlur={() => {
                              if (renamingItemId === item.id) void commitRename(section.id, item.id);
                            }}
                            autoFocus
                            className="w-full px-1.5 py-0.5 text-xs font-bold border border-sage rounded bg-white focus:outline-none text-ink"
                          />
                        ) : (
                          <span
                            onDoubleClick={() => beginRename(item.id, item.title)}
                            title="双击重命名条目"
                            className="font-bold text-ink truncate cursor-text"
                          >
                            {item.title}
                          </span>
                        )}
                        {item.period && (
                          <span className="text-faint font-mono text-[11px] shrink-0">{item.period}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover/item:opacity-100 transition">
                        <button
                          onClick={() => {
                            if (itemIdx === 0) return;
                            onReorderItem({
                              sectionId: section.id,
                              fromId: item.id,
                              toId: section.items[itemIdx - 1].id,
                            });
                          }}
                          disabled={itemIdx === 0}
                          title="上移条目"
                          className="p-1 text-faint hover:text-sage transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <ChevronUp className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (itemIdx >= section.items.length - 1) return;
                            onReorderItem({
                              sectionId: section.id,
                              fromId: item.id,
                              toId: section.items[itemIdx + 1].id,
                            });
                          }}
                          disabled={itemIdx >= section.items.length - 1}
                          title="下移条目"
                          className="p-1 text-faint hover:text-sage transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <ChevronDown className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() =>
                            onDeleteItem({ sectionId: section.id, itemId: item.id, itemTitle: item.title })
                          }
                          title="删除条目"
                          className="p-1 text-faint hover:text-error transition cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {item.subtitle && (
                      <div className="text-xs font-medium text-muted italic pl-5">{item.subtitle}</div>
                    )}

                    {/* Bullet points */}
                    <ul className="space-y-2 pt-1 pl-5">
                      {item.bullets.map((bullet) => {
                        const isEditing = editingBulletId === bullet.id;
                        const isSelected = selectedBulletId === bullet.id;

                        return (
                          <li
                            key={bullet.id}
                            onClick={() => onSelectBullet(bullet.id)}
                            onDoubleClick={() => startEditBullet({ bulletId: bullet.id, text: bullet.text })}
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
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setEditingBulletId(null);
                                    }}
                                    className="px-2 py-1 text-xs text-faint hover:bg-page rounded cursor-pointer"
                                  >
                                    取消
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      void saveBulletEdit(section.id, item.id, bullet.id);
                                    }}
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
                                      startEditBullet({ bulletId: bullet.id, text: bullet.text });
                                    }}
                                    className="p-1 text-faint hover:text-sage rounded transition cursor-pointer"
                                    title="直接编辑"
                                  >
                                    <Edit2 className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onDeleteBullet({ sectionId: section.id, itemId: item.id, bulletId: bullet.id });
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
                );
              })}
            </div>

            {/* 添加条目（T-M6-4） */}
            <div className="pt-1">
              {addingSectionId === section.id ? (
                <div className="flex items-center gap-2">
                  <input
                    value={addItemTemp}
                    onChange={(e) => setAddItemTemp(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (addItemTemp.trim()) void commitAdd(section.id);
                      } else if (e.key === 'Escape') {
                        setAddingSectionId(null);
                        setAddItemTemp('');
                      }
                    }}
                    placeholder="条目标题，如：字节跳动 · 产品经理 · 2023.06-2024.06"
                    autoFocus
                    className="flex-1 px-2 py-1 text-xs border border-sage rounded bg-white focus:outline-none text-ink"
                  />
                  <button
                    onClick={() => {
                      if (addItemTemp.trim()) void commitAdd(section.id);
                    }}
                    disabled={!addItemTemp.trim()}
                    title="确认添加"
                    className="p-1 text-sage hover:text-sage-dim disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      setAddingSectionId(null);
                      setAddItemTemp('');
                    }}
                    title="取消添加"
                    className="p-1 text-faint hover:text-error cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setAddItemTemp('');
                    setAddingSectionId(section.id);
                  }}
                  className="flex items-center gap-1 px-2 py-1 text-[11px] text-faint hover:text-sage hover:bg-page rounded transition cursor-pointer"
                  title="在该模块末尾添加条目"
                >
                  <Plus className="w-3.5 h-3.5" /> 添加条目
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
