<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../store/app-store'
import { resolveFooterStatus } from '../utils/footer-status'

const { screen, server, connectionLost, connectionNotice, error, notice, busy } = useAppStore()
const status = computed(() => resolveFooterStatus({
  screen: screen.value,
  server: server.value,
  connectionLost: connectionLost.value,
  connectionNotice: connectionNotice.value,
  error: error.value,
  notice: notice.value,
  busy: busy.value
}))
</script>

<template>
  <footer class="onboard-footer app-status-footer">
    <!-- 服务端身份固定在左边；尚未选择服务端时不借用客户端版本冒充服务端版本。 -->
    <span class="app-footer-server" :title="server ? `${server.name} · v${server.version}` : '未选择服务端'">
      {{ server?.name || '未选择服务端' }}<template v-if="server?.version"> · v{{ server.version }}</template>
    </span>
    <span
      class="onboard-footer-status"
      :class="`is-${status.tone}`"
      :role="status.tone === 'error' ? 'alert' : 'status'"
      :title="status.message"
    >
      <span class="onboard-footer-status-text">{{ status.message }}</span>
    </span>
  </footer>
</template>
