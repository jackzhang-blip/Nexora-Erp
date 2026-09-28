import assert from 'node:assert/strict'
import { test } from 'node:test'
import { inspectDiscoveredAddresses, localAddress } from '../src/main/discovery-probe.ts'

test('移动地址校验后仍只允许原有局域网与环回范围', () => {
  assert.equal(localAddress('192.168.3.191'), true)
  assert.equal(localAddress('172.29.32.1'), true)
  assert.equal(localAddress('169.254.39.123'), true)
  assert.equal(localAddress('::1'), true)
  assert.equal(localAddress('8.8.8.8'), false)
  assert.equal(localAddress('2001:4860:4860::8888'), false)
})

test('虚拟网卡地址失败时仍尝试可达的 Windows 局域网地址', async () => {
  const visited = []
  const result = await inspectDiscoveredAddresses(
    ['169.254.39.123', '172.29.32.1', '192.168.3.191', '192.168.3.191', '8.8.8.8', '::1'],
    8000, 'instance-1', async (address, port) => {
      visited.push([address, port])
      if (address !== '192.168.3.191') throw new Error('虚拟网卡不可达')
      return { id: 'instance-1', host: address }
    }, [{ address: '192.168.3.5', netmask: '255.255.255.0', internal: false }]
  )

  // 优先核验同网段地址，不扫描公网或重复地址。
  assert.deepEqual(result, { id: 'instance-1', host: '192.168.3.191' })
  assert.deepEqual(visited, [['192.168.3.191', 8000]])
})

test('同网段与虚拟地址都可达时，保存物理局域网地址', async () => {
  const result = await inspectDiscoveredAddresses(
    ['172.30.195.124', '192.168.3.5'], 8000, 'instance-1',
    async address => ({ id: 'instance-1', host: address }),
    [
      { address: '172.30.195.124', netmask: '255.255.255.255', internal: true },
      { address: '192.168.3.5', netmask: '255.255.255.0', internal: false }
    ]
  )
  assert.equal(result?.host, '192.168.3.5')
})

test('同网段地址无法通过身份核验时，仍回退到其他局域网地址', async () => {
  const visited = []
  const result = await inspectDiscoveredAddresses(
    ['192.168.3.191', '172.29.32.1'], 8000, 'expected', async address => {
      visited.push(address)
      return { id: address === '172.29.32.1' ? 'expected' : 'other', host: address }
    }, [{ address: '192.168.3.5', netmask: '255.255.255.0', internal: false }]
  )
  assert.equal(result?.host, '172.29.32.1')
  assert.deepEqual(visited, ['192.168.3.191', '172.29.32.1'])
})

test('广播身份不匹配时继续寻找同一实例的正确地址', async () => {
  const result = await inspectDiscoveredAddresses(
    ['192.168.3.10', '192.168.3.191'], 8000, 'expected', async address => ({
      id: address === '192.168.3.191' ? 'expected' : 'other', host: address
    })
  )
  assert.equal(result?.host, '192.168.3.191')
})

test('所有候选地址失败或没有局域网地址时，不显示未经核验的服务', async () => {
  const unavailable = await inspectDiscoveredAddresses(['169.254.1.2', '172.29.32.1'], 8000, 'expected', async () => {
    throw new Error('连接超时')
  })
  assert.equal(unavailable, null)
  const ignored = await inspectDiscoveredAddresses(['8.8.8.8', '::1'], 8000, undefined, async () => {
    throw new Error('不应访问非局域网地址')
  })
  assert.equal(ignored, null)
})
