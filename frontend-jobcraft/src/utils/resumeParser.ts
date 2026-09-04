import type { ResumeVersion, ResumeSection, ResumeSectionItem, ResumeBullet } from '../types/jobcraft'

/**
 * 把后端生成的 resume_markdown 解析为前端 ResumeVersion。
 *
 * 镜像 app/tools/jobcraft_resume_gen.py 的 generate_resume_markdown 实际输出格式：
 * ```
 * # 张三
 * 电话：13812345678 | 邮箱：zhang@x.com        （可选）
 * 求职意向：前端架构师
 * 目标公司：字节跳动（可选）
 * 更新日期：2026-09-03（可选）
 *
 * ## 核心能力
 * Vue、TypeScript、性能优化（可选）
 *
 * ## 工作经历
 * ### 字节跳动 · 高级前端 · 2022.04-至今        ← 卡片条目（含 · 或公司头）
 * ### 核心页面性能优化                          ← 成就标题（同卡片下的 bullet 头）
 * **背景**：日活50万的前端项目
 * **行动**：主导重构与缓存策略
 * *标签：Vue、性能优化*（可选）
 * ```
 *
 * 映射规则：
 * - `# 姓名` → personalInfo.name
 * - 联系方式行 / 键值行 → personalInfo.phone/email/location/title、jobTitle、company、updatedAt
 * - `## 核心能力` 段 → summary（顿号分隔技能）
 * - `## 工作经历` 段 → sections[0]；每个含 `·` 或"公司头"的 `###` 开启一个 item（卡片）；
 *   随后的 `###`（无 `·`）与 `**标签**：` 行合并为一条 bullet（STAR 要点）
 *
 * 采用确定性规则、容忍怪异输入，不因异常内容崩溃。markdown 为空时返回 null（调用方走空态）。
 *
 * @param markdown 后端生成的简历 markdown（可为空）
 * @param fallback 无简历时的兜底信息（submission 的 position/company/id）
 * @returns 解析后的 ResumeVersion；markdown 为空 / 无不含经历时返回 null
 */
