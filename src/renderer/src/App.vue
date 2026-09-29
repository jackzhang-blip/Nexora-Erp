<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { NConfigProvider, darkTheme, dateZhCN, zhCN } from 'naive-ui'
import { storeToRefs } from 'pinia'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useAppStore } from './store/app-store'
import { useThemeStore } from './store/theme-store'
import OnboardingView from './views/OnboardingView.vue'
import WorkspaceShell from './views/WorkspaceShell.vue'
import AppMessageProvider from './components/feedback/AppMessageProvider.vue'

// 根组件统一启动和释放桌面连接资源；页面状态仍由 Pinia store 管理。
const { screen, initialize, dispose } = useAppStore()
const { isDarkTheme } = storeToRefs(useThemeStore())
onMounted(() => {
  void initialize()
})
onUnmounted(dispose)
const naiveThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#237d7a',
    primaryColorHover: '#1d6c69',
    primaryColorPressed: '#195d5a'
  }
}
</script>

<template>
  <NConfigProvider
    :locale="zhCN"
    :date-locale="dateZhCN"
    :theme="isDarkTheme ? darkTheme : null"
    :theme-overrides="naiveThemeOverrides"
  >
    <AppMessageProvider>
      <OnboardingView
        v-if="screen !== 'app' && screen !== 'login' && screen !== 'setup'"
      />
      <WorkspaceShell v-else />
    </AppMessageProvider>
  </NConfigProvider>
</template>
