<script setup lang="ts">
import { NConfigProvider, dateZhCN, zhCN } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { provideAppStore } from './store/app-store'
import OnboardingView from './views/OnboardingView.vue'
import WorkspaceShell from './views/WorkspaceShell.vue'

// 根组件只装配应用环境；页面状态与业务操作由 store 和各视图负责。
const { screen } = provideAppStore()
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
    :theme-overrides="naiveThemeOverrides"
  >
    <OnboardingView
      v-if="screen !== 'app' && screen !== 'login' && screen !== 'setup'"
    />
    <WorkspaceShell v-else />
  </NConfigProvider>
</template>