export function markdownToResume(
  markdown: string | null | undefined,
  fallback: { position: string; company: string; id: string },
): ResumeVersion | null {
  const text = (markdown || '').trim()
  if (!text) return null

  const lines = text.split(/\r?\n/)

  const personalInfo: ResumeVersion['personalInfo'] = {
    name: '',
    email: '',
    phone: '',
    title: '',
    location: '',
  }
  let summary = ''
  let jobTitle = fallback.position || ''
  let company = fallback.company || ''
  let updatedAt = ''
  let sawHeader = false
  const sections: ResumeSection[] = []

  let currentSection: ResumeSection | null = null
  let currentItem: ResumeSectionItem | null = null
  let currentBullet: ResumeBullet | null = null
  let idCounter = 0

  const nid = (prefix: string) => `${prefix}-${idCounter++}-${Date.now().toString(36)}`
  const ensureSection = (title: string): ResumeSection => {
    const sec = { id: nid('sec'), title, items: [] as ResumeSectionItem[] }
    sections.push(sec)
    return sec
  }
  const ensureBullet = (): ResumeBullet => {
    if (currentItem && currentBullet) return currentBullet
    const b: ResumeBullet = { id: nid('bullet'), text: '' }
    currentBullet = b
    if (currentItem) currentItem.bullets.push(b)
    return b
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue

    // 姓名标题
    if (line.startsWith('# ')) {
      personalInfo.name = line.slice(2).trim()
      sawHeader = true
      continue
    }
    // 二级/三级标题
    if (line.startsWith('## ')) {
      const title = line.slice(3).trim()
      if (title === '核心能力') {
        currentSection = ensureSection('核心能力')
      } else {
        currentSection = title === '工作经历' ? ensureSection('工作经历') : ensureSection(title)
      }
      currentItem = null
      currentBullet = null
      continue
    }
    if (line.startsWith('###')) {
      const title = line.replace(/^###\s*/, '').trim()
      if (!currentSection) currentSection = ensureSection('工作经历')
      // 含 · 的是公司条目头；否则是当前条目下的成就标题 -> 作为 bullet 头
      if (title.includes('·')) {
        currentItem = { id: nid('item'), title, bullets: [] }
        currentSection.items.push(currentItem)
        currentBullet = null
      } else if (currentItem) {
        const b: ResumeBullet = { id: nid('bullet'), text: title }
        currentItem.bullets.push(b)
        currentBullet = b
      }
      continue
    }

    // 标签行忽略（置于 key-value / STAR 前，避免误吞）
    if (line.startsWith('*标签')) continue

    // STAR 标注行（**背景**：… ）→ 追加到当前 bullet 文本
    if (line.startsWith('**')) {
      if (currentBullet) {
        currentBullet.text = currentBullet.text
          ? currentBullet.text + '\n' + line
          : line
      }
      continue
    }

    // 联系方式行（含手机/邮箱/城市），优先于单键值行，因为可能「电话|邮箱」同行
    const contact = parseContact(line, personalInfo)
    if (contact.matched) {
      personalInfo.email = contact.email ?? personalInfo.email ?? ''
      personalInfo.phone = contact.phone ?? personalInfo.phone ?? ''
      personalInfo.location = contact.location ?? personalInfo.location ?? ''
      continue
    }

    // 键值行（求职意向 / 目标公司 / 更新日期 / 电话 / 邮箱 / 城市 / 职位）
    const kv = parseKeyValue(line)
    if (kv) {
      if (kv.key === '求职意向') jobTitle = kv.value
      else if (kv.key === '目标公司') company = kv.value
      else if (kv.key === '更新日期') updatedAt = kv.value
      else if (kv.key === '联系电话' || kv.key === '电话') personalInfo.phone = kv.value
      else if (kv.key === '邮箱' || kv.key === 'email' || kv.key === 'Email') personalInfo.email = kv.value
      else if (kv.key === '所在城市' || kv.key === '城市') personalInfo.location = kv.value
      else if (kv.key === '职位' || kv.key === '岗位') personalInfo.title = kv.value
      continue
    }

    // 标签行忽略
    if (line.startsWith('*标签')) continue

    // 核心能力段：顿号/逗号分隔的技能 → summary
    if (currentSection && currentSection.title === '核心能力') {
      summary = line
      continue
    }

    // 其它普通文本行：归入当前 item 的 bullet；无 item 则忽略
    if (currentItem) {
      const b = ensureBullet()
      b.text = b.text ? b.text + '\n' + line : line
      continue
    }
    // 首表头之后的杂散文本且无 section —— 忽略，不造假
  }

  // 兜底：从未看到 `#` 表头，则用 fallback.position 作为名字（不把空 markdown 当真实简历）
  if (!sawHeader) {
    personalInfo.name = personalInfo.name || fallback.position || '我的简历'
  }

  // 无任何经历 section（既没有工作/教育 section）→ 视为无效，返回 null 走空态
  if (!sections.length) return null

  return {
    id: fallback.id,
    jobId: fallback.id,
    jobTitle,
    company,
    versionName: company ? `${company} · ${jobTitle}` : jobTitle || '我的简历',
    updatedAt: updatedAt || '刚刚',
    personalInfo,
    summary,
    aiSuggestions: [],
    sections,
  }
}

/**
 * 把前端编辑后的 ResumeVersion 反序列化为后端 resume_markdown 字符串，用于持久化。
 *
 * 输出格式与 app/tools/jobcraft_resume_gen.py::generate_resume_markdown 尽量兼容，
 * 使未来重新解析/后端消费不产生结构性错位：
 * ```
 * # 姓名
 * 电话：xxx | 邮箱：xxx          （有值才输出）
 * 求职意向：{jobTitle}
 * 目标公司：{company}             （有值才输出）
 * 更新日期：{当天日期}
 *
 * ## 核心能力
 * {summary}
 *
 * ## 工作经历
 * ### {item.title}              （卡片条目；每个 bullet 作为一个 `###` 子标题块）
 * ### {bullet 第一行}
 * {bullet 剩余行，每行原文}
 * ### {bullet 第一行}
 * {bullet 剩余行，每行原文}
 * ```
 *
 * 每个 bullet 用一个 `###` 子标题 + 后续原文行还原为一条要点（与解析器互为逆运算，
 * 保证「保存 → 重新解析」的 item/bullet 分组与内容近似不变）。
 *
 * @param resume 编辑后的 ResumeVersion
 * @returns 可落库的 markdown 字符串
 */
export function resumeToMarkdown(resume: ResumeVersion): string {
  const { personalInfo, jobTitle, company, summary } = resume
  const today = new Date().toISOString().slice(0, 10)
  const lines: string[] = []
  const push = (s?: string) => {
    if (s && s.trim()) lines.push(s)
  }
  const pushBlank = () => lines.push('')

  push(`# ${personalInfo.name || '我的简历'}`)
  const contactParts: string[] = []
  if (personalInfo.phone) contactParts.push(`电话：${personalInfo.phone}`)
  if (personalInfo.email) contactParts.push(`邮箱：${personalInfo.email}`)
  if (personalInfo.location) contactParts.push(`城市：${personalInfo.location}`)
  if (personalInfo.title) contactParts.push(`职位：${personalInfo.title}`)
  if (contactParts.length) push(contactParts.join(' | '))
  if (jobTitle) push(`求职意向：${jobTitle}`)
  if (company) push(`目标公司：${company}`)
  push(`更新日期：${today}`)
  pushBlank()

  if (summary && summary.trim()) {
    push('## 核心能力')
    push(summary)
    pushBlank()
  }

  const workSection = resume.sections.find((s) => s.title === '工作经历') || resume.sections[0]
  push(workSection ? `## ${workSection.title}` : '## 工作经历')
  pushBlank()
  const items = workSection?.items || []
  for (const item of items) {
    push(`### ${item.title}${item.period ? ` · ${item.period}` : ''}`)
    pushBlank()
    for (const bullet of item.bullets || []) {
      const parts = bullet.text.split(/\r?\n/)
      push(`### ${parts[0]}`)
      if (parts.length > 1) {
        for (const p of parts.slice(1)) {
          if (p && p.trim()) push(p)
        }
      }
      pushBlank()
    }
  }

  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n'
}

interface KeyValue { key: string; value: string }

function parseKeyValue(line: string): KeyValue | null {
  const colonIdx = line.indexOf('：')
  if (colonIdx <= 0) {
    const halfIdx = line.indexOf(':')
    if (halfIdx <= 0) return null
    const key = line.slice(0, halfIdx).trim()
    const value = line.slice(halfIdx + 1).trim()
    return key && value ? { key, value } : null
  }
  const key = line.slice(0, colonIdx).trim()
  const value = line.slice(colonIdx + 1).trim()
  return key && value ? { key, value } : null
}

const EMAIL_RE = /[\w.+-]+@[\w-]+\.[\w.]+/
const PHONE_RE = /1[3-9]\d{9}/

function parseContact(
  line: string,
  personalInfo: ResumeVersion['personalInfo'],
): { matched: boolean; email?: string; phone?: string; location?: string } {
  const emailMatch = line.match(EMAIL_RE)
  const phoneMatch = line.match(PHONE_RE)
  if (!emailMatch && !phoneMatch) return { matched: false }

  const email = emailMatch ? emailMatch[0] : personalInfo.email || undefined
  const phone = phoneMatch ? phoneMatch[0] : personalInfo.phone || undefined

  let rest = line
    .replace(email || '', ' ')
    .replace(phone || '', ' ')
  // 剩余的中文片段（去掉邮箱/手机后）作为 location
  const leftover = rest
    .split(/[·|/,，]/)
    .map((s) => s.trim())
    .filter((s) => Boolean(s) && !s.includes('：') && !s.includes(':'))
    .find((s) => /[\u4e00-\u9fa5]/.test(s))
  const location = leftover || personalInfo.location || undefined

  return { matched: true, email, phone, location }
}