import { app } from 'electron'
import { spawn, type ChildProcess } from 'node:child_process'
import { X509Certificate } from 'node:crypto'
import { lookup } from 'node:dns/promises'
import { existsSync, readFileSync, writeFileSync, renameSync, mkdirSync } from 'node:fs'
import { isIP } from 'node:net'
import { isAbsolute, join, parse, resolve } from 'node:path'
import { connect as tlsConnect } from 'node:tls'
import Bonjour from 'bonjour-service'
import type { Browser, Service } from 'bonjour-service'
import { callBackend, getBackendHealth, getServerInfo, selectBackend, type BackendTarget } from './backend'
import type { ConnectionCandidate, DiscoveryResult, HostInput, ServerProfile, StartupState } from '../shared/desktop-api'

interface StoredProfile extends ServerProfile { certificate: string }
interface HostConfig { name: string; port: number; dataDir: string; enabled?: boolean }
interface Config { host?: HostConfig; activeId?: string; recent: StoredProfile[] }

let config: Config = { recent: [] }
let service: ChildProcess | null = null
let stoppingService: Promise<void> | null = null
let bonjour: Bonjour | null = null
let browser: Browser | null = null
let advertisement: Service | null = null
let discovered: DiscoveryResult[] = []
let pending: StoredProfile | null = null

function configFile(): string { return join(app.getPath('userData'), 'connections.json') }

function save(): void {
  // 连接档案不包含密码或登录令牌，证书和地址只写入当前用户的配置目录。
  const file = configFile()
  mkdirSync(app.getPath('userData'), { recursive: true })
  const temporary = `${file}.tmp`
  writeFileSync(temporary, JSON.stringify(config, null, 2), { mode: 0o600 })
  renameSync(temporary, file)
}

export function loadConnections(): void {
  if (!existsSync(configFile())) return
  try {
    const parsed: unknown = JSON.parse(readFileSync(configFile(), 'utf8'))
    if (parsed && typeof parsed === 'object' && 'recent' in parsed && Array.isArray(parsed.recent)) {
      config = parsed as Config
    }
  } catch {
    throw new Error('连接配置无法读取，请检查用户数据目录中的 connections.json')
  }
}

function publicProfile(profile: StoredProfile): ServerProfile {
  const { certificate: _certificate, ...publicPart } = profile
  return publicPart
}

export function recentProfiles(): ServerProfile[] { return config.recent.map(publicProfile) }
export function hostStatus(): { configured: boolean; running: boolean } {
  return { configured: !!config.host, running: !!service && service.exitCode === null }
}

function localAddress(address: string): boolean {
  if (isIP(address) === 4) {
    const parts = address.split('.').map(Number)
    return parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168)
      || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31)
      || (parts[0] === 169 && parts[1] === 254)
  }
  if (isIP(address) === 6) {
    const lower = address.toLowerCase()
    return lower === '::1' || lower.startsWith('fe80:') || lower.startsWith('fc') || lower.startsWith('fd')
  }
  return false
}

async function resolveAddress(raw: string): Promise<string> {
  const host = raw.trim().replace(/\.$/, '')
  if (!host || host.includes('/') || host.includes('@') || host.includes(':') && isIP(host) !== 6) {
    throw new Error('请输入局域网 IP 地址或主机名，不要包含协议和路径')
  }
  const results = isIP(host) ? [{ address: host }] : await lookup(host, { all: true })
  const chosen = results.find(({ address }) => localAddress(address))
  if (!chosen) throw new Error('地址不在本机或局域网内')
  return chosen.address
}

function certificateFromRaw(raw: Buffer): string {
  const encoded = raw.toString('base64').match(/.{1,64}/g)?.join('\n') ?? ''
  return `-----BEGIN CERTIFICATE-----\n${encoded}\n-----END CERTIFICATE-----\n`
}

