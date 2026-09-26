import { app, BrowserWindow, dialog, ipcMain, Menu, nativeImage, Tray } from 'electron'
import { join } from 'node:path'
import { mkdirSync } from 'node:fs'
import { callBackend, getBackendHealth } from './backend'
import type { ErpOperations } from '../shared/erp-api'
import type { HostInput } from '../shared/desktop-api'
import { activateSaved, approveConnection, createHost, disconnect, finishHostSetup, hostFingerprint, hostStatus,
  loadConnections, prepareConnection, recentProfiles, restartHost, resume, shutdownConnections,
  startDiscovery, stopDiscovery, stopHost } from './connections'

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let startupError: string | null = null

if (process.env.NEXORA_USER_DATA_DIR) {
  // 集成验收使用独立用户目录，避免测试创建的服务端影响真实工作资料。
  mkdirSync(process.env.NEXORA_USER_DATA_DIR, { recursive: true })
  app.setPath('userData', process.env.NEXORA_USER_DATA_DIR)
}

function assertMainWindow(event: Electron.IpcMainInvokeEvent): void {
  if (!mainWindow || event.sender !== mainWindow.webContents
    || event.senderFrame !== mainWindow.webContents.mainFrame) throw new Error('不允许的窗口请求')
}

function ensureTray(): void {
  if (tray) return
  // 托盘使用随应用打包的 PNG；关闭窗口时本机服务仍由主进程持有。
  tray = new Tray(nativeImage.createFromPath(join(__dirname, '../../resources/tray.png')))
  tray.setToolTip('Nexora ERP')
  tray.on('double-click', () => {
    if (!mainWindow) createWindow()
    else mainWindow.show()
  })
  updateTray()
}

function updateTray(): void {
  if (!tray) return
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '打开 Nexora ERP', click: () => { if (!mainWindow) createWindow(); else mainWindow.show() } },
    { label: '停止本机服务', enabled: hostStatus().running, click: () => { void stopHost().then(updateTray) } },
    { type: 'separator' },
    { label: '退出', click: () => app.quit() }
  ]))
}

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
  try { loadConnections() }
  catch (error) { startupError = error instanceof Error ? error.message : '连接配置无法读取' }
  ensureTray()
  // 只接受本应用窗口发来的版本查询，避免暴露通用 IPC 通道。
  ipcMain.handle('app:get-version', (event) => {
    assertMainWindow(event)
    return app.getVersion()
  })

  createWindow()
  ipcMain.handle('backend:get-health', (event) => {
    assertMainWindow(event)
    return getBackendHealth()
  })
  ipcMain.handle('erp:call', (event, action: keyof ErpOperations, payload: unknown) => {
    // 业务通道仅接受当前主窗口主框架的调用。
    assertMainWindow(event)
    return callBackend(action, payload)
  })
  ipcMain.handle('connection:startup', async (event) => {
    assertMainWindow(event)
    if (startupError) return { status: 'offline', message: startupError }
    const state = await resume()
    updateTray()
    return state
  })
  ipcMain.handle('connection:recent', (event) => { assertMainWindow(event); return recentProfiles() })
  ipcMain.handle('connection:prepare', (event, address: string, port: number) => {
    assertMainWindow(event); return prepareConnection(address, port)
  })
  ipcMain.handle('connection:approve', (event, id: string, fingerprint: string) => {
    assertMainWindow(event); return approveConnection(id, fingerprint)
  })
  ipcMain.handle('connection:activate', (event, id: string) => {
    assertMainWindow(event); return activateSaved(id)
  })
  ipcMain.handle('connection:disconnect', (event) => { assertMainWindow(event); disconnect() })
  ipcMain.handle('host:create', async (event, input: HostInput) => {
    assertMainWindow(event)
    const result = await createHost(input)
    updateTray()
    return result
  })
  ipcMain.handle('host:finish-setup', async (event, username: string, password: string) => {
    assertMainWindow(event)
    await finishHostSetup(username, password)
    updateTray()
  })
  ipcMain.handle('host:default-dir', (event) => {
    assertMainWindow(event)
    return join(app.getPath('home'), '.nexora-erp')
  })
  ipcMain.handle('host:choose-dir', async (event) => {
    assertMainWindow(event)
    if (!mainWindow) return null
    const selection = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory', 'createDirectory'] })
    return selection.canceled ? null : selection.filePaths[0] ?? null
  })
  ipcMain.handle('host:restart', async (event) => {
    assertMainWindow(event)
    const result = await restartHost()
    updateTray()
    return result
  })
  ipcMain.handle('host:stop', async (event) => { assertMainWindow(event); await stopHost(); updateTray() })
  ipcMain.handle('host:status', (event) => {
    assertMainWindow(event)
    return { ...hostStatus(), fingerprint: hostFingerprint() }
  })
  ipcMain.handle('discovery:start', (event) => {
    assertMainWindow(event)
    startDiscovery((results) => mainWindow?.webContents.send('discovery:update', results))
  })
  ipcMain.handle('discovery:stop', (event) => { assertMainWindow(event); stopDiscovery() })
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  // 正在托管本机服务时，各平台都由托盘维持进程；普通客户端遵循系统关闭习惯。
  if (process.platform !== 'darwin' && !hostStatus().running) app.quit()
})

app.on('before-quit', () => shutdownConnections())
