export type ThemeMode = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'nexora-theme-mode'

type ThemeStorage = Pick<Storage, 'getItem' | 'setItem'>

// 本地设置可能被禁用或清除；遇到无效值时保持可预测的浅色默认主题。
export function readThemePreference(storage: ThemeStorage | undefined): ThemeMode {
  try {
    return storage?.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

// 存储失败不应阻止本次界面切换，当前会话仍由响应式状态控制。
export function saveThemePreference(storage: ThemeStorage | undefined, mode: ThemeMode): void {
  try {
    storage?.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // 浏览器禁用本地存储时，仅跳过跨会话记忆。
  }
}
