<script setup lang="ts">
import { NMessageProvider } from 'naive-ui'
import AppMessageBridge from './AppMessageBridge.vue'
</script>

<template>
  <!-- 提供器覆盖引导、登录和工作台；传送到顶层的消息不占据页面内容高度。 -->
  <NMessageProvider placement="top-right" :duration="4000" closable keep-alive-on-hover>
    <AppMessageBridge />
    <slot />
  </NMessageProvider>
</template>
