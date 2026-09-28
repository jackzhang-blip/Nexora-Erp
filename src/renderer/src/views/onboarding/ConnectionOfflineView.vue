<script setup lang="ts">
import { useAppStore } from '../../store/app-store'
import IconErrorWarningLine from '~icons/ri/error-warning-line'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const { busy, server, host, checkConnection, switchServer, restartLocalHost } =
  useAppStore()
</script>

<template>
  <section class="onboard-panel offline-panel">
    <span class="offline-symbol"
      ><IconErrorWarningLine aria-hidden="true"
    /></span>
    <h2>{{ server?.name || '服务端' }} · 暂时无法连接</h2>
    <p>
      服务端可能未启动、网络不可达或证书发生变化。重新连接前请确认服务端身份。
    </p>
    <div class="onboard-actions">
      <button
        class="primary"
        type="button"
        :disabled="busy"
        @click="checkConnection"
      >
        重试连接</button
      ><button
        v-if="host.configured && !host.running"
        class="secondary"
        type="button"
        :disabled="busy"
        @click="restartLocalHost"
      >
        启动本机服务</button
      ><button class="secondary" type="button" @click="switchServer">
        切换服务端
      </button>
    </div>
  </section>
</template>
