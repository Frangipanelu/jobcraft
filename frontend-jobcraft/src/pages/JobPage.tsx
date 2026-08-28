import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  Divider,
  Form,
  Input,
  message,
  Modal,
  Progress,
  Space,
  Spin,
  Steps,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import {
  ArrowRightOutlined,
  DownloadOutlined,
  EditOutlined,
  FileTextOutlined,
  PrinterOutlined,
  RobotOutlined,
  SendOutlined,
  UserOutlined,
} from '@ant-design/icons'
import {
  listCards,
  saveCardVersion,
  saveResume,
  step1AtsRecommend,
  step2GapPolish,
  type ExperienceCard,
  type ResumePersonalInfo,
  type Step1AtsProfile,
} from '../api.ts'

const { Step } = Steps
const { TabPane } = Tabs
const { Text } = Typography

const LOCAL_WEIGHT = 0.4
const LLM_WEIGHT = 0.6

interface RecommendedCard {
  card_id: number
  score: number
  reason: string
}

interface SubtextDecode {
  surface_requirement: string
  hidden_meaning: string
  key_ability: string
  how_to_prove: string
}

interface CardDimensionScore {
  dimension: string
  score: number
  note: string
}

interface CardGapItem {
  card_id: number
  score: number
  local_score: number
  llm_score: number
  matched: string[]
  missing: string[]
  action: 'polish' | 'supplement' | 'good'
  rewrite_suggestion?: string
  supplement_suggestion?: string
  supplement_steps?: string[]
  dimension_analysis?: CardDimensionScore[]
  transferable_skills?: string[]
  domain_overlap?: string
  quantified_note?: string
}

interface GlobalSuggestion {
  missing_ability: string
  priority: string
  action: string
  steps: string[]
}

interface GapResult {
  per_card: CardGapItem[]
  global_suggestions: GlobalSuggestion[]
  overall_score: number
  match_level: string
}

