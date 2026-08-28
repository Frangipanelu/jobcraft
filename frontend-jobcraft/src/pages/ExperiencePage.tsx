import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Collapse,
  Input,
  Modal,
  Tag,
  Form,
  message,
  Upload,
  Popconfirm,
  Space,
  Divider,
  Tooltip,
  Typography,
  Select,
  Spin,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  UploadOutlined,
  ThunderboltOutlined,
  TagsOutlined,
  FileTextOutlined,
  PartitionOutlined,
} from '@ant-design/icons'
import {
  backfillCards,
  createCard,
  deleteCard,
  listCards,
  updateCard,
  uploadResume,
  structureCard,
  recommendTags,
  type ExperienceCard,
} from '../api.ts'

const { Title } = Typography

interface CardFormState {
  title: string
  raw_text: string
  tags: string
  card_type: string
}

function makeFormState(card?: Partial<ExperienceCard>): CardFormState {
  return {
    title: card?.title ?? '',
    raw_text: card?.raw_text ?? '',
    tags: (card?.tags ?? []).join(', '),
    card_type: card?.card_type ?? 'work',
  }
}

function parseFormState(values: CardFormState): Partial<ExperienceCard> {
  const tags = values.tags
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean)
  return {
    title: values.title,
    raw_text: values.raw_text,
    tags,
    card_type: values.card_type,
  }
}

