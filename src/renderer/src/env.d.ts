import type { DesktopApi } from '../../shared/desktop-api'

// 浏览器预览时可能没有 Electron 桥，因此在类型中保留可选状态。
declare global {
  interface Window {
    nexora?: DesktopApi
  }
}

export {}
