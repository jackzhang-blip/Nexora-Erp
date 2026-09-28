import { isIP } from 'node:net'

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
  inspect: (address: string, port: number) => Promise<T>
): Promise<T | null> {
  // 一台 Windows 主机可能同时广播物理网卡与虚拟网卡；任一地址通过证书和实例校验即可展示。
  const candidates = [...new Set(addresses.filter(address => isIP(address) === 4 && localAddress(address)))]
  if (!candidates.length) return null
  try {
    return await Promise.any(candidates.map(async address => {
      const profile = await inspect(address, port)
      if (advertisedId && profile.id !== advertisedId) throw new Error('广播实例与服务端证书身份不一致')
      return profile
    }))
  } catch {
    // 所有地址均不可用时，不把未经身份校验的广播显示为可连接服务。
    return null
  }
}
