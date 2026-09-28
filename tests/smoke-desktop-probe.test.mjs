import assert from 'node:assert/strict'
import { test } from 'node:test'
import { DesktopProbeTimeoutError, readDesktopChoices, waitForDesktopChoices } from '../scripts/smoke-desktop-probe.mjs'

class FakeSocket extends EventTarget {
  constructor() {
    super()
    this.handlers = new Map()
    this.requests = []
  }

  addEventListener(type, listener) {
    super.addEventListener(type, listener)
    this.handlers.set(type, (this.handlers.get(type) ?? 0) + 1)
  }

  removeEventListener(type, listener) {
    super.removeEventListener(type, listener)
    this.handlers.set(type, (this.handlers.get(type) ?? 0) - 1)
  }

  send(payload) {
    const request = JSON.parse(payload)
    this.requests.push(request)
    this.onSend?.(request)
  }

  respond(response) {
    const event = new Event('message')
    Object.defineProperty(event, 'data', { value: JSON.stringify(response) })
    this.dispatchEvent(event)
  }

  assertClean() {
    // 超时、成功或异常后都不能留下监听器，避免后续请求重复处理旧响应。
    for (const type of ['message', 'close', 'error']) assert.equal(this.handlers.get(type), 0)
  }
}

const pageState = { choices: ['连接服务端', '扫描局域网', '新建服务端'], errors: [] }

test('页面请求超时后清理监听器，旧响应不能冒充新请求', async () => {
  const socket = new FakeSocket()
  await assert.rejects(readDesktopChoices(socket, 1, 5), DesktopProbeTimeoutError)
  socket.assertClean()

  const next = readDesktopChoices(socket, 2, 100)
  socket.respond({ id: 1, result: { result: { value: { choices: ['旧页面'] } } } })
  socket.respond({ id: 2, result: { result: { value: pageState } } })
  assert.deepEqual(await next, pageState)
  assert.deepEqual(socket.requests.map((request) => request.id), [1, 2])
  socket.assertClean()
})

test('桌面导航暂时不回复时重试并取得三个启动入口', async () => {
  const socket = new FakeSocket()
  socket.onSend = (request) => {
    if (request.id === 2) queueMicrotask(() => socket.respond({ id: 2, result: { result: { value: pageState } } }))
  }
  assert.deepEqual(await waitForDesktopChoices(socket, {
    deadlineMs: 200, requestTimeoutMs: 10, pollIntervalMs: 1
  }), pageState)
  assert.equal(socket.requests.length, 2)
  socket.assertClean()
})

test('页面脚本异常立即失败，不被超时重试掩盖', async () => {
  const socket = new FakeSocket()
  socket.onSend = (request) => queueMicrotask(() => socket.respond({
    id: request.id, result: { exceptionDetails: { text: 'boom' } }
  }))
  await assert.rejects(waitForDesktopChoices(socket, {
    deadlineMs: 200, requestTimeoutMs: 20, pollIntervalMs: 1
  }), /页面脚本异常/)
  assert.equal(socket.requests.length, 1)
  socket.assertClean()
})

test('持续没有页面响应时在总时限结束后失败', async () => {
  const socket = new FakeSocket()
  await assert.rejects(waitForDesktopChoices(socket, {
    deadlineMs: 40, requestTimeoutMs: 5, pollIntervalMs: 1
  }), /首次进入页未正确加载/)
  assert.ok(socket.requests.length > 0)
  socket.assertClean()
})

test('调试连接关闭时立即失败并清理监听器', async () => {
  const socket = new FakeSocket()
  socket.onSend = () => queueMicrotask(() => socket.dispatchEvent(new Event('close')))
  await assert.rejects(readDesktopChoices(socket, 1, 100), /连接已关闭/)
  socket.assertClean()
})
