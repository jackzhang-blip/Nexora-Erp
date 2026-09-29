import assert from 'node:assert/strict'
import { test } from 'node:test'
import { resolveFooterStatus } from '../src/renderer/src/utils/footer-status.ts'

const connected = {
  screen: 'app',
  server: { name: '团队服务端', version: '0.1.0' },
  connectionLost: false,
  connectionNotice: '',
  error: '',
  notice: '',
  busy: false
}

test('工作台业务消息和登录错误不改变连接状态', () => {
  assert.deepEqual(resolveFooterStatus({ ...connected, notice: '入库单已保存' }), {
    message: '已连接', tone: 'success'
  })
  assert.deepEqual(resolveFooterStatus({ ...connected, screen: 'login', error: '密码错误' }), {
    message: '已连接', tone: 'success'
  })
})

test('断线优先于恢复消息，恢复后在底栏显示最新连接结果', () => {
  const recovery = { ...connected, connectionNotice: '服务端连接已恢复，数据已更新。' }
  assert.deepEqual(resolveFooterStatus(recovery), {
    message: '服务端连接已恢复，数据已更新。', tone: 'success'
  })
  assert.deepEqual(resolveFooterStatus({ ...recovery, connectionLost: true }), {
    message: '服务端连接已中断，正在重试。恢复连接前无法保存更改。', tone: 'error'
  })
})

test('没有服务端时提示等待连接，引导页错误优先于成功提示', () => {
  assert.deepEqual(resolveFooterStatus({ ...connected, server: null }), {
    message: '等待连接服务端', tone: 'pending'
  })
  assert.deepEqual(resolveFooterStatus({ ...connected, screen: 'manual', error: '连接超时', notice: '已连接' }), {
    message: '连接超时', tone: 'error'
  })
  assert.deepEqual(resolveFooterStatus({ ...connected, screen: 'welcome', server: null }), {
    message: '未连接', tone: 'idle'
  })
  assert.deepEqual(resolveFooterStatus({ ...connected, screen: 'ready' }), {
    message: '已连接', tone: 'success'
  })
})