async function inspectCertificate(host: string, port: number): Promise<{ id: string; certificate: string; fingerprint: string }> {
  return new Promise((resolvePromise, rejectPromise) => {
    // 此握手绝不发送账号或令牌；用户核对指纹后，正式请求才信任此证书。
    const socket = tlsConnect({ host, port, rejectUnauthorized: false, timeout: 5000 }, () => {
      const peer = socket.getPeerCertificate(true)
      socket.end()
      if (!peer.raw) return rejectPromise(new Error('服务端没有提供 TLS 证书'))
      const certificate = new X509Certificate(peer.raw)
      const id = /DNS:nexora-([0-9a-f-]{36})\.local/i.exec(certificate.subjectAltName ?? '')?.[1]
      if (!id) return rejectPromise(new Error('服务端证书不是 Nexora 实例证书'))
      resolvePromise({ id, certificate: certificateFromRaw(peer.raw), fingerprint: certificate.fingerprint256 })
    })
    socket.on('timeout', () => socket.destroy(new Error('连接超时')))
    socket.on('error', rejectPromise)
  })
}

async function inspectServer(address: string, port: number): Promise<StoredProfile> {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('端口必须在 1 到 65535 之间')
  const host = await resolveAddress(address)
  const certificate = await inspectCertificate(host, port)
  const target: BackendTarget = { host, port, instanceId: certificate.id, certificate: certificate.certificate }
  const info = await getServerInfo(target)
  if (!info.ready) throw new Error('此服务端尚未完成管理员初始化')
  if (!compatibleVersion(info.version)) throw new Error('服务端与客户端版本不兼容')
  return { id: info.id, name: info.name, host, port, fingerprint: certificate.fingerprint,
    version: info.version, isLocal: false, certificate: certificate.certificate }
}

function compatibleVersion(version: string): boolean {
  // 早期 0.x 版本的小版本可能改动接口，连接时要求主次版本一致。
  return version.split('.').slice(0, 2).join('.') === app.getVersion().split('.').slice(0, 2).join('.')
}

export async function prepareConnection(address: string, port: number): Promise<ConnectionCandidate> {
  const profile = await inspectServer(address, port)
  const known = config.recent.find((entry) => entry.id === profile.id)
  pending = profile
  return { ...publicProfile(profile), trusted: known?.fingerprint === profile.fingerprint,
    changed: !!known && known.fingerprint !== profile.fingerprint }
}

export function approveConnection(id: string, fingerprint: string): ServerProfile {
  if (!pending || pending.id !== id || pending.fingerprint !== fingerprint) throw new Error('连接核验已过期，请重新检测')
  const profile = pending
  pending = null
  config.recent = [profile, ...config.recent.filter((entry) => entry.id !== profile.id)].slice(0, 8)
  config.activeId = profile.id
  save()
  selectBackend({ host: profile.host, port: profile.port, instanceId: profile.id, certificate: profile.certificate })
  return publicProfile(profile)
}

export async function activateSaved(id: string): Promise<ServerProfile> {
  const profile = config.recent.find((entry) => entry.id === id)
  if (!profile) throw new Error('未找到保存的服务端')
  const actual = await inspectCertificate(profile.host, profile.port)
  if (actual.fingerprint !== profile.fingerprint || actual.id !== profile.id) {
    throw new Error('服务端证书已变化，请对照服务端屏幕重新核验后手动连接')
  }
  const info = await getServerInfo({ host: profile.host, port: profile.port,
    instanceId: profile.id, certificate: profile.certificate })
  if (!compatibleVersion(info.version)) throw new Error('服务端与客户端版本不兼容')
  profile.name = info.name
  profile.version = info.version
  config.activeId = id
  config.recent = [profile, ...config.recent.filter((entry) => entry.id !== id)]
  save()
  selectBackend({ host: profile.host, port: profile.port, instanceId: profile.id, certificate: profile.certificate })
  return publicProfile(profile)
}

export function disconnect(): void {
  config.activeId = undefined
  save()
  selectBackend(null)
}

