import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 代理目标：Docker 内用服务名 backend，本机开发用 localhost
// 通过环境变量 VITE_API_TARGET 覆盖，默认 Docker 模式
const apiTarget = process.env.VITE_API_TARGET || 'http://backend:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: apiTarget,
        ws: true,
      },
    },
  },
})
