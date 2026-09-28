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

function roleCode(payload: unknown): string {
  // 自定义角色代码写入 URL 前先按服务端规则校验，避免路径注入。
  const code = payload && typeof payload === 'object' ? (payload as Record<string, unknown>).code : undefined
  if (typeof code !== 'string' || !/^[a-z][a-z0-9_]{2,39}$/.test(code)) throw new Error('角色代码无效')
  return code
}

function operation(action: keyof ErpOperations, payload: unknown): { method: string; path: string; body?: unknown } {
  // 明确列出可调用的接口，禁止页面拼接任意后端路径。
  switch (action) {
    case 'setupStatus': return { method: 'GET', path: '/api/v1/setup/status' }
    case 'bootstrap': return { method: 'POST', path: '/api/v1/setup/admin', body: payload }
    case 'login': return { method: 'POST', path: '/api/v1/auth/login', body: payload }
    case 'logout': return { method: 'POST', path: '/api/v1/auth/logout' }
    case 'me': return { method: 'GET', path: '/api/v1/auth/me' }
    case 'changePassword': return { method: 'POST', path: '/api/v1/auth/change-password', body: payload }
    case 'permissions': return { method: 'GET', path: '/api/v1/permissions' }
    case 'roles': return { method: 'GET', path: '/api/v1/roles' }
    case 'createRole': return { method: 'POST', path: '/api/v1/roles', body: payload }
    case 'updateRole': return {
      method: 'PUT', path: `/api/v1/roles/${roleCode(payload)}`,
      body: { label: (payload as { label: unknown }).label, permissions: (payload as { permissions: unknown }).permissions }
    }
    case 'users': return { method: 'GET', path: '/api/v1/users' }
    case 'createUser': return { method: 'POST', path: '/api/v1/users', body: payload }
    case 'setUserRoles': return {
      method: 'PUT', path: `/api/v1/users/${positiveId(payload, 'userId')}/roles`,
      body: { roles: (payload as { roles: unknown }).roles }
    }
    case 'setUserStatus': return {
      method: 'PUT', path: `/api/v1/users/${positiveId(payload, 'userId')}/status`,
      body: { is_active: (payload as { is_active: unknown }).is_active }
    }
    case 'resetUserPassword': return {
      method: 'POST', path: `/api/v1/users/${positiveId(payload, 'userId')}/reset-password`,
      body: { password: (payload as { password: unknown }).password }
    }
    case 'suppliers': return { method: 'GET', path: '/api/v1/suppliers' }
    case 'createSupplier': return { method: 'POST', path: '/api/v1/suppliers', body: payload }
    case 'customers': return { method: 'GET', path: '/api/v1/customers' }
    case 'createCustomer': return { method: 'POST', path: '/api/v1/customers', body: payload }
    case 'materials': return { method: 'GET', path: '/api/v1/materials' }
    case 'createMaterial': return { method: 'POST', path: '/api/v1/materials', body: payload }
    case 'warehouses': return { method: 'GET', path: '/api/v1/warehouses' }
    case 'createWarehouse': return { method: 'POST', path: '/api/v1/warehouses', body: payload }
    case 'receipts': return { method: 'GET', path: '/api/v1/receipts' }
    case 'createReceipt': return { method: 'POST', path: '/api/v1/receipts', body: payload }
    case 'postReceipt': return { method: 'POST', path: `/api/v1/receipts/${positiveId(payload, 'receiptId')}/post` }
    case 'reverseReceipt': {
      const receiptId = positiveId(payload, 'receiptId')
      const fields = payload as ErpOperations['reverseReceipt']['input']
      return { method: 'POST', path: `/api/v1/receipts/${receiptId}/reverse`, body: { reason: fields.reason } }
    }
    // 采购退货单编号只能通过正整数校验后进入固定路径。
    case 'purchaseReturns': return { method: 'GET', path: '/api/v1/purchase-returns' }
    case 'receivablesPayables': return { method: 'GET', path: '/api/v1/finance/receivables-payables' }
    case 'financeOverview': return { method: 'GET', path: '/api/v1/finance/overview' }
    case 'financeAccounts': return { method: 'GET', path: '/api/v1/finance/accounts' }
    case 'paymentRecords': return { method: 'GET', path: '/api/v1/finance/payment-records' }
    case 'createPaymentRecord': return { method: 'POST', path: '/api/v1/finance/payment-records', body: payload }
    case 'reversePaymentRecord': return {
      method: 'POST', path: `/api/v1/finance/payment-records/${positiveId(payload, 'paymentId')}/reverse`,
      body: { reason: (payload as { reason: unknown }).reason }
    }
    // BOM 的生命周期操作只接受经校验的单据编号。
    case 'boms': return { method: 'GET', path: '/api/v1/boms' }
    case 'createBom': return { method: 'POST', path: '/api/v1/boms', body: payload }
    case 'activateBom': return { method: 'POST', path: `/api/v1/boms/${positiveId(payload, 'bomId')}/activate` }
    case 'retireBom': return { method: 'POST', path: `/api/v1/boms/${positiveId(payload, 'bomId')}/retire` }
    case 'cancelBom': return { method: 'POST', path: `/api/v1/boms/${positiveId(payload, 'bomId')}/cancel` }
    case 'workOrders': return { method: 'GET', path: '/api/v1/work-orders' }
    case 'createWorkOrder': return { method: 'POST', path: '/api/v1/work-orders', body: payload }
    case 'releaseWorkOrder': return { method: 'POST', path: `/api/v1/work-orders/${positiveId(payload, 'orderId')}/release` }
    case 'cancelWorkOrder': return { method: 'POST', path: `/api/v1/work-orders/${positiveId(payload, 'orderId')}/cancel` }
    case 'materialIssues': return { method: 'GET', path: '/api/v1/material-issues' }
    case 'createMaterialIssue': return { method: 'POST', path: '/api/v1/material-issues', body: payload }
    case 'postMaterialIssue': return { method: 'POST', path: `/api/v1/material-issues/${positiveId(payload, 'issueId')}/post` }
    case 'cancelMaterialIssue': return { method: 'POST', path: `/api/v1/material-issues/${positiveId(payload, 'issueId')}/cancel` }
    case 'materialReturns': return { method: 'GET', path: '/api/v1/material-returns' }
    case 'createMaterialReturn': return { method: 'POST', path: '/api/v1/material-returns', body: payload }
    case 'postMaterialReturn': return { method: 'POST', path: `/api/v1/material-returns/${positiveId(payload, 'returnId')}/post` }
    case 'cancelMaterialReturn': return { method: 'POST', path: `/api/v1/material-returns/${positiveId(payload, 'returnId')}/cancel` }
    case 'productionCompletions': return { method: 'GET', path: '/api/v1/production-completions' }
    case 'createProductionCompletion': return { method: 'POST', path: '/api/v1/production-completions', body: payload }
    case 'inspectProductionCompletion': {
      const completionId = positiveId(payload, 'completionId')
      const fields = payload as ErpOperations['inspectProductionCompletion']['input']
      // 路径编号只用于定位单据，请求体仅发送质检接口确认的正式字段。
      return { method: 'POST', path: `/api/v1/production-completions/${completionId}/inspect`,
        body: { accepted_quantity: fields.accepted_quantity, qc_note: fields.qc_note } }
    }
    case 'postProductionCompletion': return { method: 'POST', path: `/api/v1/production-completions/${positiveId(payload, 'completionId')}/post` }
    case 'cancelProductionCompletion': return { method: 'POST', path: `/api/v1/production-completions/${positiveId(payload, 'completionId')}/cancel` }
    case 'reverseProductionCompletion': {
      const completionId = positiveId(payload, 'completionId')
      const fields = payload as ErpOperations['reverseProductionCompletion']['input']
      // 单据编号只用于受限路径，请求体只传冲销原因。
      return { method: 'POST', path: `/api/v1/production-completions/${completionId}/reverse`,
        body: { reason: fields.reason } }
    }
    case 'productionCosts': return { method: 'GET', path: '/api/v1/production-costs' }
    case 'recordMaterialValuation': return { method: 'POST', path: '/api/v1/production-costs/material-valuations', body: payload }
    case 'recordProductionCharge': return { method: 'POST', path: '/api/v1/production-costs/charges', body: payload }
    case 'reverseProductionCost': {
      const entryId = positiveId(payload, 'entryId')
      const fields = payload as ErpOperations['reverseProductionCost']['input']
      // 记录编号只进入固定路径，请求体仅包含冲销原因。
      return { method: 'POST', path: `/api/v1/production-costs/${entryId}/reverse`, body: { reason: fields.reason } }
    }
    case 'createPurchaseReturn': return { method: 'POST', path: '/api/v1/purchase-returns', body: payload }
    case 'postPurchaseReturn': return { method: 'POST', path: `/api/v1/purchase-returns/${positiveId(payload, 'returnId')}/post` }
    case 'cancelPurchaseReturn': return { method: 'POST', path: `/api/v1/purchase-returns/${positiveId(payload, 'returnId')}/cancel` }
    case 'reversePurchaseReturn': {
      const returnId = positiveId(payload, 'returnId')
      const fields = payload as ErpOperations['reversePurchaseReturn']['input']
      return { method: 'POST', path: `/api/v1/purchase-returns/${returnId}/reverse`, body: { reason: fields.reason } }
    }
    case 'purchaseOrders': return { method: 'GET', path: '/api/v1/purchase-orders' }
    case 'createPurchaseOrder': return { method: 'POST', path: '/api/v1/purchase-orders', body: payload }
    case 'confirmPurchaseOrder': return { method: 'POST', path: `/api/v1/purchase-orders/${positiveId(payload, 'orderId')}/confirm` }
    case 'cancelPurchaseOrder': return { method: 'POST', path: `/api/v1/purchase-orders/${positiveId(payload, 'orderId')}/cancel` }
    case 'salesOrders': return { method: 'GET', path: '/api/v1/sales-orders' }
    case 'createSalesOrder': return { method: 'POST', path: '/api/v1/sales-orders', body: payload }
    case 'confirmSalesOrder': return { method: 'POST', path: `/api/v1/sales-orders/${positiveId(payload, 'orderId')}/confirm` }
    case 'cancelSalesOrder': return { method: 'POST', path: `/api/v1/sales-orders/${positiveId(payload, 'orderId')}/cancel` }
    case 'shipments': return { method: 'GET', path: '/api/v1/shipments' }
    case 'createShipment': return { method: 'POST', path: '/api/v1/shipments', body: payload }
    case 'postShipment': return { method: 'POST', path: `/api/v1/shipments/${positiveId(payload, 'shipmentId')}/post` }
    case 'cancelShipment': return { method: 'POST', path: `/api/v1/shipments/${positiveId(payload, 'shipmentId')}/cancel` }
    // 退货只能调用固定路径，单据编号先校验再拼接，避免渲染层指定任意 URL。
    case 'salesReturns': return { method: 'GET', path: '/api/v1/sales-returns' }
    case 'createSalesReturn': return { method: 'POST', path: '/api/v1/sales-returns', body: payload }
    case 'postSalesReturn': return { method: 'POST', path: `/api/v1/sales-returns/${positiveId(payload, 'returnId')}/post` }
    case 'cancelSalesReturn': return { method: 'POST', path: `/api/v1/sales-returns/${positiveId(payload, 'returnId')}/cancel` }
    case 'reverseSalesReturn': {
      const returnId = positiveId(payload, 'returnId')
      const fields = payload as ErpOperations['reverseSalesReturn']['input']
      return { method: 'POST', path: `/api/v1/sales-returns/${returnId}/reverse`, body: { reason: fields.reason } }
    }
    case 'transfers': return { method: 'GET', path: '/api/v1/transfers' }
    case 'createTransfer': return { method: 'POST', path: '/api/v1/transfers', body: payload }
    case 'postTransfer': return { method: 'POST', path: `/api/v1/transfers/${positiveId(payload, 'transferId')}/post` }
    case 'reverseTransfer': {
      const transferId = positiveId(payload, 'transferId')
      const fields = payload as ErpOperations['reverseTransfer']['input']
      // 调拨冲销只接收原因，目标路径固定且单据编号必须为正整数。
      return { method: 'POST', path: `/api/v1/transfers/${transferId}/reverse`, body: { reason: fields.reason } }
    }
    case 'stocktakes': return { method: 'GET', path: '/api/v1/stocktakes' }
    case 'createStocktake': return { method: 'POST', path: '/api/v1/stocktakes', body: payload }
    case 'postStocktake': return { method: 'POST', path: `/api/v1/stocktakes/${positiveId(payload, 'stocktakeId')}/post` }
    case 'cancelStocktake': return { method: 'POST', path: `/api/v1/stocktakes/${positiveId(payload, 'stocktakeId')}/cancel` }
    case 'reverseStocktake': {
      const stocktakeId = positiveId(payload, 'stocktakeId')
      const fields = payload as ErpOperations['reverseStocktake']['input']
      // 冲销只允许发送原因，单据编号由主进程校验后拼接到固定路径。
      return { method: 'POST', path: `/api/v1/stocktakes/${stocktakeId}/reverse`, body: { reason: fields.reason } }
    }
    case 'stock': return { method: 'GET', path: payload && typeof payload === 'object' && 'warehouseId' in payload && payload.warehouseId !== undefined
      ? `/api/v1/stock?warehouse_id=${positiveId(payload, 'warehouseId')}` : '/api/v1/stock' }
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
  if (action === 'logout' || action === 'changePassword') sessionToken = null
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
