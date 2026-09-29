<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'
import { useAppStore } from '../store/app-store'
import type { Screen } from '../store/types'
import { nexoraLogo } from '../assets/brand'
import { onboardingCopy } from '../i18n/zh-CN'
import AppStatusFooter from '../components/app/AppStatusFooter.vue'
import LoadingView from './onboarding/LoadingView.vue'
import WelcomeView from './onboarding/WelcomeView.vue'
import ManualConnectionView from './onboarding/ManualConnectionView.vue'
import DiscoveryScanView from './onboarding/DiscoveryScanView.vue'
import DiscoveryResultsView from './onboarding/DiscoveryResultsView.vue'
import LocalHostSetupView from './onboarding/LocalHostSetupView.vue'
import ServerTrustView from './onboarding/ServerTrustView.vue'
import ConnectionReadyView from './onboarding/ConnectionReadyView.vue'
import ConnectionOfflineView from './onboarding/ConnectionOfflineView.vue'

// 引导外壳只决定当前页面；各阶段的输入和操作由对应页面处理。
const { screen, version, candidate, server } = useAppStore()
const onboardingViews: Partial<Record<Screen, Component>> = {
  loading: LoadingView,
  welcome: WelcomeView,
  manual: ManualConnectionView,
  scan: DiscoveryScanView,
  results: DiscoveryResultsView,
  create: LocalHostSetupView,
  trust: ServerTrustView,
  ready: ConnectionReadyView,
  offline: ConnectionOfflineView
}
const currentView = computed(() => {
  if (screen.value === 'trust' && !candidate.value) return null
  if (screen.value === 'ready' && !server.value) return null
  return onboardingViews[screen.value] ?? null
})
</script>

<template>
  <div class="onboarding">
    <header class="onboard-top">
      <div class="onboard-logo">
        <span class="onboard-mark"><img :src="nexoraLogo" alt="" /></span
        ><strong>NEXORA <small>ERP</small></strong>
      </div>
      <span class="onboard-top-note"
        >企业运营工作台 <span v-if="version">· v{{ version }}</span></span
      >
    </header>
    <main class="onboard-main">
      <div class="onboard-hero">
        <p class="onboard-kicker">NEXORA · CONNECT</p>
        <h1>{{ onboardingCopy[screen].title }}</h1>
        <p>{{ onboardingCopy[screen].description }}</p>
      </div>
      <component :is="currentView" v-if="currentView" />
    </main>
    <AppStatusFooter />
  </div>
</template>
