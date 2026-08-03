import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#0f6b52',
          colorInfo: '#0f6b52',
          colorLink: '#0f6b52',
          colorLinkHover: '#2c7a63',
          borderRadius: 8,
          fontSize: 14,
          colorText: '#1c1b18',
          colorTextSecondary: '#6f6c63',
          colorTextTertiary: '#a8a49b',
          colorBgLayout: '#faf9f6',
          colorBgContainer: '#fefefc',
          colorBgElevated: '#fefefc',
          colorBorder: '#e9e6de',
          colorBorderSecondary: '#efede7',
          fontFamily: '"PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif',
        },
        components: {
          Layout: {
            siderBg: '#faf9f6',
            headerBg: 'rgba(250, 249, 246, 0.85)',
            headerPadding: '0 32px',
          },
          Menu: {
            itemBg: 'transparent',
            itemColor: '#6f6c63',
            itemHoverColor: '#1c1b18',
            itemHoverBg: 'rgba(28, 27, 24, 0.05)',
            itemSelectedColor: '#0a5440',
            itemSelectedBg: '#e7efe8',
            itemBorderRadius: 8,
          },
          Button: {
            controlHeight: 36,
            fontWeight: 600,
          },
          Card: {
            borderRadiusLG: 12,
          },
          Modal: {
            borderRadiusLG: 12,
          },
          Table: {
            headerBg: '#f6f4ef',
            headerColor: '#6f6c63',
            headerSplitColor: '#efede7',
            borderColor: '#efede7',
          },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
