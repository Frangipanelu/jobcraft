import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          // antd 及其全家桶依赖（rc-* 组件、@rc-component、icons、dayjs、runtime）单独成 chunk，便于长缓存
          const isAntdFamily =
            id.includes('node_modules/antd') ||
            id.includes('node_modules/@ant-design') ||
            id.includes('node_modules/@rc-component') ||
            id.includes('node_modules/rc-') ||
            id.includes('node_modules/@babel/runtime') ||
            id.includes('node_modules/@ctrl/tinycolor') ||
            id.includes('node_modules/dayjs')
          if (isAntdFamily) {
            return 'antd-vendor'
          }
          // react 生态单独成 chunk
          if (
            id.includes('node_modules/react') ||
            id.includes('node_modules/scheduler')
          ) {
            return 'react-vendor'
          }
          return 'vendor'
        },
      },
    },
  },
})
