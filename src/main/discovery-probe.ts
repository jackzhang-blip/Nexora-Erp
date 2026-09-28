import { isIP } from 'node:net'
import { networkInterfaces } from 'node:os'

interface LocalInterface { address: string; netmask: string; internal: boolean }

export function localAddress(address: string): boolean {
  if (isIP(address) === 4) {
    const parts = address.split('.').map(Number)
    return parts[0] === 10 || parts[0] === 127 || (parts[0] === 192 && parts[1] === 168)
      || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31)
      || (parts[0] === 169 && parts[1] === 254)
  }
  if (isIP(address) === 6) {
    const lower = address.toLowerCase()
    return lower === '::1' || lower.startsWith('fe80:') || lower.startsWith('fc') || lower.startsWith('fd')
  }
  return false
}

export async function inspectDiscoveredAddresses<T extends { id: string }>(
  addresses: readonly string[], port: number, advertisedId: string | undefined,
  inspect: (address: string, port: number) => Promise<T>,
  interfaces: readonly LocalInterface[] = Object.values(networkInterfaces()).flatMap((entries) => entries ?? [])
): Promise<T | null> {
  // 优先检查与当前非环回网卡同网段的地址，避免把可达但易变化的虚拟环回地址保存为常用连接。
  const candidates = [...new Set(addresses.filter(address => isIP(address) === 4 && localAddress(address)))]
  if (!candidates.length) return null

  const onLocalSubnet = (address: string): boolean => {
    const parts = address.split('.').map(Number)
    return interfaces.some((entry) => {
      if (entry.internal || isIP(entry.address) !== 4 || isIP(entry.netmask) !== 4
        || entry.netmask === '0.0.0.0') return false
      const local = entry.address.split('.').map(Number)
      const mask = entry.netmask.split('.').map(Number)
      return parts.every((part, index) => (part & mask[index]) === (local[index] & mask[index]))
    })
  }
  const preferred = candidates.filter(onLocalSubnet)
  const fallback = candidates.filter((address) => !preferred.includes(address))
  for (const group of [preferred, fallback]) {
    if (!group.length) continue
    try {
      return await Promise.any(group.map(async address => {
        const profile = await inspect(address, port)
        if (advertisedId && profile.id !== advertisedId) throw new Error('广播实例与服务端证书身份不一致')
        return profile
      }))
    } catch {
      // 同网段地址均不可用时再尝试其他局域网地址，不把未经核验的广播展示为在线服务。
    }
  }
  return null
}
