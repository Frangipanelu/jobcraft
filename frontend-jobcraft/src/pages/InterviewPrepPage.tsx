import { useEffect, useMemo, useState } from 'react'
import { Button, Card, Collapse, message, Select, Space, Spin, Tabs } from 'antd'
import {
  generateInterviewPrep,
  getInterviewPrep,
  getSubmission,
  listCards,
  type InterviewPrepResult,
  type Submission,
} from '../api.ts'

const { TabPane } = Tabs
const { Option } = Select

const ROUND_OPTIONS = [
  { label: '技术面', value: '技术面' },
  { label: '业务面', value: '业务面' },
  { label: 'HR 面', value: 'HR 面' },
]

export default function InterviewPrepPage({ submissionId }: { submissionId: string | null }) {
  const [submission, setSubmission] = useState<Submission | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [roundType, setRoundType] = useState<string>('技术面')
  const [cards, setCards] = useState<{ id: number; title: string }[]>([])
  const [selectedCardIds, setSelectedCardIds] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<InterviewPrepResult | null>(null)

  // 加载投递信息
  useEffect(() => {
    if (submissionId) {
      getSubmission(Number(submissionId))
        .then((s) => {
          setSubmission(s)
          // 自动选择卡片
          if (s.job_analysis_id) {
            fetch(`/api/jobcraft/job/${s.job_analysis_id}/selected-cards`)
              .then((r) => r.json())
              .then((d) => setSelectedCardIds(d.card_ids || []))
              .catch(() => {})
          }
        })
        .catch((e) => message.error(e.message))
        .finally(() => setInitialLoading(false))
    } else {
      setInitialLoading(false)
    }
    listCards()
      .then((data) => setCards(data.map((c) => ({ id: c.id, title: c.title }))))
      .catch((e) => message.error(e.message))
  }, [submissionId])

  // 检查已有准备稿
  useEffect(() => {
    if (submissionId && submission) {
      const jobId = submission.job_analysis_id
      if (jobId) {
        getInterviewPrep(jobId)
          .then((data) => {
            setResult(data)
            setRoundType(data.round_type)
          })
          .catch(() => setResult(null))
      }
    }
  }, [submissionId, submission])

  const groupedQuestions = useMemo(() => {
    if (!result) return []
    const map = new Map<string, InterviewPrepResult['dimension_questions']>()
    for (const q of result.dimension_questions) {
      const list = map.get(q.dimension) || []
      list.push(q)
      map.set(q.dimension, list)
    }
    return Array.from(map.entries())
  }, [result])

  const handleGenerate = async () => {
    if (!submission) {
      message.warning('未找到投递信息')
      return
    }
    const jobId = submission.job_analysis_id
    if (!jobId) {
      message.warning('该投递未关联 JD 分析，请先在 JD 分析库创建')
      return
    }
    setLoading(true)
    try {
      const data = await generateInterviewPrep(jobId, {
        round_type: roundType,
        card_ids: selectedCardIds,
        submission_id: submission.id,
      })
      setResult(data)
      message.success('面试准备已生成')
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Spin spinning={initialLoading}>
      <div>
      {submission && (
        <Card className="jc-section" style={{ marginBottom: 16 }}>
          <Space size="large">
            <span><strong>岗位：</strong>{submission.position}</span>
            <span><strong>公司：</strong>{submission.company || '-'}</span>
            <span><strong>状态：</strong>{submission.status}</span>
          </Space>
        </Card>
      )}

      <Card className="jc-section">
        <Space wrap>
          <Select
            placeholder="选择面试轮次"
            style={{ width: 160 }}
            value={roundType}
            onChange={(v) => setRoundType(v)}
          >
            {ROUND_OPTIONS.map((o) => (
              <Option key={o.value} value={o.value}>
                {o.label}
              </Option>
            ))}
          </Select>
          <Select
            mode="multiple"
            placeholder="选择要关联的经历卡"
            style={{ width: 320 }}
            value={selectedCardIds}
            onChange={(v) => setSelectedCardIds(v as number[])}
          >
            {cards.map((c) => (
              <Option key={c.id} value={c.id}>
                {c.title}
              </Option>
            ))}
          </Select>
          <Button type="primary" loading={loading} onClick={handleGenerate}>
            生成面试准备
          </Button>
        </Space>
      </Card>

      {loading && !result && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
        </div>
      )}

      {result && (
        <Tabs defaultActiveKey="pitch">
          <TabPane tab="个人介绍" key="pitch">
            <Card className="jc-section">
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{result.elevator_pitch}</pre>
            </Card>
          </TabPane>
          <TabPane tab="维度问题库" key="questions">
            <Collapse ghost>
              {groupedQuestions.map(([dimension, questions]) => (
                <Collapse.Panel header={dimension} key={dimension}>
                  {questions.map((q, idx) => (
                    <Card key={idx} size="small" style={{ marginBottom: 12 }}>
                      <div><strong>{q.question}</strong></div>
                      {q.card_ids.length > 0 && (
                        <div style={{ marginTop: 8, color: 'var(--jc-muted)' }}>
                          关联卡片 ID：{q.card_ids.join(', ')}
                        </div>
                      )}
                      {q.answer_points.length > 0 && (
                        <div style={{ marginTop: 8, background: 'var(--jc-bg-3)', border: '1px solid var(--jc-line)', padding: 12, borderRadius: 4 }}>
                          {q.answer_points.map((pt, i) => (
                            <div key={i}>• {pt}</div>
                          ))}
                        </div>
                      )}
                    </Card>
                  ))}
                </Collapse.Panel>
              ))}
            </Collapse>
          </TabPane>
          <TabPane tab="完整文字版" key="full">
            <Card className="jc-section">
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{result.full_version}</pre>
            </Card>
          </TabPane>
          <TabPane tab="HTML 预览" key="html">
            <iframe
              title="面试稿预览"
              className="jc-iframe"
              srcDoc={result.html_content}
              sandbox="allow-same-origin"
            />
          </TabPane>
        </Tabs>
      )}
    </div>
    </Spin>
  )
}
