import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AuditOutlined,
  DeleteOutlined,
  FileTextOutlined,
  InboxOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  Empty,
  Input,
  List,
  message,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tabs,
  Typography,
  Upload,
} from 'antd'
import type { UploadFile } from 'antd/es/upload'
import {
  analyzeInterviewReview,
  createInterviewReview,
  deleteInterviewReview,
  generateInterviewReviewQuestionTable,
  getInterviewReviewDetail,
  getSubmission,
  listInterviewReviews,
  listJobAnalyses,
  parseInterviewReviewPreview,
  uploadInterviewReview,
  type InterviewReviewCreateResult,
  type InterviewReviewDetailRecord,
  type InterviewReviewParsePreviewQAPair,
  type InterviewReviewParsePreviewResult,
  type InterviewReviewRecord,
  type InterviewReviewResult,
  type ReviewedQuestion,
} from '../api.ts'

const { TextArea } = Input
const { Option } = Select
const { Text, Title } = Typography
const { Panel } = Collapse

const ROUND_OPTIONS = [
  { label: '技术面', value: '技术面' },
  { label: '业务面', value: '业务面' },
  { label: 'HR 面', value: 'HR面' },
]

const questionTableColumns = [
  {
    title: '序号',
    dataIndex: 'sequence',
    width: 60,
    render: (v: number) => <Tag color="blue">Q{v}</Tag>,
  },
  {
    title: '时间',
    dataIndex: 'start_time',
    width: 90,
    render: (v?: string) => v || '-',
  },
  {
    title: '维度',
    dataIndex: 'dimension',
    width: 120,
    render: (v?: string) => (v ? <Tag>{v}</Tag> : '-'),
  },
  {
    title: '难度',
    dataIndex: 'level',
    width: 80,
    render: (v?: string) => (v ? <Tag color="orange">{v}</Tag> : '-'),
  },
  {
    title: '意图',
    dataIndex: 'intent',
    ellipsis: true,
    render: (v?: string) => v || '-',
  },
  {
    title: '问题',
    dataIndex: 'question_text',
    ellipsis: true,
  },
  {
    title: '我的回答',
    dataIndex: 'my_answer',
    ellipsis: true,
    render: (v?: string) => v || '未匹配到回答',
  },
]

function buildResultFromDetail(
  record: InterviewReviewDetailRecord,
  qaPairs: ReviewedQuestion[],
): InterviewReviewResult {
  const analysis: Partial<InterviewReviewResult> = record.analysis || {}
  return {
    record_id: record.id,
    user_id: record.user_id,
    title: record.title,
    company: record.company,
    position: record.position,
    round_type: record.round_type,
    overall_score:
      typeof analysis.overall_score === 'number' ? analysis.overall_score : 0,
    summary: analysis.summary || '',
    strengths: analysis.strengths || [],
    weaknesses: analysis.weaknesses || [],
    action_items: analysis.action_items || [],
    questions: qaPairs,
    created_at: record.created_at,
  }
}

function formatDate(iso?: string): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