export default function ExperiencePage() {
  const [cards, setCards] = useState<ExperienceCard[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [backfilling, setBackfilling] = useState(false)
  const [structuring, setStructuring] = useState<Set<number>>(new Set())
  const [structuringElapsed, setStructuringElapsed] = useState(0)
  const [initialValues, setInitialValues] = useState<CardFormState | null>(null)
  const [detailCard, setDetailCard] = useState<ExperienceCard | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [form] = Form.useForm<CardFormState>()

  const load = async () => {
    try {
      const data = await listCards()
      setCards(data)
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (structuring.size === 0) { setStructuringElapsed(0); return }
    const t0 = Date.now()
    const id = setInterval(() => setStructuringElapsed(Math.floor((Date.now() - t0) / 1000)), 500)
    return () => clearInterval(id)
  }, [structuring.size])

  const groups = useMemo(() => {
    // 按公司分组：同一公司只展示一组，组内多个岗位（角色）并列；
    // 组内同公司+同岗位去重（兼容去重逻辑上线前导入的旧数据）
    const byCompany = new Map<string, ExperienceCard[]>()
    for (const card of cards) {
      const key = (card.company || '').trim() || '(未标注公司)'
      const list = byCompany.get(key) || []
      const dup = list.some(
        (x) =>
          (x.role || '').trim() === (card.role || '').trim() &&
          (card.role || '').trim() !== '',
      )
      if (dup) continue
      byCompany.set(key, [...list, card])
    }
    const entries: [string, string, ExperienceCard[]][] = []
    for (const [company, list] of byCompany) {
      const label = company === '(未标注公司)' ? '未标注公司' : company
      entries.push([company, `${label} · ${list.length} 个岗位`, list])
    }
    return entries
  }, [cards])

  const openCreate = () => {
    const init = makeFormState()
    setInitialValues(init)
    form.setFieldsValue(init)
    setModalOpen(true)
  }

  const handleSave = async (values: CardFormState) => {
    if (initialValues && JSON.stringify(values) === JSON.stringify(initialValues)) {
      message.info('未做任何修改')
      setModalOpen(false)
      return
    }
    const payload = parseFormState(values)
    try {
      await createCard(payload)
      message.success('经历卡已创建')
      setModalOpen(false)
      await load()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteCard(id)
      message.success('已删除')
      await load()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const cards = await uploadResume(file)
      message.success(`已导入 ${cards.length} 张经历卡`)
      await load()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const handleBackfill = async () => {
    setBackfilling(true)
    try {
      const res = await backfillCards()
      if (res.splits.length === 0) {
        message.info('未发现「单卡装下整份简历」的历史数据，无需拆分')
        return
      }
      const count = res.splits.reduce((n, s) => n + s.created_ids.length, 0)
      Modal.info({
        title: '拆分完成',
        content: (
          <div>
            <p>共拆分 {res.splits.length} 张旧卡，新建 {count} 张经历卡。</p>
            <p style={{ color: 'var(--jc-muted)' }}>
              原卡已归档（可在岗位分析中显示归档），每段经历独立成卡，便于后续匹配与润色。
            </p>
          </div>
        ),
      })
      await load()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setBackfilling(false)
    }
  }

  const openDetail = (card: ExperienceCard) => {
    setDetailCard(card)
    setDetailOpen(true)
  }

  const handleSaveDetail = async (payload: Partial<ExperienceCard>) => {
    if (!detailCard) return
    try {
      await updateCard(detailCard.id, payload)
      message.success('经历卡已更新')
      setDetailOpen(false)
      await load()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleStructure = async (cardId: number) => {
    setStructuring((prev) => new Set(prev).add(cardId))
    try {
      await structureCard(cardId)
      message.success('AI 结构化分析完成')
      await load()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setStructuring((prev) => {
        const next = new Set(prev)
        next.delete(cardId)
        return next
      })
    }
  }

  const handleRecommendTags = async (cardId: number) => {
    try {
      const recommended = await recommendTags(cardId)
      if (recommended.length === 0) {
        message.info('AI 暂无标签推荐')
        return
      }
      await updateCard(cardId, { tags: recommended })
      message.success(`已应用 ${recommended.length} 个推荐标签`)
      await load()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const renderSummary = (card: ExperienceCard) => {
    const cache = card.ai_structured as { summary?: string } | null
    const summary = cache?.summary || card.summary || ''
    if (!summary) return null
    return (
      <div className="jc-summary" style={{ marginTop: 8 }}>
        {summary}
      </div>
    )
  }

  return (
    <Spin spinning={loading}>
      <div>
      <div className="jc-page-header">
        <Title level={4} style={{ margin: 0 }}>经历卡片</Title>
        <Space wrap>
          <Button icon={<PartitionOutlined />} loading={backfilling} onClick={handleBackfill}>
            {backfilling ? '拆分中...' : '拆分历史整卡'}
          </Button>
          <Upload
            showUploadList={false}
            accept=".pdf,.docx,.md,.txt"
            beforeUpload={async (file) => {
              await handleUpload(file as File)
              return false
            }}
          >
            <Button icon={<UploadOutlined />} loading={uploading}>
              {uploading ? '导入中...' : '上传简历导入'}
            </Button>
          </Upload>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建经历
          </Button>
        </Space>
      </div>

      {groups.map(([gkey, label, list]) => (
        <Collapse key={gkey} className="jc-section" ghost defaultActiveKey={[gkey]}>
          <Collapse.Panel header={<b>{label}</b>} key={gkey}>
            <div className="jc-card-grid">
              {list.map((card) => (
                <div key={card.id} className="jc-card">
                  <div className="jc-card-header">
                    {card.company && <span className="jc-card-company">{card.company}</span>}
                    {card.role && <span className="jc-card-role">{card.role}</span>}
                    {card.period && <span className="jc-card-period">{card.period}</span>}
                  </div>
                  <div className="jc-card-title">
                    {card.title}
                    {card.card_type === 'project' && (
                      <Tag color="purple" style={{ marginLeft: 8 }}>项目</Tag>
                    )}
                    {card.card_type === 'intern' && (
                      <Tag color="blue" style={{ marginLeft: 8 }}>实习</Tag>
                    )}
                  </div>
                  {card.tags.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      {card.tags.map((tag) => (
                        <Tag key={tag} className="jc-tag">{tag}</Tag>
                      ))}
                    </div>
                  )}
                  {renderSummary(card)}
                  <Divider style={{ margin: '12px 0' }} />
                  <Space>
                    <Button size="small" icon={<FileTextOutlined />} onClick={() => openDetail(card)}>
                      详情
                    </Button>
                    <Tooltip title="AI 结构化分析（S/A/R）">
                      <Button
                        size="small"
                        icon={<ThunderboltOutlined />}
                        loading={structuring.has(card.id)}
                        onClick={() => handleStructure(card.id)}
                      >
                        {structuring.has(card.id) ? `AI 分析中（${structuringElapsed} 秒）` : 'AI 分析'}
                      </Button>
                    </Tooltip>
                    <Tooltip title="AI 推荐标签">
                      <Button
                        size="small"
                        icon={<TagsOutlined />}
                        onClick={() => handleRecommendTags(card.id)}
                      >
                        标签
                      </Button>
                    </Tooltip>
                    <Popconfirm title="确认删除？" onConfirm={() => handleDelete(card.id)}>
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                </div>
              ))}
            </div>
          </Collapse.Panel>
        </Collapse>
      ))}

      <Modal
        open={modalOpen}
        title="新建经历"
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        width={720}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="card_type"
            label="经历类型"
            initialValue="work"
            rules={[{ required: true, message: '请选择经历类型' }]}
          >
            <Select
              options={[
                { label: '工作经历', value: 'work' },
                { label: '实习经历', value: 'intern' },
                { label: '项目经历', value: 'project' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="例如：负责用户增长项目 DAU 5w→15w" />
          </Form.Item>
          <Form.Item
            name="raw_text"
            label="经历描述"
            rules={[{ required: true, message: '请描述你的经历' }]}
            extra="自由书写即可，不必拘泥于 STAR 格式。AI 后续会帮你结构化。"
          >
            <Input.TextArea rows={8} placeholder="写下这段经历的关键信息：项目背景、你的工作、困难、结果……" />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔，可空）">
            <Input placeholder="例如 用户增长, 数据分析, 项目管理" />
          </Form.Item>
        </Form>
      </Modal>

      <DetailModal
        card={detailCard}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        onSave={handleSaveDetail}
      />
    </div>
    </Spin>
  )
}

function DetailModal({ card, open, onClose, onSave }: {
  card: ExperienceCard | null
  open: boolean
  onClose: () => void
  onSave: (payload: Record<string, any>) => void
}) {
  const cache = card?.ai_structured as Record<string, any> | null | undefined
  const achievements = (cache?.achievements || []) as Record<string, any>[]
  const [summary, setSummary] = useState(cache?.summary || '')
  const [items, setItems] = useState<Record<string, any>[]>([])
  const [form] = Form.useForm<CardFormState>()

  useEffect(() => {
    setSummary(cache?.summary || '')
    setItems(achievements.map(a => ({ ...a, action: { ...(a.action || {}) } })))
    form.setFieldsValue(makeFormState(card ?? undefined))
  }, [card])

  const updateItem = (i: number, field: string, value: string) => {
    setItems(prev => {
      const next = [...prev]
      next[i] = { ...next[i], [field]: value }
      return next
    })
  }

  const updateAction = (i: number, field: string, value: string) => {
    setItems(prev => {
      const next = [...prev]
      next[i] = { ...next[i], action: { ...next[i].action, [field]: value } }
      return next
    })
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    const basic = parseFormState(values)
    onSave({
      ...basic,
      ai_structured: { summary, achievements: items },
    })
  }

  return (
    <Modal
      open={open}
      title={`经历详情 — ${card?.title || ''}`}
      onCancel={onClose}
      onOk={handleSave}
      width={800}
    >
      <div style={{ maxHeight: 560, overflowY: 'auto' }}>
        <Form form={form} layout="vertical" initialValues={makeFormState(card ?? undefined)}>
          <Form.Item
            name="card_type"
            label="经历类型"
            rules={[{ required: true, message: '请选择经历类型' }]}
          >
            <Select
              options={[
                { label: '工作经历', value: 'work' },
                { label: '实习经历', value: 'intern' },
                { label: '项目经历', value: 'project' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="例如：负责用户增长项目 DAU 5w→15w" />
          </Form.Item>
          <Form.Item
            name="raw_text"
            label="经历描述"
            extra="自由书写即可，不必拘泥于 STAR 格式。AI 后续会帮你结构化。"
          >
            <Input.TextArea rows={4} placeholder="写下这段经历的关键信息：项目背景、你的工作、困难、结果……" />
          </Form.Item>
          <Form.Item name="tags" label="标签（逗号分隔，可空）">
            <Input placeholder="例如 用户增长, 数据分析, 项目管理" />
          </Form.Item>
        </Form>
        <Divider style={{ margin: '8px 0 16px' }} />
        {!cache ? (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--jc-muted)' }}>
            暂无 AI 结构化数据，可先保存基础信息，再点击卡片上的「AI 分析」
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>摘要</div>
              <Input.TextArea rows={2} value={summary} onChange={e => setSummary(e.target.value)} />
            </div>
            {items.map((item, i) => (
              <Card key={i} size="small" title={`工作项 ${i + 1}`} style={{ marginBottom: 12 }}>
                <Form layout="vertical">
                  <Form.Item label="标题">
                    <Input value={item.title || ''} onChange={e => updateItem(i, 'title', e.target.value)} />
                  </Form.Item>
                  <Form.Item label="背景 (Situation)">
                    <Input.TextArea rows={2} value={item.situation || ''} onChange={e => updateItem(i, 'situation', e.target.value)} />
                  </Form.Item>
                  <Form.Item label="核心行动 (Action)">
                    <Input.TextArea rows={2} value={item.action?.main || ''} onChange={e => updateAction(i, 'main', e.target.value)} />
                  </Form.Item>
                  <Form.Item label="困难">
                    <Input.TextArea rows={2} value={item.action?.difficulty || ''} onChange={e => updateAction(i, 'difficulty', e.target.value)} />
                  </Form.Item>
                  <Form.Item label="解决方式">
                    <Input.TextArea rows={2} value={item.action?.resolution || ''} onChange={e => updateAction(i, 'resolution', e.target.value)} />
                  </Form.Item>
                  <Form.Item label="结果 (Result)">
                    <Input.TextArea rows={2} value={item.result || ''} onChange={e => updateItem(i, 'result', e.target.value)} />
                  </Form.Item>
                </Form>
              </Card>
            ))}
          </>
        )}
      </div>
    </Modal>
  )
}