export default function JobPage({ jobId }: { jobId?: string | null }) {
  const [form] = Form.useForm()
  const [initialLoading, setInitialLoading] = useState(!!jobId)
  const [step, setStep] = useState(jobId ? 1 : 0)
  const [jdText, setJdText] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [company, setCompany] = useState('')
  const [allCards, setAllCards] = useState<ExperienceCard[]>([])
  const [jobAnalysisId, setJobAnalysisId] = useState<number | null>(jobId ? Number(jobId) : null)
  const [ats, setAts] = useState<Step1AtsProfile | null>(null)
  const [recommendedCards, setRecommendedCards] = useState<RecommendedCard[]>([])
  const [selectedCardIds, setSelectedCardIds] = useState<number[]>([])
  const [analyzing, setAnalyzing] = useState(false)

  const [gapResult, setGapResult] = useState<GapResult | null>(null)
  const [editTexts, setEditTexts] = useState<Record<number, string>>({})
  const [saving, setSaving] = useState<Set<number>>(new Set())
  const [generating, setGenerating] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [resumeMd, setResumeMd] = useState<string | null>(null)
  const [resumeHtml, setResumeHtml] = useState<string | null>(null)
  const [personalInfo, setPersonalInfo] = useState<ResumePersonalInfo>({
    name: '',
    phone: '',
    email: '',
    city: '',
    github: '',
    education: '',
    years: '',
  })
  const [showPersonalForm, setShowPersonalForm] = useState(false)
  const resumeFrameRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem('jobcraft_personal_info')
      if (saved) setPersonalInfo(JSON.parse(saved))
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    listCards().then(setAllCards).catch((e) => message.error(e.message))
  }, [])

  useEffect(() => {
    if (!jobId) return
    fetch(`/api/jobcraft/job/analyze/${jobId}`)
      .then(r => r.json())
      .then(analysis => {
        setJdText(analysis.jd_text || '')
        setJobTitle(analysis.position || '')
        setCompany(analysis.company || '')
        setAts(analysis.jd_requirements || {})
        setSelectedCardIds([])
      })
      .catch(e => message.error(e.message))
      .finally(() => setInitialLoading(false))
  }, [jobId])

  const cardMap = useMemo(() => {
    const m = new Map<number, ExperienceCard>()
    for (const c of allCards) m.set(c.id, c)
    return m
  }, [allCards])

  const handleStep1 = async () => {
    if (!jobTitle.trim() || !jdText.trim()) {
      message.warning('请填写岗位名称和 JD 内容')
      return
    }
    if (!company.trim()) {
      message.warning('请输入公司名称')
      return
    }
    setAnalyzing(true)
    try {
      const res = await step1AtsRecommend({ position: jobTitle.trim(), company: company.trim(), jd_text: jdText.trim() })
      setJobAnalysisId(res.job_analysis_id)
      setAts(res.ats)
      setRecommendedCards(res.recommended_cards)
      setSelectedCardIds(res.recommended_cards.map((r) => r.card_id))
      setStep(1)
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleStep2 = async () => {
    if (!jobAnalysisId || selectedCardIds.length === 0) {
      message.warning('请至少选择 1 张经历卡')
      return
    }
    setAnalyzing(true)
    try {
      const res = await step2GapPolish({ job_analysis_id: jobAnalysisId, card_ids: selectedCardIds })
      setGapResult(res)
      // 初始化编辑框：有 rewrite_suggestion 的填入默认值
      const init: Record<number, string> = {}
      for (const item of res.per_card) {
        const card = cardMap.get(item.card_id)
        if (item.rewrite_suggestion) {
          init[item.card_id] = item.rewrite_suggestion
        } else if (card) {
          init[item.card_id] = card.raw_text || ''
        }
      }
      setEditTexts(init)
      setStep(2)
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSaveVersion = async (cardId: number) => {
    if (!jobAnalysisId) return
    setSaving((prev) => new Set(prev).add(cardId))
    try {
      await saveCardVersion({
        card_id: cardId,
        source_type: 'job_analysis',
        source_id: jobAnalysisId,
        raw_text: editTexts[cardId] || '',
      })
      message.success('已保存')
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setSaving((prev) => {
        const next = new Set(prev)
        next.delete(cardId)
        return next
      })
    }
  }

  const handleGenerateResume = async () => {
    if (!jobAnalysisId) return
    setGenerating(true)
    try {
      const res = await saveResume({
        job_analysis_id: jobAnalysisId,
        selected_card_ids: selectedCardIds,
        card_versions: editTexts,
        personal_info: personalInfo,
      })
      setResumeMd(res.resume_markdown || null)
      setResumeHtml(res.resume_html || null)
      message.success('简历已生成')
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setGenerating(false)
    }
  }

  const handlePrintPdf = () => {
    if (!resumeHtml) return
    const win = window.open('', '_blank')
    if (!win) {
      message.warning('请允许弹窗以导出 PDF')
      return
    }
    win.document.write(resumeHtml)
    win.document.close()
    win.focus()
    setTimeout(() => win.print(), 300)
  }

  const handleDownloadPdf = async () => {
    if (!resumeHtml) return
    setDownloadingPdf(true)
    // 创建离屏容器承载简历 HTML，避免污染当前页面样式
    const container = document.createElement('div')
    container.style.cssText =
      'position:fixed;left:-9999px;top:0;width:794px;background:#ffffff;z-index:-1;'
    container.innerHTML = resumeHtml
    document.body.appendChild(container)
    try {
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ])
      // 等待字体与图片加载完成再截图
      await new Promise((r) => setTimeout(r, 300))
      const canvas = await html2canvas(container, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#ffffff',
        windowWidth: 794,
      })
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
      const pageW = pdf.internal.pageSize.getWidth()
      const pageH = pdf.internal.pageSize.getHeight()
      const imgH = (canvas.height * pageW) / canvas.width
      let heightLeft = imgH
      let position = 0
      pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, position, pageW, imgH)
      heightLeft -= pageH
      while (heightLeft > 0) {
        position -= pageH
        pdf.addPage()
        pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, position, pageW, imgH)
        heightLeft -= pageH
      }
      const safeName = (s: string) => s.replace(/[\\/:*?"<>|]/g, '').trim() || 'resume'
      pdf.save(`${safeName(company)}-${safeName(jobTitle)}.pdf`)
      message.success('PDF 已下载')
    } catch (err) {
      message.error(`PDF 导出失败：${(err as Error).message}`)
    } finally {
      document.body.removeChild(container)
      setDownloadingPdf(false)
    }
  }

  const savePersonalInfo = (values: ResumePersonalInfo) => {
    const next = { ...personalInfo, ...values }
    setPersonalInfo(next)
    try {
      localStorage.setItem('jobcraft_personal_info', JSON.stringify(next))
    } catch { /* ignore */ }
    setShowPersonalForm(false)
    message.success('个人信息已保存')
  }

  return (
    <Spin spinning={initialLoading}>
      <div>
      <Steps current={step} style={{ marginBottom: 24, background: 'var(--jc-panel)', padding: 16, borderRadius: 8 }}>
        <Step title="输入 JD" icon={<FileTextOutlined />} />
        <Step title="选择卡片" icon={<RobotOutlined />} />
        <Step title="缺口分析" icon={<EditOutlined />} />
      </Steps>

      {/* Step 0: 输入 JD */}
      {step === 0 && (
        <div className="jc-section">
          <Form layout="vertical">
            <Form.Item label="岗位名称">
              <Input
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                placeholder="例如：高级产品经理"
              />
            </Form.Item>
            <Form.Item label="公司">
              <Input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="如：字节跳动"
              />
            </Form.Item>
            <Form.Item label="JD 文本">
              <Input.TextArea
                rows={10}
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="粘贴岗位 JD 文本..."
              />
            </Form.Item>
            <Button type="primary" icon={<SendOutlined />} loading={analyzing} onClick={handleStep1}>
              ATS 解析并推荐卡片
            </Button>
          </Form>
        </div>
      )}
      {step === 0 && jobId && (
        <div style={{ textAlign: 'center', padding: 24, color: 'var(--jc-muted)' }}>
          检测到已有分析记录（ID: {jobId}），可重新输入 JD 覆盖，或
          <Button type="link" onClick={() => setStep(1)}>直接进入卡片选择</Button>
        </div>
      )}

      {/* Step 1: 推荐卡片 */}
      {step === 1 && (
        <div>
          {ats && (
            <div className="jc-section" style={{ marginBottom: 16 }}>
              <h4>岗位画像</h4>
              <Space wrap>
                {ats.required_skills?.map((s: string) => <Tag key={s} color="blue">{s}</Tag>)}
                {ats.preferred_skills?.map((s: string) => <Tag key={s} color="green">{s}</Tag>)}
              </Space>
              {ats.responsibilities && (
                <ul style={{ marginTop: 8 }}>
                  {ats.responsibilities.slice(0, 5).map((r: string, i: number) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
              {ats.subtext_decoded && ats.subtext_decoded.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <h4 style={{ color: 'var(--jc-warn-text)' }}>暗话分析（JD 潜台词）</h4>
                  {ats.subtext_decoded.map((s: SubtextDecode, i: number) => (
                    <div key={i} style={{ background: 'var(--jc-warn-bg)', border: '1px solid var(--jc-line)', borderRadius: 8, padding: '12px 16px', marginBottom: 8 }}>
                      <Text strong>「{s.surface_requirement}」</Text>
                      <div style={{ color: 'var(--jc-warn-text)', marginTop: 4 }}>
                        → 实际期望：{s.hidden_meaning}
                      </div>
                      <div style={{ marginTop: 4 }}>
                        <Text type="secondary">关键能力：</Text>
                        <Tag color="volcano">{s.key_ability}</Tag>
                      </div>
                      <div style={{ marginTop: 4, color: 'var(--jc-muted)' }}>如何证明：{s.how_to_prove}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="jc-section">
            <h4>选择要分析的经历卡片</h4>
            <Checkbox.Group
              value={selectedCardIds}
              onChange={(v) => setSelectedCardIds(v as number[])}
              style={{ width: '100%' }}
            >
              {(recommendedCards.length > 0 ? recommendedCards : allCards.map(c => ({ card_id: c.id, score: 0, reason: '' }))).map((rc) => {
                const card = cardMap.get(rc.card_id)
                return (
                  <Card key={rc.card_id} size="small" style={{ marginBottom: 8 }}>
                    <Checkbox value={rc.card_id}>
                      <Text strong>{card?.title || `卡片 #${rc.card_id}`}</Text>
                      {rc.score > 0 && (
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                          匹配度 {rc.score}%
                        </Text>
                      )}
                      {rc.reason && <><br /><Text type="secondary">{rc.reason}</Text></>}
                      <div style={{ marginTop: 4 }}>
                        {(card?.tags || []).map((t) => <Tag key={t}>{t}</Tag>)}
                      </div>
                    </Checkbox>
                  </Card>
                )
              })}
            </Checkbox.Group>
            <Divider />
            <Button type="primary" icon={<ArrowRightOutlined />} loading={analyzing} onClick={handleStep2}>
              缺口分析
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: 缺口分析 + 编辑 + 简历 */}
      {step === 2 && gapResult && (
        <div>
          <Tabs defaultActiveKey="gap">
            <TabPane tab="缺口与修改" key="gap">
              {gapResult.overall_score !== undefined && (
                <div style={{ background: 'var(--jc-info-bg)', border: '1px solid var(--jc-line)', borderRadius: 12, padding: 16, marginBottom: 16 }}>
                  <Space align="center">
                    <Progress
                      type="dashboard"
                      percent={gapResult.overall_score}
                      size={96}
                      strokeColor={gapResult.overall_score >= 80 ? 'var(--jc-success)' : gapResult.overall_score >= 60 ? 'var(--jc-warn)' : 'var(--jc-danger)'}
                    />
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 600 }}>
                        整体匹配度：{gapResult.overall_score} 分
                        <Tag color={gapResult.overall_score >= 80 ? 'success' : gapResult.overall_score >= 60 ? 'warning' : 'error'} style={{ marginLeft: 8 }}>
                          {gapResult.match_level}
                        </Tag>
                      </div>
                      <div style={{ color: 'var(--jc-muted)', marginTop: 4 }}>
                        评分构成：本地关键词命中 {Math.round(LOCAL_WEIGHT * 100)}% + LLM 语义匹配 {Math.round(LLM_WEIGHT * 100)}%，按所选卡片融合分取平均
                      </div>
                    </div>
                  </Space>
                </div>
              )}
              {gapResult.per_card.map((item) => {
                const card = cardMap.get(item.card_id)
                if (!card) return null
                const actionLabel = item.action === 'polish' ? '润色' : item.action === 'supplement' ? '补充' : '良好'
                const actionColor = item.action === 'polish' ? 'orange' : item.action === 'supplement' ? 'red' : 'green'
                return (
                  <Card
                    key={item.card_id}
                    size="small"
                    title={
                      <Space>
                        <Text strong>{card.title}</Text>
                        <Tag color={actionColor}>{actionLabel}</Tag>
                        <Progress
                          type="circle"
                          percent={item.score}
                          size={24}
                          strokeColor={item.score >= 80 ? 'var(--jc-success)' : item.score >= 60 ? 'var(--jc-warn)' : 'var(--jc-danger)'}
                        />
                      </Space>
                    }
                    style={{ marginBottom: 12 }}
                  >
                    <Space wrap style={{ marginBottom: 8 }}>
                      {item.matched.map((m) => <Tag key={m} color="success">{m}</Tag>)}
                      {item.missing.map((m) => <Tag key={m} color="error">{m}</Tag>)}
                    </Space>
                    <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--jc-soft)' }}>
                      评分对比：
                      <Tag style={{ marginRight: 4 }}>本地关键词 {item.local_score ?? 0} 分</Tag>
                      <Tag color="blue" style={{ marginRight: 4 }}>LLM 语义 {item.llm_score ?? 0} 分</Tag>
                      <Tag color="geekblue">融合 {item.score} 分</Tag>
                    </div>
                    {((item.dimension_analysis && item.dimension_analysis.length > 0) ||
                      (item.transferable_skills && item.transferable_skills.length > 0) ||
                      item.domain_overlap ||
                      item.quantified_note) && (
                      <div style={{ background: 'var(--jc-success-bg)', border: '1px solid var(--jc-line)', padding: '8px 12px', borderRadius: 6, marginBottom: 8 }}>
                        <Text type="secondary" strong>多维评估</Text>
                        {item.dimension_analysis && item.dimension_analysis.length > 0 && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                            {item.dimension_analysis.map((d, i) => (
                              <div key={i} title={d.note}>
                                <Tag
                                    color={d.score >= 80 ? 'green' : d.score >= 60 ? 'orange' : 'red'}
                                  style={{ cursor: 'help' }}
                                >
                                  {d.dimension} {d.score} 分
                                </Tag>
                              </div>
                            ))}
                          </div>
                        )}
                        {item.transferable_skills && item.transferable_skills.length > 0 && (
                          <div style={{ marginTop: 4 }}>
                            <Text type="secondary">可迁移能力：</Text>
                            {item.transferable_skills.map((s, i) => <Tag key={i} color="geekblue">{s}</Tag>)}
                          </div>
                        )}
                        {item.domain_overlap && (
                          <div style={{ marginTop: 4 }}><Text type="secondary">领域契合度：</Text>{item.domain_overlap}</div>
                        )}
                        {item.quantified_note && (
                          <div style={{ marginTop: 4 }}><Text type="secondary">量化对标：</Text>{item.quantified_note}</div>
                        )}
                      </div>
                    )}
                    {item.rewrite_suggestion && (
                      <div style={{ background: 'var(--jc-warn-bg)', border: '1px solid var(--jc-line)', padding: '8px 12px', borderRadius: 6, marginBottom: 8 }}>
                        <Text type="secondary">改写建议：</Text>
                        <div style={{ whiteSpace: 'pre-wrap' }}>{item.rewrite_suggestion}</div>
                      </div>
                    )}
                    {item.supplement_suggestion && (
                      <div style={{ background: 'var(--jc-danger-bg)', border: '1px solid var(--jc-line)', padding: '8px 12px', borderRadius: 6, marginBottom: 8 }}>
                        <Text type="danger">补充建议：</Text>
                        <div>{item.supplement_suggestion}</div>
                        {item.supplement_steps && (
                          <ol style={{ margin: '4px 0 0 16px' }}>
                            {item.supplement_steps.map((s, i) => <li key={i}>{s}</li>)}
                          </ol>
                        )}
                      </div>
                    )}
                    <Input.TextArea
                      rows={5}
                      value={editTexts[item.card_id] || ''}
                      onChange={(e) => setEditTexts((prev) => ({ ...prev, [item.card_id]: e.target.value }))}
                      placeholder="编辑经历文本..."
                    />
                    <div style={{ marginTop: 8 }}>
                      <Button
                        size="small"
                        type="primary"
                        loading={saving.has(item.card_id)}
                        onClick={() => handleSaveVersion(item.card_id)}
                      >
                        保存版本
                      </Button>
                    </div>
                  </Card>
                )
              })}
              {gapResult.global_suggestions.length > 0 && (
                <div className="jc-section">
                  <h4>全局补充建议</h4>
                  {gapResult.global_suggestions.map((g, i) => (
                    <Card key={i} size="small" style={{ marginBottom: 8 }}>
                      <Space>
                        <Tag color={g.priority === 'high' ? 'red' : g.priority === 'medium' ? 'orange' : 'green'}>
                          {g.priority}
                        </Tag>
                        <Text strong>{g.missing_ability}</Text>
                      </Space>
                      <p>{g.action}</p>
                      {g.steps.length > 0 && (
                        <ol>
                          {g.steps.map((s, j) => <li key={j}>{s}</li>)}
                        </ol>
                      )}
                    </Card>
                  ))}
                </div>
              )}
              <Divider />
              <Button type="primary" icon={<DownloadOutlined />} loading={generating} onClick={handleGenerateResume}>
                生成简历
              </Button>
            </TabPane>
            <TabPane tab="简历预览" key="resume">
              <Space style={{ marginBottom: 16 }} wrap>
                <Button type="primary" icon={<DownloadOutlined />} loading={generating} onClick={handleGenerateResume}>
                  {resumeMd ? '重新生成' : '生成简历'}
                </Button>
                <Button icon={<UserOutlined />} onClick={() => { form.setFieldsValue(personalInfo); setShowPersonalForm(true) }}>
                  {personalInfo.name ? `个人信息：${personalInfo.name}` : '补充个人信息'}
                </Button>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  loading={downloadingPdf}
                  disabled={!resumeHtml}
                  onClick={handleDownloadPdf}
                >
                  一键下载 PDF
                </Button>
                <Button
                  type="primary"
                  ghost
                  icon={<PrinterOutlined />}
                  disabled={!resumeHtml}
                  onClick={handlePrintPdf}
                >
                  打印
                </Button>
              </Space>
              {resumeHtml ? (
                <iframe
                  ref={resumeFrameRef}
                  title="简历预览"
                  className="jc-iframe"
                  srcDoc={resumeHtml}
                />
              ) : resumeMd ? (
                <div className="jc-resume-preview">{resumeMd}</div>
              ) : null}
            </TabPane>
          </Tabs>
        </div>
      )}

      <Modal
        title="补充个人信息（用于简历头部）"
        open={showPersonalForm}
        onCancel={() => setShowPersonalForm(false)}
        onOk={() => form.submit()}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={savePersonalInfo}
        >
          <Form.Item label="姓名" name="name"><Input placeholder="张三" /></Form.Item>
          <Form.Item label="电话" name="phone"><Input placeholder="13800000000" /></Form.Item>
          <Form.Item label="邮箱" name="email"><Input placeholder="you@example.com" /></Form.Item>
          <Form.Item label="城市" name="city"><Input placeholder="北京" /></Form.Item>
          <Form.Item label="学历" name="education"><Input placeholder="本科 · 计算机科学" /></Form.Item>
          <Form.Item label="工作年限" name="years"><Input placeholder="5 年" /></Form.Item>
          <Form.Item label="GitHub / 作品链接" name="github"><Input placeholder="https://github.com/xxx" /></Form.Item>
        </Form>
      </Modal>
    </div>
    </Spin>
  )
}
