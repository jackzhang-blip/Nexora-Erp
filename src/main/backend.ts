import type { BackendHealth } from '../shared/desktop-api'

export async function getBackendHealth(): Promise<BackendHealth> {
  try {
    // 地址只由主进程环境配置，页面不能传入任意 URL。
    const base = new URL(process.env.NEXORA_API_URL || 'http://127.0.0.1:8000')
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password) {
      return { connected: false, message: '后端地址配置无效，请检查 NEXORA_API_URL。' }
    }
    const response = await fetch(new URL('/api/v1/health', base), {
      signal: AbortSignal.timeout(5000),
      redirect: 'error'
    })
    if (!response.ok) {
      return { connected: false, message: `后端返回 HTTP ${response.status}，请检查服务后重试。` }
    }
    const data: unknown = await response.json()
    if (!data || typeof data !== 'object' || !('status' in data) || data.status !== 'ok'
      || !('service' in data) || data.service !== 'nexora-api'
      || !('version' in data) || typeof data.version !== 'string' || !data.version.trim()) {
      return { connected: false, message: '后端响应格式不匹配，请确认运行的是 Nexora API。' }
    }
    return { connected: true, version: data.version }
  } catch {
    return { connected: false, message: '无法连接后端，请确认服务已启动、地址正确，然后重试。' }
  }
}
