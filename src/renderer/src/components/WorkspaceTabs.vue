<script setup lang="ts">
import { useAppStore } from '../store/app-store'
import IconCloseLine from '~icons/ri/close-line'

// 标签栏只渲染当前会话已打开的路由；关闭规则由路由模块统一决定。
const { activeTab, openedTabs, navigateToRoute, closeOpenedRoute } =
  useAppStore()
</script>

<template>
  <nav class="workspace-tabs" aria-label="已打开页面">
    <div
      v-for="item in openedTabs"
      :key="item.key"
      class="workspace-tab"
      :class="{ active: activeTab === item.key }"
    >
      <button
        class="workspace-tab-link"
        type="button"
        :aria-current="activeTab === item.key ? 'page' : undefined"
        @click="navigateToRoute(item.key)"
      >
        {{ item.label }}
      </button>
      <button
        v-if="openedTabs.length > 1"
        class="workspace-tab-close"
        type="button"
        :aria-label="`关闭${item.label}`"
        @click="closeOpenedRoute(item.key)"
      >
        <IconCloseLine aria-hidden="true" />
      </button>
    </div>
  </nav>
</template>
