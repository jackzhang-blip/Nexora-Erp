import assert from 'node:assert/strict'
import { test } from 'node:test'
import { callBackend, getBackendHealth } from '../src/main/backend.ts'

test('后端连接契约与失败处理', async (t) => {
  const originalUrl = process.env.NEXORA_API_URL
  t.after(() => {
    if (originalUrl === undefined) delete process.env.NEXORA_API_URL
    else process.env.NEXORA_API_URL = originalUrl
  })
  process.env.NEXORA_API_URL = 'http://127.0.0.1:8123'
  const fetchMock = t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url.href, 'http://127.0.0.1:8123/api/v1/health')
    assert.equal(options.redirect, 'error')
    assert.ok(options.signal instanceof AbortSignal)
    return Response.json({ status: 'ok', service: 'nexora-api', version: '0.1.0' })
  })
  assert.deepEqual(await getBackendHealth(), { connected: true, version: '0.1.0' })
  for (const data of [null, {}, { status: 'ok', service: 'other', version: '1' }]) {
    fetchMock.mock.mockImplementation(async () => Response.json(data))
    assert.equal((await getBackendHealth()).connected, false)
  }
  fetchMock.mock.mockImplementation(async () => new Response('unavailable', { status: 503 }))
  assert.match((await getBackendHealth()).message, /503/)
  fetchMock.mock.mockImplementation(async () => new Response('invalid json'))
  assert.equal((await getBackendHealth()).connected, false)
  fetchMock.mock.mockImplementation(async () => { throw new Error('connection refused') })
  assert.equal((await getBackendHealth()).connected, false)
  process.env.NEXORA_API_URL = 'file:///tmp/test'
  assert.match((await getBackendHealth()).message, /配置无效/)
})