function backendCommand(host: HostConfig): { command: string; args: string[]; cwd?: string } {
  const args = ['--data-dir', host.dataDir, '--name', host.name, '--port', String(host.port)]
  if (app.isPackaged) {
    const executable = join(process.resourcesPath, 'backend-service',
      process.platform === 'win32' ? 'nexora-server.exe' : 'nexora-server')
    return { command: executable, args }
  }
  return { command: process.env.NEXORA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
    args: ['-m', 'app.server', ...args],
    cwd: join(app.getAppPath(), 'backend') }
}

async function startHost(): Promise<ServerProfile> {
  if (!config.host) throw new Error('本机尚未配置服务端')
  // 停止后立即重新启动时，先等待旧进程释放监听端口。
  if (stoppingService) await stoppingService
  if (!service || service.exitCode !== null) {
    const launch = backendCommand(config.host)
    const child = spawn(launch.command, launch.args, { cwd: launch.cwd, stdio: ['ignore', 'ignore', 'pipe'],
      windowsHide: true })
    service = child
    let failure = ''
    child.stderr?.on('data', (data: Buffer) => { failure = (failure + data.toString()).slice(-3000) })
    child.on('error', (error) => { failure = error.message })
    child.on('exit', () => {
      if (service === child) { advertisement?.stop(); advertisement = null }
    })
    // 服务端需要先生成证书和迁移数据库，再由健康接口证实已经监听端口。
    for (let attempt = 0; attempt < 60; attempt += 1) {
      if (child.exitCode !== null || failure.includes('Error') || failure.includes('error')) {
        throw new Error(`本机服务启动失败：${failure || '进程已退出'}`)
      }
      try {
        const certificate = await inspectCertificate('127.0.0.1', config.host.port)
        const certificateFile = join(config.host.dataDir, 'server.crt')
        if (!existsSync(certificateFile) || readFileSync(certificateFile, 'utf8') !== certificate.certificate) {
          throw new Error('监听端口已被其他程序占用')
        }
        const target: BackendTarget = { host: '127.0.0.1', port: config.host.port,
          instanceId: certificate.id, certificate: certificate.certificate }
        const info = await getServerInfo(target)
        const profile: StoredProfile = { id: info.id, name: info.name, host: '127.0.0.1',
          port: config.host.port, fingerprint: certificate.fingerprint, version: info.version,
          isLocal: true, certificate: certificate.certificate }
        config.recent = [profile, ...config.recent.filter((entry) => entry.id !== profile.id)].slice(0, 8)
        save()
        if (info.ready) advertise(profile)
        return publicProfile(profile)
      } catch (error) {
        if (error instanceof Error && error.message.includes('已被其他程序占用')) throw error
        await new Promise((done) => setTimeout(done, 250))
      }
    }
    throw new Error(`本机服务启动超时。${failure}`)
  }
  const profile = config.recent.find((entry) => entry.isLocal)
  if (!profile) throw new Error('本机服务连接档案缺失')
  return publicProfile(profile)
}

function advertise(profile: ServerProfile): void {
  if (advertisement) return
  bonjour ??= new Bonjour()
  // 只广播公开的实例标识，不在 mDNS 中放账号、证书或业务资料。
  advertisement = bonjour.publish({ name: profile.name, type: 'nexora', protocol: 'tcp',
    port: profile.port, txt: { id: profile.id, version: profile.version } })
}

export async function createHost(input: HostInput): Promise<ServerProfile> {
  const name = input.name.trim()
  if (!name || name.length > 80) throw new Error('实例名称须为 1 到 80 个字符')
  if (!Number.isInteger(input.port) || input.port < 1 || input.port > 65535) throw new Error('服务端口无效')
  if (!input.dataDir || !isAbsolute(input.dataDir) || resolve(input.dataDir) === parse(resolve(input.dataDir)).root) {
    throw new Error('请选择明确的数据目录')
  }
  if (!/^[A-Za-z0-9_]{3,40}$/.test(input.username) || input.password.length < 12 || input.password.length > 128) {
    throw new Error('管理员账号须为 3 到 40 位英文、数字或下划线，密码至少 12 位')
  }
  if (config.host) throw new Error('此电脑已配置服务端，请到设置中启动或管理')
  config.host = { name, port: input.port, dataDir: resolve(input.dataDir), enabled: true }
  save()
  const profile = await startHost()
  await activateSaved(profile.id)
  const info = await getServerInfo()
  if (!info.ready) {
    await finishHostSetup(input.username, input.password)
  }
  return profile
}

