import { contextBridge, ipcRenderer } from 'electron'
import type { DesktopApi } from '../shared/desktop-api'

// 只暴露明确的版本查询方法，不把 ipcRenderer 整体交给页面。
const desktopApi: DesktopApi = {
  getVersion: () => ipcRenderer.invoke('app:get-version') as Promise<string>
}

contextBridge.exposeInMainWorld('nexora', desktopApi)
