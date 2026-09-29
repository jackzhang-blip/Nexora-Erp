import { computed, ref, watch } from 'vue'
import { readThemePreference, saveThemePreference } from '../utils/theme-preference'
import type { ThemeMode } from '../utils/theme-preference'

function availableStorage(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage
  } catch {
    return undefined
  }
}

// 账号区与根主题提供器共用一份状态，切换时 Naive UI 和页面背景同步更新。
export const themeMode = ref<ThemeMode>(readThemePreference(availableStorage()))
export const isDarkTheme = computed(() => themeMode.value === 'dark')

export function setDarkTheme(enabled: boolean): void {
  themeMode.value = enabled ? 'dark' : 'light'
}

watch(themeMode, (mode) => {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = mode
    document.documentElement.style.colorScheme = mode
  }
  saveThemePreference(availableStorage(), mode)
}, { immediate: true })
