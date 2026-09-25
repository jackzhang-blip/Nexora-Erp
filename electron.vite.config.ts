import { defineConfig } from 'electron-vite'
import vue from '@vitejs/plugin-vue'

// 主进程、预加载脚本和 Vue 页面分别构建，避免桌面权限泄露到渲染进程。
export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    plugins: [vue()]
  }
})
