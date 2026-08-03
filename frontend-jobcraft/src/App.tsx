import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Button, Layout, Menu, Spin } from 'antd'
import {
  AimOutlined,
  ArrowLeftOutlined,
  FileTextOutlined,
  HomeOutlined,
} from '@ant-design/icons'
import { navigate, parseRoute, type RouteName } from './useRoute.ts'

const CareerRoutePage = lazy(() => import('./pages/CareerRoutePage.tsx'))
const ExperiencePage = lazy(() => import('./pages/ExperiencePage.tsx'))
const JDAnalysisPage = lazy(() => import('./pages/JDAnalysisPage.tsx'))
const JobPage = lazy(() => import('./pages/JobPage.tsx'))
const InterviewPrepPage = lazy(() => import('./pages/InterviewPrepPage.tsx'))
const InterviewReviewPage = lazy(() => import('./pages/InterviewReviewPage.tsx'))

const { Sider, Header, Content } = Layout

const NAV_ITEMS: { key: RouteName; icon: React.ReactNode; label: string }[] = [
  { key: 'dashboard', icon: <HomeOutlined />, label: '求职路线' },
  { key: 'experience', icon: <FileTextOutlined />, label: '经历卡' },
  { key: 'jd-analysis', icon: <AimOutlined />, label: 'JD 分析库' },
]

const PAGE_TITLES: Record<string, string> = {
  dashboard: '求职路线',
  experience: '经历卡',
  'jd-analysis': 'JD 分析库',
  job: '定制简历',
  prep: '面试准备',
  review: '面试复盘',
}

function isNavRoute(name: RouteName): boolean {
  return ['dashboard', 'experience', 'jd-analysis'].includes(name)
}

export default function App() {
  const [route, setRoute] = useState(parseRoute)

  useEffect(() => {
    const handler = () => setRoute(parseRoute())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const activeKey = isNavRoute(route.name) ? route.name : 'dashboard'

  const pageNode = useMemo(() => {
    const node = (() => {
      switch (route.name) {
        case 'dashboard':
          return <CareerRoutePage />
        case 'experience':
          return <ExperiencePage />
        case 'jd-analysis':
          return <JDAnalysisPage />
        case 'job':
          return <JobPage jobId={route.params.jobId || null} />
        case 'prep':
          return <InterviewPrepPage submissionId={route.params.submissionId || null} />
        case 'review':
          return <InterviewReviewPage submissionId={route.params.submissionId || null} />
        default:
          return <CareerRoutePage />
      }
    })()
    return (
      <Suspense
        fallback={
          <div style={{ textAlign: 'center', padding: 80 }}>
            <Spin size="large" tip="页面加载中..." />
          </div>
        }
      >
        {node}
      </Suspense>
    )
  }, [route])

  const isSubPage = route.name === 'job' || route.name === 'prep' || route.name === 'review'
  const pageTitle = PAGE_TITLES[route.name] || ''

  return (
    <Layout className="jc-layout">
      <Sider width={200} className="jc-sider">
        <div className="jc-brand">
          <div className="jc-brand-logo">J</div>
          <div>
            <div className="jc-brand-title">JobCraft</div>
            <div className="jc-brand-sub">求职助手</div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          className="jc-menu"
          items={NAV_ITEMS.map((item) => ({
            key: item.key,
            icon: item.icon,
            label: item.label,
            onClick: () => navigate(item.key as RouteName),
          }))}
        />
      </Sider>
      <Layout>
        <Header className="jc-header">
          {isSubPage && (
            <Button
              className="jc-back-link"
              type="link"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('dashboard')}
            >
              返回
            </Button>
          )}
          <span className="jc-page-title">{pageTitle}</span>
        </Header>
        <Content className="jc-page">{pageNode}</Content>
      </Layout>
    </Layout>
  )
}
