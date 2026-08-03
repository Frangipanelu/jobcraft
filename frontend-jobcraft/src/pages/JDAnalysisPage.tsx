import { useEffect, useState } from 'react'
import {
  listJobAnalyses,
  step1AtsRecommend,
} from '../api.ts'
import { navigate as routeNavigate } from '../useRoute.ts'
import {
  AimOutlined,
  DeleteOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Descriptions,
  Divider,
  Empty,
  Input,
  message,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
const { Text } = Typography
const { TextArea } = Input

export default function JDAnalysisPage() {
  const [analyses, setAnalyses] = useState<any[]>([])
  const [searchText, setSearchText] = useState('')
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([])
  const [loading, setLoading] = useState(false)
  const [position, setPosition] = useState('')
  const [company, setCompany] = useState('')
  const [jdText, setJdText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeElapsed, setAnalyzeElapsed] = useState(0)
  const [result, setResult] = useState<any>(null)
  const [analysisId, setAnalysisId] = useState<number | null>(null)

  const loadAnalyses = async () => {
    setLoading(true)
    try {
      const data = await listJobAnalyses()
      setAnalyses(data.analyses || [])
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAnalyses()
  }, [])

  useEffect(() => {
    if (!analyzing) { setAnalyzeElapsed(0); return }
    const t0 = Date.now()
    const id = setInterval(() => setAnalyzeElapsed(Math.floor((Date.now() - t0) / 1000)), 500)
    return () => clearInterval(id)
  }, [analyzing])

  const handleViewAnalysis = async (id: number) => {
    try {
      const res = await fetch(`/api/jobcraft/job/analyze/${id}`)
      if (!res.ok) throw new Error('查询失败')
      const analysis = await res.json()
      setResult(analysis.jd_requirements || analysis.ats)
      setAnalysisId(analysis.id)
      setPosition(analysis.position || '')
      setCompany(analysis.company || '')
      setJdText(analysis.jd_text || '')
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleAnalyze = async () => {
    if (!position.trim()) {
      message.warning('请输入岗位名称')
      return
    }
    if (!jdText.trim()) {
      message.warning('请粘贴 JD 文本')
      return
    }
    setAnalyzing(true)
    setResult(null)
    setAnalysisId(null)
    try {
      if (!company.trim()) {
        message.warning('请输入公司名称')
        return
      }
      const data = await step1AtsRecommend({
        position: position.trim(),
        company: company.trim(),
        jd_text: jdText.trim(),
      })
      setResult(data.ats)
      setAnalysisId(data.job_analysis_id)
      message.success('JD 分析完成')
      loadAnalyses()
    } catch (err) {
      message.error((err as Error).message)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`/api/jobcraft/job/analyze/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      message.success('已删除')
      setSelectedRowKeys(prev => prev.filter(k => k !== id))
      loadAnalyses()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) { message.warning('请先选择记录'); return }
    try {
      await Promise.all(selectedRowKeys.map(id =>
        fetch(`/api/jobcraft/job/analyze/${id}`, { method: 'DELETE' })
      ))
      message.success(`已删除 ${selectedRowKeys.length} 条记录`)
      setSelectedRowKeys([])
      loadAnalyses()
    } catch (err) {
      message.error((err as Error).message)
    }
  }

  const filteredAnalyses = searchText.trim()
    ? analyses.filter(a => (a.position || '').includes(searchText) || (a.company || '').includes(searchText))
    : analyses

  const ats = result as any

  return (
    <div>
      <Card title="新建 JD 分析" style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Input
              placeholder="岗位名称 *"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
              style={{ width: 280 }}
            />
            <Input
              placeholder="公司 *"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              style={{ width: 200 }}
            />
          </Space>
          <TextArea
            rows={6}
            placeholder="粘贴 JD 原文..."
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
          />
          <Space>
            <Button type="primary" loading={analyzing} onClick={handleAnalyze} icon={<AimOutlined />}>
              开始分析
            </Button>
          </Space>
        </Space>
      </Card>

      {analyzing && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" tip={`AI 正在分析 JD（${analyzeElapsed} 秒）`} />
          <div style={{ marginTop: 12, color: 'var(--jc-muted)', fontSize: 13 }}>首次分析约需 10-30 秒</div>
        </div>
      )}

      {ats && (
        <Card title="分析结果" style={{ marginBottom: 24 }}>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="岗位">{ats.job_title}</Descriptions.Item>
            <Descriptions.Item label="经验要求">{ats.years_of_experience || '-'}</Descriptions.Item>
            <Descriptions.Item label="学历要求">{ats.education || '-'}</Descriptions.Item>
            <Descriptions.Item label="薪资范围">{ats.salary || '-'}</Descriptions.Item>
            <Descriptions.Item label="工作地点">{ats.location || '-'}</Descriptions.Item>
          </Descriptions>

          <div style={{ marginTop: 12 }}>
            <Text strong>硬技能：</Text>
            <div style={{ marginTop: 4 }}>
              {(ats.required_skills || []).map((s: string) => (
                <Tag key={s} color="blue">{s}</Tag>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <Text strong>加分技能：</Text>
            <div style={{ marginTop: 4 }}>
              {(ats.preferred_skills || []).map((s: string) => (
                <Tag key={s} color="green">{s}</Tag>
              ))}
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <Text strong>职责：</Text>
            <ul style={{ margin: '4px 0 0 16px' }}>
              {(ats.responsibilities || []).map((r: string, i: number) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>

          {(ats.subtext_decoded || []).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text strong style={{ color: 'var(--jc-warn-text)' }}>暗话分析（JD 潜台词）：</Text>
              {(ats.subtext_decoded || []).map((s: any, i: number) => (
                <div key={i} style={{ background: 'var(--jc-warn-bg)', border: '1px solid var(--jc-line)', borderRadius: 8, padding: '12px 16px', marginTop: 8 }}>
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
          <Divider />
          <Button type="primary" icon={<FileTextOutlined />} onClick={() => routeNavigate('job', { jobId: String(analysisId) })}>
            进入定制工作台
          </Button>
        </Card>
      )}

      <Card
        title={`分析历史（${analyses.length}）`}
        loading={loading}
        extra={
          <Space>
            <Input.Search
              placeholder="搜索岗位/公司"
              allowClear
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ width: 180 }}
            />
            {selectedRowKeys.length > 0 && (
              <Popconfirm title={`确定删除选中的 ${selectedRowKeys.length} 条记录？`} onConfirm={handleBatchDelete}>
                <Button size="small" danger>批量删除（{selectedRowKeys.length}）</Button>
              </Popconfirm>
            )}
          </Space>
        }
      >
        {filteredAnalyses.length === 0 ? (
          <Empty description={searchText ? '无匹配记录' : '暂无分析记录'} />
        ) : (
          <Table
            dataSource={filteredAnalyses}
            rowKey="id"
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
            size="small"
            rowSelection={{
              selectedRowKeys,
              onChange: (keys: any) => setSelectedRowKeys(keys as number[]),
            }}
            columns={[
              {
                title: '岗位',
                dataIndex: 'position',
                render: (v: string, r: any) => <a onClick={() => handleViewAnalysis(r.id)}>{v || '-'}</a>,
              },
              { title: '公司', dataIndex: 'company', render: (v: string) => v || '-' },
              { title: '时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
              {
                title: '操作',
                render: (_: any, record: any) => (
                  <Space>
                    <Button size="small" onClick={() => handleViewAnalysis(record.id)}>查看</Button>
                    <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
