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
    calls.push({ path: url.pathname, method: options.method, authorization: options.headers.Authorization })
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
