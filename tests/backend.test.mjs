import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getBackendHealth } from '../src/main/backend.ts'

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
