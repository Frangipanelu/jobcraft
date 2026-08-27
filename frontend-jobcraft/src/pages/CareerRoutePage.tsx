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
  getSubmission,
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
  sub?: string
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

  // 查看简历弹窗
  const [showResume, setShowResume] = useState(false)
  const [resumeMarkdown, setResumeMarkdown] = useState('')

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

  // 查看已投简历（Markdown 原文）
  const handleViewResume = async (id: number) => {
    try {
      const sub = await getSubmission(id)
      setResumeMarkdown(sub.resume_markdown || '（暂无简历内容）')
      setShowResume(true)
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
      label: '简历',
      sub: hasResume ? '已上传' : '待上传',
      icon: <FileTextOutlined />,
      state: hasResume ? 'done' : 'todo',
      tooltip: hasResume ? '查看简历原文' : '上传已投递的简历文件',
      onClick: () => {
        if (hasResume) {
          handleViewResume(item.id)
        } else {
          setUpCompany(item.company)
          setUpPosition(item.position)
          setShowUpload(true)
        }
      },
    }

    // 🔍 JD分析
    const jdBtn: BtnConfig = {
      key: 'jd',
      label: 'JD 分析',
      sub: hasAnalysis ? '已完成' : hasResume ? '待分析' : '需简历',
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
      label: '润色',
      sub: isManual ? `已抽 ${item.card_count} 张` : `已润色 ${item.card_version_count} 张`,
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
      sub: prepEnabled
        ? item.prep_count > 0
          ? `${item.prep_count} 份`
          : '待生成'
        : '需≥面试邀约',
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
      sub: reviewEnabled
        ? item.review_count > 0
          ? `${item.review_count} 次`
          : '待复盘'
        : '需≥一面',
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
      <div className="jc-page-header">
        <Title level={4} style={{ margin: 0 }}>我的求职路线</Title>
        <Button icon={<UploadOutlined />} onClick={() => setShowUpload(true)}>
          上传已投简历
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="jc-route-card">
          <div className="jc-route-head">
            <Text strong style={{ fontSize: 16 }}>还没有投递记录</Text>
            <Button icon={<UploadOutlined />} onClick={() => setShowUpload(true)}>
              上传已投简历
            </Button>
          </div>
          <div className="jc-route-meta">上传一份已投简历，或手动补录后，每家公司会呈现这条求职路线。</div>
          <div className="jc-route-flow">
            {['resume', 'jd', 'polish', 'prep', 'review'].map((key, i) => (
              <div key={key} className="jc-route-step-wrap">
                {i > 0 && <span className="jc-route-link" />}
                <div className="jc-route-step locked">
                  <span className="jc-route-node">
                    {key === 'resume' && <FileTextOutlined />}
                    {key === 'jd' && <AimOutlined />}
                    {key === 'polish' && <FileTextOutlined />}
                    {key === 'prep' && <AudioOutlined />}
                    {key === 'review' && <FormOutlined />}
                  </span>
                  <div className="jc-route-label">
                    {key === 'resume' ? '简历' : key === 'jd' ? 'JD 分析' : key === 'polish' ? '润色' : key === 'prep' ? '面试准备' : '复盘'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
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
            <div key={item.id} className="jc-route-card">
              <div className="jc-route-head">
                <div className="jc-route-title">
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
                <Space size={8}>
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
                  <Popconfirm title="确定删除？" onConfirm={() => handleDelete(item.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              </div>

              <div className="jc-route-meta">
                {item.created_at && <>创建 {new Date(item.created_at).toLocaleDateString('zh-CN')}</>}
              </div>

              <div className="jc-route-flow">
                {btns.map((btn, i) => (
                  <div key={btn.key} className="jc-route-step-wrap">
                    {i > 0 && <span className={`jc-route-link ${btns[i - 1].state === 'done' ? 'is-done' : ''}`} />}
                    <div className={`jc-route-step ${btn.state}`}>
                      <Tooltip title={btn.tooltip}>
                        <Button
                          className="jc-route-node"
                          icon={btn.icon}
                          disabled={btn.state === 'locked'}
                          onClick={btn.onClick}
                          aria-label={btn.label}
                        />
                      </Tooltip>
                      <div className="jc-route-label">{btn.label}</div>
                      {btn.sub && <div className="jc-route-sub">{btn.sub}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
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

      {/* 查看简历弹窗 */}
      <Modal
        title="已投简历原文"
        open={showResume}
        onCancel={() => setShowResume(false)}
        footer={null}
        width={680}
      >
        <div className="jc-resume-preview" style={{ maxHeight: 520 }}>
          {resumeMarkdown}
        </div>
      </Modal>
    </div>
  )
}
