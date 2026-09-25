import type { BackendHealth } from '../shared/desktop-api'
import type { ErpOperations } from '../shared/erp-api'
import { request as httpsRequest } from 'node:https'

export interface BackendTarget {
  host: string
  port: number
  instanceId: string
  certificate: string
}

let sessionToken: string | null = null
let selectedTarget: BackendTarget | null = null

export function selectBackend(target: BackendTarget | null): void {
  // 切换服务端必须丢弃旧服务端令牌，避免把会话发到另一台机器。
  sessionToken = null
  selectedTarget = target
}

function backendBase(): URL {
  const base = new URL(process.env.NEXORA_API_URL || 'http://127.0.0.1:8000')
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password
    || !['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname)) {
    throw new Error('后端地址配置无效，请检查 NEXORA_API_URL。')
  }
  return base
}

async function sendRequest(path: string, method: string, headers: Record<string, string>, body?: unknown,
                           timeout = 10000, targetOverride?: BackendTarget): Promise<Response> {
  const target = targetOverride ?? selectedTarget
  if (!target) {
    // 开发环境仍支持显式配置的旧地址，桌面向导连接一律走证书固定的 HTTPS。
    return fetch(new URL(path, backendBase()), {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeout), redirect: 'error'
    })
  }
  return new Promise((resolve, reject) => {
    const req = httpsRequest({
      hostname: target.host, port: target.port, path, method, headers,
      ca: target.certificate, servername: `nexora-${target.instanceId}.local`,
      rejectUnauthorized: true, timeout
    }, (incoming) => {
      const chunks: Buffer[] = []
      incoming.on('data', (chunk: Buffer) => chunks.push(chunk))
      incoming.on('end', () => resolve(new Response(incoming.statusCode === 204 ? null : Buffer.concat(chunks), {
        status: incoming.statusCode ?? 500
      })))
    })
    req.on('timeout', () => req.destroy(new Error('连接超时')))
    req.on('error', reject)
    if (body !== undefined) req.write(JSON.stringify(body))
    req.end()
  })
}

export async function getServerInfo(target?: BackendTarget): Promise<{ id: string; name: string; version: string; ready: boolean }> {
  const response = await sendRequest('/api/v1/server/info', 'GET', {}, undefined, 5000, target)
  if (!response.ok) throw new Error(`服务端身份检查失败（HTTP ${response.status}）`)
  const info: unknown = await response.json()
  if (!info || typeof info !== 'object' || !('id' in info) || typeof info.id !== 'string'
    || !('name' in info) || typeof info.name !== 'string'
    || !('version' in info) || typeof info.version !== 'string'
    || !('ready' in info) || typeof info.ready !== 'boolean') {
    throw new Error('服务端身份响应格式无效')
  }
  if ((target ?? selectedTarget) && info.id !== (target ?? selectedTarget)?.instanceId) throw new Error('服务端实例身份已变化')
  return info as { id: string; name: string; version: string; ready: boolean }
}

function positiveId(payload: unknown, key: string): number {
  const value = payload && typeof payload === 'object' ? (payload as Record<string, unknown>)[key] : undefined
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('记录编号无效')
  }
  return value
}

function operation(action: keyof ErpOperations, payload: unknown): { method: string; path: string; body?: unknown } {
  // 明确列出可调用的接口，禁止页面拼接任意后端路径。
  switch (action) {
    case 'setupStatus': return { method: 'GET', path: '/api/v1/setup/status' }
    case 'bootstrap': return { method: 'POST', path: '/api/v1/setup/admin', body: payload }
    case 'login': return { method: 'POST', path: '/api/v1/auth/login', body: payload }
    case 'logout': return { method: 'POST', path: '/api/v1/auth/logout' }
    case 'me': return { method: 'GET', path: '/api/v1/auth/me' }
    case 'roles': return { method: 'GET', path: '/api/v1/roles' }
    case 'users': return { method: 'GET', path: '/api/v1/users' }
    case 'createUser': return { method: 'POST', path: '/api/v1/users', body: payload }
    case 'setUserRoles': return {
      method: 'PUT', path: `/api/v1/users/${positiveId(payload, 'userId')}/roles`,
      body: { roles: (payload as { roles: unknown }).roles }
    }
    case 'suppliers': return { method: 'GET', path: '/api/v1/suppliers' }
    case 'createSupplier': return { method: 'POST', path: '/api/v1/suppliers', body: payload }
    case 'materials': return { method: 'GET', path: '/api/v1/materials' }
    case 'createMaterial': return { method: 'POST', path: '/api/v1/materials', body: payload }
    case 'receipts': return { method: 'GET', path: '/api/v1/receipts' }
    case 'createReceipt': return { method: 'POST', path: '/api/v1/receipts', body: payload }
    case 'postReceipt': return { method: 'POST', path: `/api/v1/receipts/${positiveId(payload, 'receiptId')}/post` }
    case 'stock': return { method: 'GET', path: '/api/v1/stock' }
    case 'movements': return { method: 'GET', path: '/api/v1/movements' }
    default: throw new Error('不允许的业务操作')
  }
}

export async function callBackend(action: keyof ErpOperations, payload: unknown): Promise<unknown> {
  const request = operation(action, payload)
  const publicAction = action === 'setupStatus' || action === 'bootstrap' || action === 'login'
  if (!publicAction && !sessionToken) throw new Error('请先登录')
  const activeToken = sessionToken
  // 即使本地服务暂时不可达，退出时也立刻丢弃桌面进程持有的令牌。
  if (action === 'logout') sessionToken = null
  let response: Response
  try {
    response = await sendRequest(request.path, request.method, {
        ...(request.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(publicAction ? {} : { Authorization: `Bearer ${activeToken}` })
      }, request.body)
  } catch {
    throw new Error('无法连接服务端，请检查网络、服务状态和证书。')
  }
  const data: unknown = response.status === 204 ? undefined : await response.json().catch(() => undefined)
  if (!response.ok) {
    if (response.status === 401 && !publicAction) sessionToken = null
    const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : undefined
    throw new Error(typeof detail === 'string' ? detail : `请求失败（HTTP ${response.status}）`)
  }
  if (action === 'login') {
    if (!data || typeof data !== 'object' || !('token' in data) || typeof data.token !== 'string'
      || !('user' in data) || !data.user) throw new Error('登录响应格式不匹配')
    sessionToken = data.token
    return data.user
  }
  if (action === 'logout') sessionToken = null
  return data
}

export async function getBackendHealth(): Promise<BackendHealth> {
  try {
    // 地址只由主进程环境配置，页面不能传入任意 URL。
    const response = await sendRequest('/api/v1/health', 'GET', {}, undefined, 5000)
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
  } catch (error) {
    return { connected: false, message: error instanceof Error && error.message.includes('配置无效')
      ? error.message : '无法连接后端，请确认服务已启动、地址正确，然后重试。' }
  }
}
