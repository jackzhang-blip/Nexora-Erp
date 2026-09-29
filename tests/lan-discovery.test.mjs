import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { test } from 'node:test'
import { createLanDiscovery, discoveryInterfaces } from '../src/main/lan-discovery.ts'

test('搜索覆盖全部局域网 IPv4 网卡，排除环回、IPv6 和代理测试地址', () => {
  assert.deepEqual(discoveryInterfaces([
    { address: '198.18.0.1', internal: false },
    { address: '192.168.3.191', internal: false },
    { address: '172.29.32.1', internal: false },
    { address: '10.0.0.2', internal: false },
    { address: '169.254.1.2', internal: false },
    { address: '127.0.0.1', internal: true },
    { address: 'fe80::1', internal: false },
    { address: '192.168.3.191', internal: false }
  ]), ['192.168.3.191', '172.29.32.1', '10.0.0.2', '169.254.1.2'])
})

function fakeClient() {
  const browser = new EventEmitter()
  browser.services = []
  let stops = 0
  let destroys = 0
  browser.stop = () => { stops++ }
  return { browser, find: () => browser, destroy: () => { destroys++ },
    counts: () => [stops, destroys] }
}

test('每张网卡显式指定组播出口，合并发现且避免重复离线，停止释放全部资源', () => {
  const clients = []
  const options = []
  const discovery = createLanDiscovery(['192.168.3.191', '172.29.32.1'], option => {
    options.push(option)
    const client = fakeClient()
    clients.push(client)
    return client
  })
  assert.deepEqual(options, [
    { interface: '192.168.3.191', bind: '0.0.0.0' },
    { interface: '172.29.32.1', bind: '0.0.0.0' }
  ])
  const service = { addresses: ['192.168.3.5'], port: 8000, txt: { id: 'mac' } }
  const up = []
  const down = []
  discovery.on('up', entry => up.push(entry))
  discovery.on('down', entry => down.push(entry))
  for (const client of clients) {
    client.browser.services.push(service)
    client.browser.emit('up', service)
  }
  assert.equal(up.length, 2)
  assert.equal(discovery.services.length, 2)
  clients[0].browser.services = []
  clients[0].browser.emit('down', service)
  assert.equal(down.length, 0)
  clients[1].browser.services = []
  clients[1].browser.emit('down', service)
  assert.deepEqual(down, [service])
  discovery.stop()
  discovery.stop()
  clients[0].browser.emit('up', service)
  assert.equal(up.length, 2)
  assert.deepEqual(clients.map(client => client.counts()), [[1, 1], [1, 1]])
  assert.deepEqual(discovery.services, [])
})

test('创建中途失败释放已启动的浏览器与失败客户端', () => {
  const first = fakeClient()
  const second = fakeClient()
  second.find = () => { throw new Error('启动失败') }
  assert.throws(() => createLanDiscovery(['192.168.3.191', '172.29.32.1'], option =>
    option.interface === '192.168.3.191' ? first : second), /启动失败/)
  assert.deepEqual(first.counts(), [1, 1])
  assert.deepEqual(second.counts(), [0, 1])
})

test('没有局域网网卡时不退回未知默认出口', () => {
  const discovery = createLanDiscovery([], () => { throw new Error('不应创建') })
  assert.deepEqual(discovery.services, [])
  discovery.stop()
})
