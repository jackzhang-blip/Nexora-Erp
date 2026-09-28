export interface TrayHostStatus {
  configured: boolean
  running: boolean
  migrationNeeded?: boolean
}

export function keepDesktopInTray(platform: NodeJS.Platform): boolean {
  // Windows 与 macOS 的托盘由桌面进程持有，关窗不能触发整个进程退出。
  return platform === 'win32' || platform === 'darwin'
}

export function trayServiceLabel(status: TrayHostStatus | null): string {
  if (!status) return '本机服务：状态读取失败'
  if (status.migrationNeeded) return '本机服务：需要迁移'
  if (!status.configured) return '本机服务：未配置'
  return status.running ? '本机服务：运行中' : '本机服务：已停止'
}
