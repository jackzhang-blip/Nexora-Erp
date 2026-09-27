import { app } from 'electron'
import { execFile } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { HostInput } from '../shared/desktop-api'

export interface ManagedStatus {
  configured: boolean
  running: boolean
  name?: string
  dataDir?: string
  port?: number
}
type HostAction = 'install' | 'upgrade' | 'start' | 'stop'

function executable(): string {
  return join(process.resourcesPath, 'backend-service',
    process.platform === 'win32' ? 'nexora-server.exe' : 'nexora-server')
}

function run(command: string, args: string[], timeout = 30000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout, windowsHide: true, maxBuffer: 1024 * 1024 }, (error, stdout, stderr) => {
      if (error) reject(new Error(stderr.trim() || error.message))
      else resolve(stdout)
    })
  })
}

function shellQuote(value: string): string {
  return `'${value.replaceAll("'", "'\\''")}'`
}

function windowsQuote(value: string): string {
  // CreateProcess 的反斜杠和引号规则必须成对处理，避免含空格路径被拆开。
  return `"${value.replace(/(\\*)"/g, '$1$1\\"').replace(/\\+$/g, '$&$&')}"`
}

async function runElevated(action: HostAction, requestPath?: string): Promise<void> {
  const binary = executable()
  const args = action === 'install'
    ? ['install', '--request', requestPath!, '--source', join(process.resourcesPath, 'backend-service')]
    : action === 'upgrade' ? ['upgrade', '--source', join(process.resourcesPath, 'backend-service')] : [action]
  if (process.platform === 'darwin') {
    const command = [binary, ...args].map(shellQuote).join(' ')
    // 仅固定的主机管理命令申请管理员权限，不把管理员密码交给应用。
    await run('osascript', ['-e', `do shell script ${JSON.stringify(command)} with administrator privileges`], 120000)
  } else if (process.platform === 'win32') {
    const commandLine = args.map(windowsQuote).join(' ')
    const quotePs = (value: string): string => `'${value.replaceAll("'", "''")}'`
    const script = `$p = Start-Process -FilePath ${quotePs(binary)} -ArgumentList ${quotePs(commandLine)} -Verb RunAs -Wait -PassThru; exit $p.ExitCode`
    const encoded = Buffer.from(script, 'utf16le').toString('base64')
    await run('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], 120000)
  } else {
    throw new Error('固定主机仅支持 Windows 和 macOS')
  }
}

export async function managedHostStatus(): Promise<ManagedStatus> {
  if (!app.isPackaged) return { configured: false, running: false }
  const raw = await run(executable(), ['status'], 10000)
  const parsed: unknown = JSON.parse(raw)
  const status = parsed && typeof parsed === 'object' && 'data_dir' in parsed
    ? { ...(parsed as Record<string, unknown>), dataDir: parsed.data_dir } : parsed
  if (!status || typeof status !== 'object' || !('configured' in status)
    || !('running' in status) || typeof status.configured !== 'boolean'
    || typeof status.running !== 'boolean'
    || (status.configured && (!('name' in status) || typeof status.name !== 'string'
      || !('dataDir' in status) || typeof status.dataDir !== 'string'
      || !('port' in status) || typeof status.port !== 'number'))) {
    throw new Error('系统服务状态格式无效')
  }
  return status as ManagedStatus
}

export async function installManagedHost(input: Pick<HostInput, 'name' | 'dataDir' | 'port'>): Promise<void> {
  if (!app.isPackaged) throw new Error('开发模式不能安装系统服务，请先生成内部安装包')
  const directory = mkdtempSync(join(tmpdir(), 'nexora-host-request-'))
  const request = join(directory, 'host.json')
  try {
    // 提权进程仅接收无密码配置；管理员账号密码仍由现有 HTTPS 初始化接口传递。
    writeFileSync(request, JSON.stringify({ name: input.name, data_dir: input.dataDir, port: input.port }),
      { mode: 0o600 })
    await runElevated('install', request)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}

export async function startManagedHost(): Promise<void> { await runElevated('start') }
export async function stopManagedHost(): Promise<void> { await runElevated('stop') }
export async function upgradeManagedHost(): Promise<void> { await runElevated('upgrade') }
