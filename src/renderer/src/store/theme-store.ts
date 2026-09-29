import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { readThemePreference, saveThemePreference } from '../utils/theme-preference'
import type { ThemeMode } from '../utils/theme-preference'

function availableStorage(): Storage | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage
  } catch {
    return undefined
  }
}

// 主题作为独立 Pinia store，根组件与账号区读取同一份设置。
export const useThemeStore = defineStore('theme', () => {
  const themeMode = ref<ThemeMode>(readThemePreference(availableStorage()))
  const isDarkTheme = computed(() => themeMode.value === 'dark')

  function setDarkTheme(enabled: boolean): void {
    themeMode.value = enabled ? 'dark' : 'light'
  }

  watch(themeMode, (mode) => {
    // 主题切换同步更新根节点与本地偏好，设置存储不可用时仍保留当前视觉状态。
    if (typeof document !== 'undefined') {
      document.documentElement.dataset.theme = mode
      document.documentElement.style.colorScheme = mode
    }
    saveThemePreference(availableStorage(), mode)
  }, { immediate: true })

  return { themeMode, isDarkTheme, setDarkTheme }
})