test('桌面业务接口只转发固定操作且令牌留在主进程', async (t) => {
  const originalUrl = process.env.NEXORA_API_URL
  t.after(() => {
    if (originalUrl === undefined) delete process.env.NEXORA_API_URL
    else process.env.NEXORA_API_URL = originalUrl
  })
  process.env.NEXORA_API_URL = 'http://127.0.0.1:8123'
  const calls = []
  const fetchMock = t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ path: url.pathname, search: url.search, method: options.method, authorization: options.headers.Authorization })
    if (url.pathname.endsWith('/login')) {
      return Response.json({ token: 'private-session-token', user: { id: 1, username: 'admin', roles: ['admin'], permissions: [] } })
    }
    if (url.pathname.endsWith('/logout')) return new Response(null, { status: 204 })
    return Response.json({ id: 1, username: 'admin', roles: ['admin'], permissions: [] })
  })
  const user = await callBackend('login', { username: 'admin', password: 'secure-pass-123' })
  assert.equal(user.username, 'admin')
  assert.equal(JSON.stringify(user).includes('private-session-token'), false)
  await callBackend('me', undefined)
  assert.equal(calls[1].authorization, 'Bearer private-session-token')
  await callBackend('postReceipt', { receiptId: 3 })
  assert.equal(calls[2].path, '/api/v1/receipts/3/post')
  await callBackend('setUserStatus', { userId: 2, is_active: false })
  assert.equal(calls[3].path, '/api/v1/users/2/status')
  await callBackend('updateRole', { code: 'stock_clerk', label: '库存员', permissions: ['inventory.view'] })
  assert.equal(calls[4].path, '/api/v1/roles/stock_clerk')
  // 新增仓库与调拨操作仍经过固定白名单，仓库筛选编号不能拼接任意路径。
  await callBackend('warehouses', undefined)
  assert.equal(calls[5].path, '/api/v1/warehouses')
  await callBackend('postTransfer', { transferId: 6 })
  assert.equal(calls[6].path, '/api/v1/transfers/6/post')
  await callBackend('stock', { warehouseId: 2 })
  assert.equal(calls[7].path, '/api/v1/stock')
  assert.equal(calls[7].search, '?warehouse_id=2')
  await assert.rejects(callBackend('stock', { warehouseId: '../users' }), /记录编号无效/)
  await assert.rejects(callBackend('postTransfer', { transferId: '../users' }), /记录编号无效/)
  // 采购订单确认也只能使用经校验的单据编号。
  await callBackend('confirmPurchaseOrder', { orderId: 9 })
  assert.equal(calls[8].path, '/api/v1/purchase-orders/9/confirm')
  await assert.rejects(callBackend('cancelPurchaseOrder', { orderId: '../users' }), /记录编号无效/)
  // 盘点确认与取消均使用受限的单据编号，不允许页面提供任意接口路径。
  await callBackend('postStocktake', { stocktakeId: 4 })
  assert.equal(calls[9].path, '/api/v1/stocktakes/4/post')
  await assert.rejects(callBackend('cancelStocktake', { stocktakeId: '../users' }), /记录编号无效/)
  // 销售出库只接收固定操作，单据编号由主进程校验后拼接。
  await callBackend('postShipment', { shipmentId: 5 })
  assert.equal(calls[10].path, '/api/v1/shipments/5/post')
  // 退货确认与取消都由主进程限定目标路径和编号。
  await callBackend('salesReturns', undefined)
  assert.equal(calls[11].path, '/api/v1/sales-returns')
  await callBackend('postSalesReturn', { returnId: 7 })
  assert.equal(calls[12].path, '/api/v1/sales-returns/7/post')
  await assert.rejects(callBackend('cancelSalesReturn', { returnId: '../users' }), /记录编号无效/)
  // 采购退货也必须固定接口路径，并拒绝伪造的单据编号。
  await callBackend('purchaseReturns', undefined)
  assert.equal(calls[13].path, '/api/v1/purchase-returns')
  await callBackend('postPurchaseReturn', { returnId: 8 })
  assert.equal(calls[14].path, '/api/v1/purchase-returns/8/post')
  await assert.rejects(callBackend('cancelPurchaseReturn', { returnId: '../users' }), /记录编号无效/)
  // 财务只读查询同样通过主进程的固定路径，不能由页面拼装任意后端地址。
  await callBackend('receivablesPayables', undefined)
  assert.equal(calls[15].path, '/api/v1/finance/receivables-payables')
  await callBackend('financeOverview', undefined)
  assert.equal(calls[16].path, '/api/v1/finance/overview')
  // 收付款与冲销只能调用固定接口，冲销编号在进入路径前校验。
  await callBackend('financeAccounts', undefined)
  assert.equal(calls[17].path, '/api/v1/finance/accounts')
  await callBackend('paymentRecords', undefined)
  assert.equal(calls[18].path, '/api/v1/finance/payment-records')
  await callBackend('reversePaymentRecord', { paymentId: 11, reason: '误录' })
  assert.equal(calls[19].path, '/api/v1/finance/payment-records/11/reverse')
  await assert.rejects(callBackend('reversePaymentRecord', { paymentId: '../users', reason: '误录' }), /记录编号无效/)
  // 生产 BOM 的启停用也只能使用受限的路径和编号。
  await callBackend('boms', undefined)
  assert.equal(calls[20].path, '/api/v1/boms')
  await callBackend('activateBom', { bomId: 12 })
  assert.equal(calls[21].path, '/api/v1/boms/12/activate')
  await assert.rejects(callBackend('retireBom', { bomId: '../users' }), /记录编号无效/)
  // 生产工单列表和下达操作也必须经过主进程的固定路径与正整数编号校验。
  await callBackend('workOrders', undefined)
  assert.equal(calls[22].path, '/api/v1/work-orders')
  await callBackend('releaseWorkOrder', { orderId: 13 })
  assert.equal(calls[23].path, '/api/v1/work-orders/13/release')
  await assert.rejects(callBackend('cancelWorkOrder', { orderId: '../users' }), /记录编号无效/)
  // 领料确认同样只允许固定业务路径，不能拼接外部传入的路径片段。
  await callBackend('materialIssues', undefined)
  assert.equal(calls[24].path, '/api/v1/material-issues')
  await callBackend('postMaterialIssue', { issueId: 14 })
  assert.equal(calls[25].path, '/api/v1/material-issues/14/post')
  await assert.rejects(callBackend('cancelMaterialIssue', { issueId: '../users' }), /记录编号无效/)
  // 退料确认沿受限接口访问固定路径，原领料编号和退料编号不可作为路径片段注入。
  await callBackend('materialReturns', undefined)
  assert.equal(calls[26].path, '/api/v1/material-returns')
  await callBackend('postMaterialReturn', { returnId: 15 })
  assert.equal(calls[27].path, '/api/v1/material-returns/15/post')
  await assert.rejects(callBackend('cancelMaterialReturn', { returnId: '../users' }), /记录编号无效/)
  await assert.rejects(callBackend('confirmSalesOrder', { orderId: '../users' }), /记录编号无效/)
  await assert.rejects(callBackend('updateRole', { code: '../users', label: '错误', permissions: [] }), /角色代码无效/)
  await assert.rejects(callBackend('postReceipt', { receiptId: '../users' }), /记录编号无效/)
  await assert.rejects(callBackend('unknown-operation', undefined), /不允许的业务操作/)
  await callBackend('logout', undefined)
  await assert.rejects(callBackend('me', undefined), /请先登录/)
  await callBackend('login', { username: 'admin', password: 'secure-pass-123' })
  await callBackend('changePassword', { current_password: 'old-password-123', new_password: 'new-password-123' })
  await assert.rejects(callBackend('me', undefined), /请先登录/)
  await callBackend('login', { username: 'admin', password: 'new-password-123' })
  fetchMock.mock.mockImplementation(async () => { throw new Error('connection refused') })
  await assert.rejects(callBackend('logout', undefined), /无法连接服务端/)
  await assert.rejects(callBackend('me', undefined), /请先登录/)
})
