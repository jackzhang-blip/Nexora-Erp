import { app, BrowserWindow, ipcMain } from 'electron'
import { join } from 'node:path'
import { getBackendHealth } from './backend'

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  // 渲染进程保持隔离；桌面能力通过预加载脚本的受限接口提供。
  const window = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 820,
    minHeight: 560,
    backgroundColor: '#0c1424',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  mainWindow = window
  window.on('closed', () => {
    if (mainWindow === window) mainWindow = null
  })

  // 当前页面不需要弹出新窗口，先阻止页面内容自行打开外部地址。
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  if (process.env.ELECTRON_RENDERER_URL) {
    void window.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void window.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  // 只接受本应用窗口发来的版本查询，避免暴露通用 IPC 通道。
  ipcMain.handle('app:get-version', (event) => {
    if (!mainWindow || event.sender !== mainWindow.webContents) {
      throw new Error('不允许的窗口请求')
    }
    return app.getVersion()
  })

  createWindow()
  ipcMain.handle('backend:get-health', (event) => {
    if (!mainWindow || event.sender !== mainWindow.webContents
      || event.senderFrame !== mainWindow.webContents.mainFrame) {
      throw new Error('不允许的窗口请求')
    }
    return getBackendHealth()
  })
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  // macOS 约定关闭窗口后保留应用，其他平台则退出进程。
  if (process.platform !== 'darwin') app.quit()
})
