import type { BackendHealth } from '../shared/desktop-api'
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { join } from 'node:path'
import { existsSync } from 'node:fs'

export async function getBackendHealth(baseUrl?: string, timeout = 5000): Promise<BackendHealth> {
  try {
    // 地址只由主进程环境配置，页面不能传入任意 URL。
    const base = new URL(baseUrl || process.env.NEXORA_API_URL || 'http://127.0.0.1:8000')
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password) {
      return { connected: false, message: '后端地址配置无效，请检查 NEXORA_API_URL。' }
    }
    const response = await fetch(new URL('/api/v1/health', base), {
      signal: AbortSignal.timeout(timeout),
      redirect: 'error'
    })
    if (!response.ok) {
      return { connected: false, message: `后端返回 HTTP ${response.status}，请检查服务后重试。` }
    }
    const data: unknown = await response.json()
    if (!data || typeof data !== 'object' || !('status' in data) || data.status !== 'ok'
      || !('service' in data) || data.service !== 'nexora-api'
      || !('version' in data) || typeof data.version !== 'string' || !data.version.trim()) {
      return { connected: false, message: '后端响应格式不匹配，请确认运行的是 Nexora API。' }
    }
    return { connected: true, version: data.version }
  } catch {
    return { connected: false, message: '后端暂时不可用，请重试；持续失败时请重启应用。' }
  }
}

export function createBackendService(backendDirectory: string) {
  let child: ChildProcessWithoutNullStreams | undefined
  let starting: Promise<BackendHealth> | undefined
  let endpoint: string | undefined
  let stopping = false

  async function stopChild(): Promise<void> {
    const process = child
    if (!process) return
    await new Promise<void>((resolve) => {
      const timer = setTimeout(() => { process.kill(); resolve() }, 6000)
      process.once('close', () => { clearTimeout(timer); resolve() })
      // 管道 EOF 同时覆盖 Windows 虚拟环境启动器下的 Python 子进程。
      process.stdin.end()
    })
    if (child === process) { child = undefined; endpoint = undefined }
  }

  async function start(): Promise<BackendHealth> {
    const python = process.env.NEXORA_PYTHON || join(backendDirectory, '.venv',
      process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
    if (!existsSync(python)) {
      return { connected: false, message: '后端运行环境未安装，请按开发说明安装 Python 依赖后重试。' }
    }
    let output = ''
    let failure = false
    const processHandle = spawn(python, ['-u', join(backendDirectory, 'run_desktop.py'),
      '--parent-pid', String(process.pid)], {
      cwd: backendDirectory, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe']
    })
    child = processHandle
    // 保持监听，避免退出与写管道同时发生时出现未处理错误。
    processHandle.stdin.on('error', () => {})
    processHandle.on('error', () => { failure = true })
    processHandle.on('close', () => {
      failure = true
      if (child === processHandle) { child = undefined; endpoint = undefined }
    })
    processHandle.stderr.on('data', (data: Buffer) => console.error('[FastAPI]', data.toString().trim()))
    processHandle.stdout.on('data', (data: Buffer) => {
      output += data.toString()
      const newline = output.indexOf('\n')
      if (newline < 0) return
      try {
        const { port } = JSON.parse(output.slice(0, newline)) as { port: number }
        if (Number.isInteger(port) && port > 0 && port <= 65535) endpoint = `http://127.0.0.1:${port}`
        else failure = true
      } catch { failure = true }
      output = ''
    })
    const deadline = Date.now() + 15000
    while (!failure && !stopping && Date.now() < deadline) {
      if (endpoint) {
        const health = await getBackendHealth(endpoint, 1000)
        if (health.connected && !failure && !stopping) return health
      }
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
    await stopChild()
    return { connected: false, message: '后端启动失败或超时，请检查 Python 依赖及终端日志，然后重试。' }
  }

  return {
    async check(): Promise<BackendHealth> {
      if (stopping) return { connected: false, message: '应用正在退出。' }
      if (starting) return starting
      if (child && endpoint) return getBackendHealth(endpoint)
      starting = start()
      try { return await starting } finally { starting = undefined }
    },
    async stop(): Promise<void> {
      stopping = true
      await starting
      await stopChild()
    }
  }
}