export async function finishHostSetup(username: string, password: string): Promise<void> {
  if (!config.host || !service || service.exitCode !== null) throw new Error('本机服务尚未运行')
  const profile = config.recent.find((entry) => entry.isLocal)
  if (!profile || config.activeId !== profile.id) throw new Error('请先连接本机服务')
  await callBackend('bootstrap', { username, password })
  advertise(profile)
}

export async function resume(): Promise<StartupState> {
  try {
    if (config.host && config.host.enabled !== false) await startHost()
    if (!config.activeId) return { status: 'welcome' }
    const profile = await activateSaved(config.activeId)
    const health = await getBackendHealth()
    if (!health.connected) throw new Error(health.message)
    if (!(await getServerInfo()).ready && profile.isLocal) return { status: 'needs_setup', server: profile }
    return { status: 'connected', server: profile }
  } catch (error) {
    return { status: 'offline', message: error instanceof Error ? error.message : '无法恢复上次连接',
      server: config.recent.find((entry) => entry.id === config.activeId)
        ? publicProfile(config.recent.find((entry) => entry.id === config.activeId)!) : undefined }
  }
}

export async function restartHost(): Promise<ServerProfile> {
  if (!config.host) throw new Error('本机尚未配置服务端')
  config.host.enabled = true
  save()
  const profile = await startHost()
  await activateSaved(profile.id)
  return profile
}

export async function stopHost(persistStopped = true): Promise<void> {
  if (persistStopped && config.host) {
    // 用户主动停止会持续生效；应用退出时仅结束进程，不改下次启动的选择。
    config.host.enabled = false
    save()
  }
  advertisement?.stop()
  advertisement = null
  const child = service
  service = null
  if (config.activeId && config.recent.find((entry) => entry.id === config.activeId)?.isLocal) selectBackend(null)
  if (!child || child.exitCode !== null) return
  child.kill()
  // 监听 exit 比固定延时可靠；超时后允许界面继续给出可恢复的端口错误。
  const pending = new Promise<void>((resolvePromise) => {
    const timer = setTimeout(resolvePromise, 5000)
    child.once('exit', () => { clearTimeout(timer); resolvePromise() })
  })
  stoppingService = pending
  await pending
  if (stoppingService === pending) stoppingService = null
}

export function hostFingerprint(): string | null {
  return config.recent.find((entry) => entry.isLocal)?.fingerprint ?? null
}

export function startDiscovery(onUpdate: (results: DiscoveryResult[]) => void): void {
  stopDiscovery()
  discovered = []
  bonjour ??= new Bonjour()
  browser = bonjour.find({ type: 'nexora', protocol: 'tcp' })
  browser.on('up', (serviceEntry) => {
    const address = serviceEntry.addresses?.find((candidate) => localAddress(candidate) && isIP(candidate) === 4)
    if (!address) return
    void inspectServer(address, serviceEntry.port).then((profile) => {
      const result: DiscoveryResult = { ...publicProfile(profile), online: true }
      discovered = [result, ...discovered.filter((entry) => entry.id !== result.id)]
      onUpdate([...discovered])
    }).catch(() => { /* 非 Nexora 或尚未就绪的服务不进入结果列表。 */ })
  })
  browser.on('down', (serviceEntry) => {
    const id = serviceEntry.txt?.id
    discovered = discovered.map((entry) => entry.id === id ? { ...entry, online: false } : entry)
    onUpdate([...discovered])
  })
  onUpdate([])
}

export function stopDiscovery(): void { browser?.stop(); browser = null }

export function shutdownConnections(): void {
  stopDiscovery()
  void stopHost(false)
  bonjour?.destroy()
  bonjour = null
}
