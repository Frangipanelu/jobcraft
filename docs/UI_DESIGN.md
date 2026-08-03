# UI Design — JobCraft 求职助手

> 本文件是前端视觉系统的**唯一事实来源**（source of truth）。修改任何样式前先读本文件；
> 颜色/字体必须引用 `src/index.css` 的 `--jc-*` token，禁止在组件内硬编码裸色值。
> 相关规范：`AGENTS.md` §3.2（TypeScript/React）、`docs/CODE_REVIEW.md`。

---

## 1. 设计定位

| 项 | 取值 |
|----|------|
| 风格名 | **极简编辑**（Editorial Minimal） |
| 一句话 | 暖米白纸面 + 单祖母绿点缀 + 灰阶文字 + hairline 细线 + 衬线标题，像一本排版克制的杂志 |
| 适用场景 | 求职者日常使用的内部工具（非营销页） |
| 情绪 | 冷静、可信、专注——帮助用户把注意力放在"经历/JD 内容"上，而非 UI 本身 |

对比基调（anti-slop 立场，见 hallmark audit）：
- **不做** 渐变标题、玻璃拟态、霓虹点缀、3 等分图标卡、居中大 hero。
- **不做** 每页各自为政的配色——全站共享一套 token。

---

## 2. 设计令牌（Design Tokens）

唯一入口：`frontend-jobcraft/src/index.css` 的 `:root`。组件内引用 `var(--jc-*)`，**禁止内联裸色值**（RFC：hallmark audit C1）。

### 2.1 颜色

| Token | 值 | 用途 |
|-------|-----|------|
| `--jc-bg` | `#faf9f6` | 页面底（暖米白） |
| `--jc-bg-2` | `#f1efe9` | 次级底 |
| `--jc-panel` | `#fefefc` | 卡片/面板面（偏白） |
| `--jc-panel-2` | `#f6f4ef` | 简历预览等次级面板 |
| `--jc-line` | `#e9e6de` | hairline 边框 |
| `--jc-ink` | `#1c1b18` | 主文字（墨色） |
| `--jc-soft` | `#4a4842` | 次级文字 |
| `--jc-muted` | `#6f6c63` | 辅助文字（≥12px 用；对比度约 4.5:1） |
| `--jc-accent` | `#0f6b52` | 品牌祖母绿（唯一强调色） |
| `--jc-accent-deep` | `#0a5440` | 强调色深阶（hover/选中文字） |
| `--jc-accent-soft` | `#e7efe8` | 强调色浅底（菜单选中/高亮块） |
| `--jc-danger` | `#a34436` | 危险/错误文字 |
| `--jc-danger-soft` | `#f5e7e2` | 危险浅底 |
| `--jc-shadow` | `0 1px 2px rgba(30,30,25,.04), 0 10px 30px -24px rgba(30,30,25,.28)` | 卡片投影（克制的两层） |

**语义状态色**（用于 Tag / Progress / 状态条，仍走 token，不直接写 AntD 默认 `#52c41a` 等）：

| 状态 | token 建议 | 说明 |
|------|-----------|------|
| success | 复用 `--jc-accent` 系 或 `--jc-success:#3d8f5c` | 完成/达标 |
| warning | `--jc-warn:#c07a2b` | 待改进 |
| error/danger | `--jc-danger:#a34436` | 缺失/失败 |

> 注意：AntD Tag 的 `color="green"/"orange"` 预置色仍可使用，但涉及**大块背景/文字**的自定义色必须走 token。

### 2.2 字体

| 角色 | 字体栈 | 说明 |
|------|--------|------|
| 标题 `--jc-serif` | `"Fraunces", "Songti SC", "STSong", Georgia, serif` | 衬线标题；中文字符回退到宋体类 |
| 正文 `--jc-sans` | `"PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif` | 全站正文/组件 |

