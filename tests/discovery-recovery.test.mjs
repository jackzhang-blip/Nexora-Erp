import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { findPinnedService } from '../src/main/discovery-probe.ts'

function browser(services = []) {
  const emitter = new EventEmitter()
  emitter.services = services
  return emitter
}

test('旧地址失效后只用原证书实例的新局域网地址恢复', async () => {
  const service = { txt: { id: 'saved-id' }, addresses: ['169.254.4.1', '192.168.3.120'], port: 8000 }
  const discovered = browser([service])
  const checked = []
  const result = await findPinnedService(discovered, { id: 'saved-id', fingerprint: 'trusted' }, async (address, port) => {
    checked.push([address, port])
    if (address !== '192.168.3.120') throw new Error('虚拟网卡不可达')
    return { id: 'saved-id', fingerprint: 'trusted', host: address, port }
  }, 100)
  assert.deepEqual(result, { id: 'saved-id', fingerprint: 'trusted', host: '192.168.3.120', port: 8000 })
  assert.equal(checked.some(([address]) => address === '192.168.3.120'), true)
  assert.equal(discovered.listenerCount('up'), 0)
})

test('广播身份或证书不匹配时不自动更换已保存的服务端', async () => {
  const discovered = browser([
    { txt: { id: 'other-id' }, addresses: ['192.168.3.120'], port: 8000 },
    { txt: { id: 'saved-id' }, addresses: ['192.168.3.121'], port: 8000 }
  ])
  const checked = []
  const result = await findPinnedService(discovered, { id: 'saved-id', fingerprint: 'trusted' }, async (address) => {
    checked.push(address)
    return { id: 'saved-id', fingerprint: 'changed', host: address }
  }, 30)
  assert.equal(result, null)
  assert.deepEqual(checked, ['192.168.3.121'])
  assert.equal(discovered.listenerCount('up'), 0)
})

test('扫描期间新出现的服务也可恢复，超时后不再接受迟到广播', async () => {
  const discovered = browser()
  const waiting = findPinnedService(discovered, { id: 'saved-id', fingerprint: 'trusted' }, async address => ({
    id: 'saved-id', fingerprint: 'trusted', host: address
  }), 100)
  discovered.emit('up', { txt: { id: 'saved-id' }, addresses: ['192.168.3.122'], port: 8000 })
  assert.equal((await waiting)?.host, '192.168.3.122')
  assert.equal(discovered.listenerCount('up'), 0)
  const expired = findPinnedService(discovered, { id: 'saved-id', fingerprint: 'trusted' }, async () => {
    throw new Error('不应连接迟到服务')
  }, 10)
  assert.equal(await expired, null)
  discovered.emit('up', { txt: { id: 'saved-id' }, addresses: ['192.168.3.123'], port: 8000 })
  assert.equal(discovered.listenerCount('up'), 0)
})