export default function InterviewReviewPage({ submissionId }: { submissionId?: string | null } = {}) {
  const [records, setRecords] = useState<InterviewReviewRecord[]>([])
  const [analyses, setAnalyses] = useState<any[]>([])
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null)
  const [result, setResult] = useState<InterviewReviewResult | null>(null)

  const [company, setCompany] = useState('')
  const [position, setPosition] = useState('')
  const [roundType, setRoundType] = useState<string>('业务面')
  const [jobAnalysisId, setJobAnalysisId] = useState<number | undefined>()
  const [rawText, setRawText] = useState('')

  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [inputMode, setInputMode] = useState<'text' | 'file'>('text')
  const [detailRecord, setDetailRecord] = useState<InterviewReviewDetailRecord | null>(null)

  const [loadingList, setLoadingList] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [dimensionFilter, setDimensionFilter] = useState<string | null>(null)

  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewData, setPreviewData] = useState<InterviewReviewParsePreviewResult | null>(null)

  // 分步分析状态
  const [currentRecordId, setCurrentRecordId] = useState<number | null>(null)
  const [selectedSequences, setSelectedSequences] = useState<number[]>([])
  const [questionTable, setQuestionTable] = useState<InterviewReviewParsePreviewQAPair[]>([])
  const [generatingQuestionTable, setGeneratingQuestionTable] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisStep, setAnalysisStep] = useState<'input' | 'preview' | 'question_table' | 'result'>('input')

  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadRecords()
    listJobAnalyses()
      .then((res) => setAnalyses(res.analyses || []))
      .catch((e) => message.error(e.message))
    if (submissionId) {
      getSubmission(Number(submissionId))
        .then((s) => {
          setCompany(s.company)
          setPosition(s.position)
          if (s.job_analysis_id) setJobAnalysisId(s.job_analysis_id)
        })
        .catch(() => {})
    }
  }, [submissionId])

  // 分析结果出现时自动滚动到解析区
  useEffect(() => {
    if (result && !loadingDetail) {
      resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [result, loadingDetail])

  const loadRecords = async () => {
    setLoadingList(true)
    try {
      const data = await listInterviewReviews()
      setRecords(data.records || [])
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setLoadingList(false)
    }
  }

  const handleSelectRecord = async (recordId: number) => {
    setLoadingDetail(true)
    setSelectedRecordId(recordId)
    try {
      const data = await getInterviewReviewDetail(recordId)
      const record = data.record
      const qaPairs = data.qa_pairs || []
      setDetailRecord(record)
      setResult(buildResultFromDetail(record, qaPairs))
    } catch (err) {
      message.error((err as Error).message)
      setResult(null)
      setDetailRecord(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleUpload = async () => {
    if (!position.trim()) {
      message.warning('请填写岗位名称')
      return
    }

    setUploading(true)
    try {
      let created: InterviewReviewCreateResult
      if (inputMode === 'file') {
        const file = fileList[0]?.originFileObj as File | undefined
        if (!file) {
          message.warning('请选择文件')
          setUploading(false)
          return
        }
        created = await uploadInterviewReview(file, {
          company: company.trim(),
          position: position.trim(),
          round_type: roundType,
          job_analysis_id: jobAnalysisId,
          submission_id: submissionId ? Number(submissionId) : null,
        })
      } else {
        if (!rawText.trim()) {
          message.warning('请粘贴面试记录文本')
          setUploading(false)
          return
        }
        created = await createInterviewReview({
          company: company.trim(),
          position: position.trim(),
          round_type: roundType,
          job_analysis_id: jobAnalysisId,
          submission_id: submissionId ? Number(submissionId) : null,
          raw_text: rawText.trim(),
        })
      }
      message.success('面试记录已解析，请选择要详细复盘的问题')
      setCurrentRecordId(created.record_id)
      setPreviewData({
        dialogue: created.dialogue,
        qa_pairs: created.qa_pairs,
        qa_pair_count: created.qa_pair_count,
        speaker_count: created.speaker_count,
        role_counts: created.role_counts,
      })
      // 默认勾选前 8 个有价值的问题
      const defaultSelected = created.qa_pairs
        .slice(0, 8)
        .map((q) => q.sequence)
      setSelectedSequences(defaultSelected)
      setPreviewVisible(true)
      setAnalysisStep('preview')
      setFileList([])
      await loadRecords()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (recordId: number) => {
    try {
      await deleteInterviewReview(recordId)
      message.success('已删除')
      if (selectedRecordId === recordId) {
        setSelectedRecordId(null)
        setResult(null)
      }
      await loadRecords()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handlePreview = async () => {
    const previewParams = {
      company: company.trim(),
      position: position.trim(),
      round_type: roundType,
      job_analysis_id: jobAnalysisId,
      submission_id: submissionId ? Number(submissionId) : null,
      with_intent: true,
    }
    if (inputMode === 'file') {
      const file = fileList[0]?.originFileObj as File | undefined
      if (!file) {
        message.warning('请选择文件')
        return
      }
      setPreviewLoading(true)
      try {
        const data = await parseInterviewReviewPreview({ file, ...previewParams })
        setPreviewData(data)
        setPreviewVisible(true)
        // 预览模式下尚未创建记录，不支持勾选分析
        setSelectedSequences([])
        setCurrentRecordId(null)
        setAnalysisStep('preview')
      } catch (err) {
        message.error((err as Error).message)
      } finally {
        setPreviewLoading(false)
      }
      return
    }

    if (!rawText.trim()) {
      message.warning('请粘贴面试记录文本')
      return
    }
    setPreviewLoading(true)
    try {
      const data = await parseInterviewReviewPreview({
        raw_text: rawText.trim(),
        ...previewParams,
      })
      setPreviewData(data)
      setPreviewVisible(true)
      setSelectedSequences([])
      setCurrentRecordId(null)
      setAnalysisStep('preview')
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const {
    groupedQuestions,
    dimensionStats,
    overallStats,
    availableDimensions,
  } = useMemo(() => {
    if (!result) {
      return {
        groupedQuestions: [],
        dimensionStats: [],
        overallStats: { total: 0, avg: 0, minAvg: 0, weakDimension: '-' },
        availableDimensions: [],
      }
    }

    // 按维度分组
    const map = new Map<string, ReviewedQuestion[]>()
    for (const q of result.questions) {
      const dim = q.dimension || '未分类'
      const list = map.get(dim) || []
      list.push(q)
      map.set(dim, list)
    }
    const allGroups = Array.from(map.entries())

    // 每个维度的统计
    const stats = allGroups.map(([dim, questions]) => {
      const avg =
        questions.reduce((sum, q) => sum + q.score, 0) / questions.length
      return {
        dimension: dim,
        count: questions.length,
        avg: Math.round(avg),
      }
    })

    // 整体统计
    const total = result.questions.length
    const avg =
      total > 0
        ? Math.round(
          result.questions.reduce((sum, q) => sum + q.score, 0) / total
        )
        : 0
    const weak =
      stats.length > 0
        ? stats.reduce((min, s) => (s.avg < min.avg ? s : min), stats[0])
        : null

    const filteredGroups = dimensionFilter
      ? allGroups.filter(([dim]) => dim === dimensionFilter)
      : allGroups

    return {
      groupedQuestions: filteredGroups,
      dimensionStats: stats,
      overallStats: {
        total,
        avg,
        minAvg: weak?.avg ?? 0,
        weakDimension: weak?.dimension ?? '-',
      },
      availableDimensions: stats.map((s) => s.dimension),
    }
  }, [result, dimensionFilter])

  return (
    <div>
      {/* 顶部：上传面试记录（横向通栏） */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: 'var(--jc-bg)',
          paddingBottom: 16,
        }}
      >
        <Card className="jc-section" title="上传面试记录">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 16,
              marginBottom: 16,
            }}
          >
            <Input
              placeholder="公司"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              style={{ width: '100%' }}
            />
            <Input
              placeholder="岗位名称 *"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              style={{ width: '100%' }}
            />
            <Select
              placeholder="面试轮次"
              value={roundType}
              onChange={(v) => setRoundType(v)}
              style={{ width: '100%' }}
            >
              {ROUND_OPTIONS.map((o) => (
                <Option key={o.value} value={o.value}>
                  {o.label}
                </Option>
              ))}
            </Select>
            <Select
              placeholder="关联岗位分析（可选）"
              value={jobAnalysisId}
              onChange={(v) => setJobAnalysisId(v)}
              style={{ width: '100%' }}
              allowClear
            >
              {analyses.map((a) => (
                <Option key={a.id} value={a.id}>
                  {a.position}（{a.company || '无公司'}）
                </Option>
              ))}
            </Select>
          </div>

          <div style={{ marginBottom: 8 }}>
            <Text type="secondary">
              推荐按标准模板书写，可
              <a href="/interview_record_template.md" download> 点击下载模板 </a>
              。支持标签：面试官/我、Q/A、Interviewer/Candidate、讲话人1/2、Speaker 1/2；
              也支持仅时间戳格式。上传前可先点「解析预览」确认说话人拆分。
            </Text>
          </div>

          <Segmented
            options={[
              { label: '粘贴文本', value: 'text' },
              { label: '上传文件', value: 'file' },
            ]}
            value={inputMode}
            onChange={(v) => {
              setInputMode(v as 'text' | 'file')
              if (v === 'text') setFileList([])
            }}
            style={{ marginBottom: 16 }}
          />

          {inputMode === 'file' ? (
            <Upload.Dragger
              name="interview_file"
              multiple={false}
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: newFileList }) => setFileList(newFileList)}
              onRemove={() => {
                setFileList([])
                return true
              }}
              accept=".txt,.md,.pdf,.docx"
              style={{ marginBottom: 16 }}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽上传面试记录文件</p>
              <p className="ant-upload-hint">
                支持 TXT / PDF / DOCX / MD，内容建议按标准模板格式书写
              </p>
            </Upload.Dragger>
          ) : (
            <TextArea
              rows={8}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder={
                '按标准模板粘贴面试对话，例如：\n' +
                '面试官：请你先做一个自我介绍。\n' +
                '我：我叫李明，毕业于某某大学计算机专业。\n' +
                '面试官 09:02 你们订单系统每天量级多少？\n' +
                '我：日均几百万单。'
              }
            />
          )}

          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <Space>
              <Button
                loading={previewLoading}
                onClick={handlePreview}
              >
                解析预览
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                loading={uploading}
                onClick={handleUpload}
              >
                上传并分析
              </Button>
            </Space>
          </div>
        </Card>

        <Modal
          title="解析预览"
          open={previewVisible}
          onCancel={() => setPreviewVisible(false)}
          width={800}
          footer={[
            <Button key="close" onClick={() => setPreviewVisible(false)}>
              关闭
            </Button>,
            currentRecordId && (
              <Button
                key="question-table"
                type="primary"
                loading={generatingQuestionTable}
                disabled={selectedSequences.length === 0}
                onClick={async () => {
                  if (!currentRecordId) return
                  setGeneratingQuestionTable(true)
                  try {
                    const data = await generateInterviewReviewQuestionTable(currentRecordId)
                    setQuestionTable(data.questions)
                    setPreviewVisible(false)
                    setAnalysisStep('question_table')
                    message.success('问题表已生成')
                  } catch (err) {
                    message.error((err as Error).message)
                  } finally {
                    setGeneratingQuestionTable(false)
                  }
                }}
              >
                生成问题表（已选 {selectedSequences.length}/8）
              </Button>
            ),
          ].filter(Boolean)}
        >
          {previewData && (
            <div>
              <Text>
                识别到 <Text strong>{previewData.speaker_count}</Text> 位发言人：
                面试官 <Text strong>{previewData.role_counts.interviewer}</Text> 句 /{' '}
                面试者 <Text strong>{previewData.role_counts.candidate}</Text> 句 /{' '}
                未知 <Text strong>{previewData.role_counts.unknown}</Text> 句；
                共匹配 <Text strong>{previewData.qa_pair_count}</Text> 个 QA 对
              </Text>
              {currentRecordId && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">
                    请勾选需要详细解析的问题（最多 8 个）。未勾选的问题也会进入问题表汇总，但不会生成详细解析。
                  </Text>
                </div>
              )}
              <Tabs
                style={{ marginTop: 16 }}
                items={[
                  {
                    key: 'dialogue',
                    label: '说话人拆分',
                    children: (
                      <List
                        dataSource={previewData.dialogue}
                        renderItem={(item) => (
                          <List.Item>
                            <div style={{ width: '100%' }}>
                              <Space>
                                <Tag
                                  color={
                                    item.role === 'interviewer'
                                      ? 'blue'
                                      : item.role === 'candidate'
                                        ? 'green'
                                        : 'default'
                                  }
                                >
                                  {item.role === 'interviewer'
                                    ? '面试官'
                                    : item.role === 'candidate'
                                      ? '面试者'
                                      : '未知'}
                                </Tag>
                                <Text strong>{item.speaker}</Text>
                                {item.time && (
                                  <Text type="secondary">{item.time}</Text>
                                )}
                              </Space>
                              <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>
                                {item.content}
                              </div>
                            </div>
                          </List.Item>
                        )}
                      />
                    ),
                  },
                  {
                    key: 'qa',
                    label: 'QA 配对预览',
                    children: previewData.qa_pairs.length === 0 ? (
                      <Empty description="未识别到 QA 对" />
                    ) : (
                      <List
                        dataSource={previewData.qa_pairs}
                        renderItem={(item) => {
                          const checked = selectedSequences.includes(item.sequence)
                          const disabled = !checked && selectedSequences.length >= 8 && !!currentRecordId
                          return (
                            <List.Item>
                              <div style={{ width: '100%' }}>
                                <Space wrap>
                                  <Tag color="blue">Q{item.sequence}</Tag>
                                  <Text strong>{item.speaker}</Text>
                                  {item.start_time && (
                                    <Text type="secondary">{item.start_time}</Text>
                                  )}
                                  {item.dimension && <Tag>{item.dimension}</Tag>}
                                  {item.level && <Tag color="orange">{item.level}</Tag>}
                                  {item.intent && (
                                    <Tag color="purple">意图：{item.intent}</Tag>
                                  )}
                                  {currentRecordId && (
                                    <Checkbox
                                      checked={checked}
                                      disabled={disabled}
                                      onChange={(e) => {
                                        if (e.target.checked) {
                                          setSelectedSequences((prev) =>
                                            [...prev, item.sequence].slice(0, 8)
                                          )
                                        } else {
                                          setSelectedSequences((prev) =>
                                            prev.filter((s) => s !== item.sequence)
                                          )
                                        }
                                      }}
                                    >
                                      详细解析
                                    </Checkbox>
                                  )}
                                </Space>
                                <div
                                  style={{
                                    marginTop: 4,
                                    padding: 8,
                                    background: 'var(--jc-success-bg)',
                                    borderRadius: 4,
                                    whiteSpace: 'pre-wrap',
                                  }}
                                >
                                  <Text strong>问题：</Text>
                                  <Text>{item.question_text || '未识别'}</Text>
                                </div>
                                <div
                                  style={{
                                    marginTop: 4,
                                    padding: 8,
                                    background: 'var(--jc-info-bg)',
                                    borderRadius: 4,
                                    whiteSpace: 'pre-wrap',
                                  }}
                                >
                                  <Text strong>回答：</Text>
                                  <Text>{item.my_answer || '未匹配到回答'}</Text>
                                </div>
                              </div>
                            </List.Item>
                          )
                        }}
                      />
                    ),
                  },
                ]}
              />
            </div>
          )}
        </Modal>
      </div>

      {/* 下方：复盘区 + 历史记录 */}
      <div className="jc-review-cols">
        <div ref={resultRef} style={{ minWidth: 0 }}>
          {loadingDetail && (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
            </div>
          )}

          {analysisStep === 'question_table' && !result && !loadingDetail && currentRecordId && (
            <Card className="jc-section" title="问题表汇总">
              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">
                  已生成完整问题表（含意图、维度、难度）。请勾选需要详细解析的问题（最多 8 个），然后点击「开始详细解析」。
                </Text>
              </div>
              <Table
                rowKey="sequence"
                dataSource={questionTable}
                columns={questionTableColumns}
                pagination={false}
                bordered
                size="small"
                rowSelection={{
                  type: 'checkbox',
                  selectedRowKeys: selectedSequences,
                  onChange: (keys) => setSelectedSequences(keys as number[]),
                  getCheckboxProps: (record) => ({
                    disabled:
                      selectedSequences.length >= 8 &&
                      !selectedSequences.includes(record.sequence),
                  }),
                }}
              />
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                <Space>
                  <Button
                    onClick={() => {
                      setAnalysisStep('preview')
                      setPreviewVisible(true)
                    }}
                  >
                    返回预览
                  </Button>
                  <Button
                    type="primary"
                    loading={analyzing}
                    disabled={selectedSequences.length === 0}
                    onClick={async () => {
                      if (!currentRecordId) return
                      setAnalyzing(true)
                      try {
                        const data = await analyzeInterviewReview(
                          currentRecordId,
                          selectedSequences,
                        )
                        setResult(data)
                        setAnalysisStep('result')
                        setSelectedRecordId(currentRecordId)
                        setDetailRecord(null)
                        message.success('详细解析完成')
                        await loadRecords()
                      } catch (err) {
                        message.error((err as Error).message)
                      } finally {
                        setAnalyzing(false)
                      }
                    }}
                  >
                    开始详细解析（已选 {selectedSequences.length}/8）
                  </Button>
                </Space>
              </div>
            </Card>
          )}

          {result && !loadingDetail && (
            <>
              <Card className="jc-section" title="整体评价">
                <Row gutter={[24, 16]} align="middle">
                  <Col flex="none">
                    <Progress
                      type="circle"
                      percent={result.overall_score}
                      width={90}
                      status="active"
                      strokeColor={
                        result.overall_score >= 80
                          ? 'var(--jc-success)'
                          : result.overall_score >= 60
                            ? 'var(--jc-warn)'
                            : 'var(--jc-danger)'
                      }
                    />
                  </Col>
                  <Col flex="auto">
                    <Title level={5} style={{ marginTop: 0 }}>
                      {result.title || `${result.company} ${result.position}`}
                    </Title>
                    <Text>{result.summary || '暂无总结'}</Text>
                    <div style={{ marginTop: 12 }}>
                      <Space wrap>
                        {result.strengths.map((s, i) => (
                          <Tag key={`s-${i}`} color="green">
                            {s}
                          </Tag>
                        ))}
                        {result.weaknesses.map((w, i) => (
                          <Tag key={`w-${i}`} color="red">
                            {w}
                          </Tag>
                        ))}
                      </Space>
                    </div>
                  </Col>
                  <Col xs={24} sm={12} md={8} lg={6}>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Statistic
                          title="总题数"
                          value={overallStats.total}
                        />
                      </Col>
                      <Col span={12}>
                        <Statistic
                          title="平均得分"
                          value={overallStats.avg}
                          suffix="分"
                        />
                      </Col>
                    </Row>
                    {overallStats.weakDimension !== '-' && (
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary">薄弱维度：</Text>
                        <Tag color="red">
                          {overallStats.weakDimension}（
                          {overallStats.minAvg}分）
                        </Tag>
                      </div>
                    )}
                  </Col>
                </Row>

                {dimensionStats.length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <Text strong>各维度均分：</Text>
                    <Row gutter={[16, 8]} style={{ marginTop: 8 }}>
                      {dimensionStats.map((s) => (
                        <Col key={s.dimension} xs={12} md={8} lg={6}>
                          <div>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {s.dimension}
                            </Text>
                            <Progress
                              percent={s.avg}
                              size="small"
                              status="active"
                              format={(p) => `${p}分`}
                              strokeColor={
                                s.avg >= 80
                                  ? 'var(--jc-success)'
                                  : s.avg >= 60
                                    ? 'var(--jc-warn)'
                                    : 'var(--jc-danger)'
                              }
                            />
                          </div>
                        </Col>
                      ))}
                    </Row>
                  </div>
                )}

                {result.action_items.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <Text strong>后续行动：</Text>
                    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                      {result.action_items.map((item, i) => (
                        <li key={`a-${i}`}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>

              <Card
                className="jc-section"
                title="问题拆解与改进建议"
                extra={
                  <Space wrap>
                    <Button
                      size="small"
                      type={dimensionFilter === null ? 'primary' : 'default'}
                      onClick={() => setDimensionFilter(null)}
                    >
                      全部
                    </Button>
                    {availableDimensions.map((dim) => (
                      <Button
                        key={dim}
                        size="small"
                        type={dimensionFilter === dim ? 'primary' : 'default'}
                        onClick={() => setDimensionFilter(dim)}
                      >
                        {dim}
                      </Button>
                    ))}
                  </Space>
                }
              >
                {groupedQuestions.length === 0 ? (
                  <Empty description="未识别到问题" />
                ) : (
                  <Collapse ghost>
                    {groupedQuestions.map(([dimension, questions]) => {
                      const dimAvg = Math.round(
                        questions.reduce((sum, q) => sum + q.score, 0) /
                        questions.length
                      )
                      return (
                        <Panel
                          header={
                            <Space>
                              <Text strong>{dimension || '未分类'}</Text>
                              <Tag>{questions.length} 题</Tag>
                              <Tag
                                color={
                                  dimAvg >= 80
                                    ? 'green'
                                    : dimAvg >= 60
                                      ? 'orange'
                                      : 'red'
                                }
                              >
                                均分 {dimAvg}
                              </Tag>
                            </Space>
                          }
                          key={dimension}
                        >
                          {questions.map((q) => {
                            const isAnalyzed = q.score > 0 || q.expected_answer
                            return (
                              <Badge.Ribbon
                                key={q.sequence}
                                text={isAnalyzed ? `${q.score}分` : '未解析'}
                                color={
                                  isAnalyzed
                                    ? q.score >= 80
                                      ? 'green'
                                      : q.score >= 60
                                        ? 'orange'
                                        : 'red'
                                    : 'default'
                                }
                              >
                                <Card
                                  size="small"
                                  style={{ marginBottom: 16 }}
                                  title={
                                    <Space wrap>
                                      <Tag color="blue">Q{q.sequence}</Tag>
                                      <Tag>{q.level}</Tag>
                                      {q.related_card_id && (
                                        <Tag color="purple">
                                          关联：{q.related_card_title || '经历卡'}
                                        </Tag>
                                      )}
                                      {!isAnalyzed && (
                                        <Tag color="default">未详细解析</Tag>
                                      )}
                                    </Space>
                                  }
                                  extra={
                                    <Tag icon={<FileTextOutlined />}>
                                      {q.start_time || '无时间'}
                                    </Tag>
                                  }
                                >
                                  <div style={{ marginBottom: 8 }}>
                                    <Text strong>面试官：</Text>
                                    <Text>{q.question_text}</Text>
                                  </div>
                                  <div style={{ marginBottom: 8 }}>
                                    <Text strong type="secondary">
                                      考察意图：
                                    </Text>
                                    <Text>{q.intent}</Text>
                                  </div>
                                  {isAnalyzed && (
                                    <div
                                      style={{
                                        background: 'var(--jc-info-bg)',
                                        padding: 12,
                                        borderRadius: 4,
                                        marginBottom: 12,
                                      }}
                                    >
                                      <Text strong>标准答案：</Text>
                                      <div>{q.expected_answer}</div>
                                    </div>
                                  )}
                                  <div
                                    style={{
                                      background: 'var(--jc-bg-3)',
                                      padding: 12,
                                      borderRadius: 4,
                                      marginBottom: 12,
                                    }}
                                  >
                                    <Text strong>我的回答：</Text>
                                    <div>{q.my_answer || '未匹配到回答'}</div>
                                  </div>
                                  {q.feedback.length > 0 && (
                                    <div style={{ marginBottom: 8 }}>
                                      <Text strong type="warning">
                                        诊断反馈：
                                      </Text>
                                      <ul
                                        style={{
                                          margin: '4px 0 0 16px',
                                          padding: 0,
                                        }}
                                      >
                                        {q.feedback.map((f, i) => (
                                          <li key={`f-${i}`}>{f}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                  {q.suggestions.length > 0 && (
                                    <div>
                                      <Text strong type="success">
                                        改进建议：
                                      </Text>
                                      <ul
                                        style={{
                                          margin: '4px 0 0 16px',
                                          padding: 0,
                                        }}
                                      >
                                        {q.suggestions.map((s, i) => (
                                          <li key={`sug-${i}`}>{s}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </Card>
                              </Badge.Ribbon>
                            )
                          })}
                        </Panel>
                      )
                    })}
                  </Collapse>
                )}
              </Card>

              {detailRecord?.raw_text && (
                <Card className="jc-section" title="原始面试记录">
                  <Collapse ghost defaultActiveKey={[]}>
                    <Panel header="展开查看原始文本" key="raw">
                      <pre
                        style={{
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          background: 'var(--jc-bg-3)',
                          padding: 12,
                          borderRadius: 4,
                          maxHeight: 400,
                          overflow: 'auto',
                        }}
                      >
                        {detailRecord.raw_text}
                      </pre>
                    </Panel>
                  </Collapse>
                </Card>
              )}
            </>
          )}
        </div>

        <div style={{ minWidth: 0 }}>
          <Card
            className="jc-section"
            title="历史记录"
            size="small"
            loading={loadingList}
          >
            {records.length === 0 ? (
              <Empty description="暂无复盘记录" />
            ) : (
              <List
                dataSource={records}
                renderItem={(item) => (
                  <List.Item
                    style={{
                      padding: '12px 0',
                      borderBottom: '1px solid var(--jc-line)',
                      background:
                        selectedRecordId === item.id ? 'var(--jc-success-bg)' : undefined,
                      cursor: 'pointer',
                    }}
                    onClick={() => handleSelectRecord(item.id)}
                    actions={[
                      <Popconfirm
                        key="del"
                        title="确定删除这条复盘记录吗？"
                        onConfirm={(e) => {
                          e?.stopPropagation()
                          handleDelete(item.id)
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                      >
                        <Button
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>,
                    ]}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <AuditOutlined />
                          <Text strong>
                            {item.title || `${item.company} ${item.position}`}
                          </Text>
                        </Space>
                      }
                      description={
                        <div>
                          <div>
                            {item.company} · {item.position} · {item.round_type}
                          </div>
                          <div>
                            <Tag
                              color={
                                item.status === 'done'
                                  ? 'green'
                                  : item.status === 'analyzing'
                                    ? 'processing'
                                    : 'default'
                              }
                            >
                              {item.status}
                            </Tag>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {formatDate(item.created_at)}
                            </Text>
                          </div>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