- Fraunces 通过 Google Fonts `@import` 加载（CSS 顶部），离线时优雅回退到 Georgia/Songti。
- **标题一律不倾斜**（anti-slop：禁 italic 标题），强调用字重或 accent 色。
- 2+1 纪律：全站最多 3 个字体族；当前仅 serif + sans 两个，mono（`ui-monospace`）仅用于简历原文预览。

### 2.3 圆角与间距

- 圆角：卡片/面板 `12px`（`--jc-radius`）；表单控件/按钮 8px（AntD token `borderRadius:8`）；内嵌小块 4-6px。
- 间距：页面留白 `40px`（`.jc-page` 边距）；卡内距 `22px`；卡片网格 gap `18px`。
- 对齐尺度：页面容器左右边距 40px，卡片间距 18px，内容块间距 20px（`.jc-section` margin-bottom）。

---

## 3. 布局结构

```
┌── Sider(200px) ──┬──────────── Content ────────────┐
│  J 品牌区        │  Header（hairline 底）          │
│  导航菜单        │  ┌─ .jc-page ────────────────┐ │
│  (flex:1)        │  │  40px 边距               │ │
│                  │  │  .jc-card-grid / section │ │
└──────────────────┴──┴──────────────────────────┘─┘
```

- **Sider**：`--jc-bg` 底色 + 右侧 hairline；品牌区 36px accent 方块 "J" + 衬线字标。
- **Header**：半透明白 `rgba(250,249,246,.85)` + `backdrop-filter: blur(10px)`，与页面底同色系，不抢视觉。
- **页面**：`.jc-page` 40px 边距；内容块一律 `.jc-section`（白面板 + hairline + 12px 圆角）。
- **卡片网格**：`.jc-card-grid` `repeat(auto-fill, minmax(min(320px,100%),1fr))`，小屏自动收窄不溢出。

---

## 4. 组件风格约定

| 组件 | 约定 |
|------|------|
| 主按钮 | `type="primary"`，accent 底；次要操作 `default`；危险 `danger` |
| 卡片 | `.jc-card` / `.jc-section`：hairline 边框 + 微投影，hover 仅 `translateY(-2px)`（reduced-motion 时禁用） |
| 标签 | AntD `Tag`，用预置色或语义 token |
| 提示条 | 不嵌套 `Card`（M4），改用带 `background` 的 div 块（如 `--jc-accent-soft` / `--jc-warn` 底） |
| 状态行 | CareerRoute 的 5 个动作按钮固定 90×56，图标上文字下；小屏需 `flex-wrap` |
| 可点击文字 | 一律用 `Button`/`a` 而非 `span onClick`（M5，键盘可达 + focus-visible） |
| 图标 | 只用 `@ant-design/icons`，**禁用 emoji 当图标**（M3） |

---

## 5. 响应式

| 视口 | 行为 |
|------|------|
| 320–768px | `html,body{overflow-x:clip}` 防横向滚动；卡片网格单列；动作按钮自动换行 |
| ≥768px | 卡片网格多列；两栏布局（如 InterviewReview 主区+侧栏） |

硬性要求（hallmark audit C2 修复后）：
- 320px 视口无横向滚动（grid 用 `minmax(min(320px,100%),1fr)`）。
- 点击类文本不折两行（按钮用 `white-space:nowrap` 或允许换行容器）。

---

## 6. 无障碍

- 所有可点击元素必须是真实 `<button>`/`<a>`，具备 `:focus-visible` 焦点环。
- 正文与背景对比度 ≥ 4.5:1；`--jc-muted` 已校准（11-12px 辅助文字可用，更小文字再加深）。
- 动效遵循 `prefers-reduced-motion: reduce` 降级。

---

## 7. 历史与版本

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-07 | v0.8 | 引入 `--jc-*` 设计系统，ConfigProvider token 对齐 |
| 2026-08-03 | v0.9 | **hallmark audit 落地**：C1 token 化、C2 响应式、M1 Fraunces、M3 图标、M4 去嵌套卡、M5 可点击语义化；本文件建立 |

审计档案见会话记录与 `docs/harness/`。
