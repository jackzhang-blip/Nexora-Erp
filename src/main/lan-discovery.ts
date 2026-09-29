import { EventEmitter } from 'node:events'
import { isIP } from 'node:net'
import { networkInterfaces } from 'node:os'
import Bonjour, { type ServiceConfig } from 'bonjour-service'
import type { ServiceAdvertisement } from './discovery-probe'

interface NetworkAddress { address: string; internal: boolean }
interface DiscoveryBrowser extends EventEmitter {
  services: ServiceAdvertisement[]
  stop(): void
}
interface DiscoveryClient {
  find(options: { type: string; protocol: 'tcp' }): DiscoveryBrowser
  destroy(): void
}
type DiscoveryOptions = Partial<ServiceConfig> & { interface: string; bind: string }

export function discoveryInterfaces(
  interfaces: readonly NetworkAddress[] = Object.values(networkInterfaces()).flatMap(entries => entries ?? [])
): string[] {
  return [...new Set(interfaces.filter(entry => !entry.internal && isIP(entry.address) === 4
    && /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)/.test(entry.address))
    .map(entry => entry.address))]
}

export function createLanDiscovery(
  addresses = discoveryInterfaces(),
  createClient: (options: DiscoveryOptions) => DiscoveryClient = options => new Bonjour(options)
): DiscoveryBrowser {
  const combined = new EventEmitter() as DiscoveryBrowser
  const sessions: { client: DiscoveryClient; browser: DiscoveryBrowser }[] = []
  let stopped = false
  Object.defineProperty(combined, 'services', { get: () => sessions.flatMap(session => session.browser.services) })
  combined.stop = () => {
    if (stopped) return
    stopped = true
    for (const { client, browser } of sessions) {
      browser.stop()
      client.destroy()
    }
    sessions.length = 0
    combined.removeAllListeners()
  }
  try {
    for (const address of new Set(addresses)) {
      // Windows 的默认组播出口可能是 VPN/虚拟网卡；每张局域网网卡单独发查询，接收仍绑定通配地址。
      const client = createClient({ interface: address, bind: '0.0.0.0' })
      let browser: DiscoveryBrowser
      try {
        browser = client.find({ type: 'nexora', protocol: 'tcp' })
      } catch (error) {
        client.destroy()
        throw error
      }
      sessions.push({ client, browser })
      browser.on('up', (service: ServiceAdvertisement) => {
        if (!stopped) combined.emit('up', service)
      })
      browser.on('down', (service: ServiceAdvertisement) => {
        if (stopped) return
        // 同一服务可能经多张网卡被发现，只有全部浏览器都移除后才报告离线。
        if (service.txt?.id && combined.services.some(entry => entry.txt?.id === service.txt?.id)) return
        combined.emit('down', service)
      })
    }
    return combined
  } catch (error) {
    combined.stop()
    throw error
  }
}
