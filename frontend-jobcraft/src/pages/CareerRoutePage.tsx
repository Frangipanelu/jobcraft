import { useCallback, useEffect, useState } from 'react'
import {
  AimOutlined,
  AudioOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FormOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Empty,
  Input,
  message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from 'antd'
import {
  createManualSubmission,
  getDashboard,
  step1AtsRecommend,
  updateSubmission,
  type DashboardItem,
} from '../api.ts'
import { navigate } from '../useRoute.ts'

const { Text, Title } = Typography
const { Option } = Select
const { TextArea } = Input

const STATUS_OPTIONS = [
  '已投递',
  '面试邀约',
  '一面',
  '二面',
  'Offer',
  '已关闭',
]

type BtnState = 'todo' | 'done' | 'locked' | 'ready'

interface BtnConfig {
  key: string
  label: string
  icon: React.ReactNode
  state: BtnState
  tooltip: string
  onClick?: () => void
}

export default function CareerRoutePage() {
  const [items, setItems] = useState<DashboardItem[]>([])
  const [loading, setLoading] = useState(true)

  // 手动补录弹窗
  const [showUpload, setShowUpload] = useState(false)
  const [upPosition, setUpPosition] = useState('')
  const [upCompany, setUpCompany] = useState('')
  const [upFile, setUpFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  // 粘贴 JD 弹窗
  const [showJd, setShowJd] = useState(false)
  const [jdTargetId, setJdTargetId] = useState<number | null>(null)
  const [jdText, setJdText] = useState('')
  const [jdAnalyzing, setJdAnalyzing] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getDashboard()
      setItems(data.submissions)
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleStatusChange = async (id: number, status: string) => {
    try {
      await updateSubmission(id, { status })
      loadData()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await fetch(`/api/jobcraft/submission/${id}`, { method: 'DELETE' })
      message.success('已删除')
      loadData()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  // 上传已投简历
  const handleUpload = async () => {
    if (!upPosition.trim()) {
      message.warning('请输入岗位名称')
      return
    }
    if (!upFile) {
      message.warning('请选择要上传的简历文件')
      return
    }
    setUploading(true)
    try {
      await createManualSubmission(upFile, { position: upPosition.trim(), company: upCompany.trim() })
      message.success('简历已上传，投递记录已创建')
      setShowUpload(false)
      setUpPosition('')
      setUpCompany('')
      setUpFile(null)
      loadData()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  // 粘贴 JD 分析
  const handlePasteJd = async () => {
    if (!jdText.trim()) {
      message.warning('请粘贴 JD 文本')
      return
    }
    if (!jdTargetId) return
    setJdAnalyzing(true)
    try {
      const item = items.find((i) => i.id === jdTargetId)
      const data = await step1AtsRecommend({
        position: item?.position || '',
        company: item?.company || '',
        jd_text: jdText.trim(),
      })
      await updateSubmission(jdTargetId, { job_analysis_id: data.job_analysis_id })
      message.success('JD 分析完成')
      setShowJd(false)
      setJdText('')
      setJdTargetId(null)
      loadData()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setJdAnalyzing(false)
    }
  }

  const buildButtons = (item: DashboardItem): BtnConfig[] => {
    const status = item.status
    const isManual = item.is_manual
    const hasResume = item.has_resume
    const hasAnalysis = item.has_analysis
    const prepEnabled = status !== '已投递'
    const reviewEnabled = status !== '已投递'

    // 📄 简历
    const resumeBtn: BtnConfig = {
      key: 'resume',
      label: isManual && !hasResume ? '上传已投简历' : '查看简历',
      icon: <FileTextOutlined />,
      state: hasResume ? 'done' : 'todo',
      tooltip: hasResume ? '查看简历' : '上传已投递的简历文件',
      onClick: () => {
        if (!hasResume) {
          setUpCompany(item.company)
          setUpPosition(item.position)
          setShowUpload(true)
        }
      },
    }

    // 🔍 JD分析
    const jdBtn: BtnConfig = {
      key: 'jd',
      label: isManual && !hasAnalysis ? '粘贴 JD' : '查看分析',
      icon: <AimOutlined />,
      state: hasAnalysis ? 'done' : !hasResume ? 'locked' : 'todo',
      tooltip: hasAnalysis
        ? '查看 JD 分析'
        : !hasResume
          ? '请先上传简历'
          : '粘贴 JD 文本进行分析',
      onClick: () => {
        if (!hasAnalysis && hasResume) {
          setJdTargetId(item.id)
          setShowJd(true)
        }
      },
    }

    // 📝 润色卡片
    const polishBtn: BtnConfig = {
      key: 'polish',
      label: isManual ? `已自动抽取${item.card_count}张` : `已润色${item.card_version_count}张`,
      icon: <FileTextOutlined />,
      state: 'done',
      tooltip: isManual
        ? '上传简历时已自动抽取经历卡'
        : `该 JD 已润色 ${item.card_version_count} 张经历卡`,
    }

    // 🎤 面试准备
    const prepBtn: BtnConfig = {
      key: 'prep',
      label: '面试准备',
      icon: <AudioOutlined />,
      state: prepEnabled ? (item.prep_count > 0 ? 'done' : 'ready') : 'locked',
      tooltip: prepEnabled
        ? item.prep_count > 0
          ? `已生成 ${item.prep_count} 份`
          : '生成面试准备稿'
        : '需状态≥面试邀约',
      onClick: () => {
        if (prepEnabled) {
          navigate('prep' as any, { submissionId: String(item.id) })
        }
      },
    }

    // 📝 复盘
    const reviewBtn: BtnConfig = {
      key: 'review',
      label: '复盘',
      icon: <FormOutlined />,
      state: reviewEnabled ? (item.review_count > 0 ? 'done' : 'ready') : 'locked',
      tooltip: reviewEnabled
        ? item.review_count > 0
          ? `已复盘 ${item.review_count} 次`
          : '面试后复盘'
        : '需状态≥一面',
      onClick: () => {
        if (reviewEnabled) {
          navigate('review' as any, { submissionId: String(item.id) })
        }
      },
    }

    return [resumeBtn, jdBtn, polishBtn, prepBtn, reviewBtn]
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>我的求职路线</Title>
        <Button icon={<UploadOutlined />} onClick={() => setShowUpload(true)}>
          上传已投简历
        </Button>
      </div>

      {items.length === 0 ? (
        <Empty
          description="还没有投递记录，点击右上角上传已投简历开始"
          style={{ padding: 60 }}
        />
      ) : (
        items.map((item) => {
          const btns = buildButtons(item)
          const statusColor =
            item.status === 'Offer'
              ? 'success'
              : item.status === '已关闭'
                ? 'error'
                : item.status === '已投递'
                  ? 'default'
                  : 'processing'

          return (
            <Card key={item.id} style={{ marginBottom: 16 }} bodyStyle={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <Space size={16}>
                  <div>
                    <Text strong style={{ fontSize: 16 }}>{item.position}</Text>
                    {item.company && (
                      <>
                        <Text type="secondary" style={{ margin: '0 8px' }}>·</Text>
                        <Text>{item.company}</Text>
                      </>
                    )}
                    {item.is_manual && (
                      <Tag style={{ marginLeft: 8 }}>手动</Tag>
                    )}
                  </div>
                  <Select
                    value={item.status}
                    onChange={(v) => handleStatusChange(item.id, v)}
                    style={{ width: 130 }}
                    size="small"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <Option key={s} value={s}>{s}</Option>
                    ))}
                  </Select>
                  <Tag color={statusColor}>{item.status}</Tag>
                </Space>
                <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              </div>

              <div style={{ color: 'var(--jc-muted)', fontSize: 12, marginBottom: 12 }}>
                {item.created_at && <>创建 {new Date(item.created_at).toLocaleDateString('zh-CN')}</>}
              </div>

              <Space size={8} wrap>
                {btns.map((btn) => {
                  const btnStyle: React.CSSProperties = {
                    width: 90,
                    height: 56,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    borderRadius: 6,
                    border: '1px solid var(--jc-line)',
                  }

                  if (btn.state === 'locked') {
                    return (
                      <Tooltip key={btn.key} title={btn.tooltip}>
                        <Button style={{ ...btnStyle, opacity: 0.35, cursor: 'not-allowed' }} disabled>
                          {btn.icon}{'\n'}{btn.label}
                        </Button>
                      </Tooltip>
                    )
                  }

                  if (btn.state === 'todo') {
                    return (
                      <Tooltip key={btn.key} title={btn.tooltip}>
                        <Button
                          type="primary"
                          style={{ ...btnStyle, border: 'none' }}
                          onClick={btn.onClick}
                        >
                          {btn.icon}{'\n'}{btn.label}
                        </Button>
                      </Tooltip>
                    )
                  }

                  if (btn.state === 'done') {
                    return (
                      <Tooltip key={btn.key} title={btn.tooltip}>
                        <Button
                          style={{ ...btnStyle, borderColor: 'var(--jc-success)', color: 'var(--jc-success)' }}
                          onClick={btn.onClick}
                        >
                          {btn.icon}{'\n'}{btn.label}
                        </Button>
                      </Tooltip>
                    )
                  }

                  // ready
                  return (
                    <Tooltip key={btn.key} title={btn.tooltip}>
                      <Button style={btnStyle} onClick={btn.onClick}>
                        {btn.icon}{'\n'}{btn.label}
                      </Button>
                    </Tooltip>
                  )
                })}
              </Space>
            </Card>
          )
        })
      )}

      {/* 上传简历弹窗 */}
      <Modal
        title="上传已投简历"
        open={showUpload}
        onOk={handleUpload}
        onCancel={() => { setShowUpload(false); setUpPosition(''); setUpCompany(''); setUpFile(null) }}
        confirmLoading={uploading}
        okText="上传并创建投递"
        width={520}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input
            placeholder="岗位名称 *"
            value={upPosition}
            onChange={(e) => setUpPosition(e.target.value)}
          />
          <Input
            placeholder="公司（可选）"
            value={upCompany}
            onChange={(e) => setUpCompany(e.target.value)}
          />
          <Upload.Dragger
            accept=".pdf,.docx,.md,.txt"
            maxCount={1}
            showUploadList={false}
            beforeUpload={(file) => { setUpFile(file); return false }}
          >
            <p style={{ margin: 0 }}>
              <UploadOutlined style={{ fontSize: 24, color: 'var(--jc-accent)' }} />
            </p>
            <p>点击或拖拽简历文件到此处</p>
            <p style={{ fontSize: 12, color: 'var(--jc-muted)' }}>支持 PDF / DOCX / MD / TXT</p>
            {upFile && <p style={{ color: 'var(--jc-success)', marginTop: 8 }}>{upFile.name}</p>}
          </Upload.Dragger>
        </Space>
      </Modal>

      {/* 粘贴 JD 弹窗 */}
      <Modal
        title="JD 分析"
        open={showJd}
        onOk={handlePasteJd}
        onCancel={() => { setShowJd(false); setJdText(''); setJdTargetId(null) }}
        confirmLoading={jdAnalyzing}
        okText="开始分析"
        width={560}
      >
        <TextArea
          rows={8}
          placeholder="粘贴 JD 原文..."
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
      </Modal>
    </div>
  )
}
