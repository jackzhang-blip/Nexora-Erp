<script setup lang="ts">
import { onMounted, ref } from 'vue'

// 读取主进程版本号，验证 Vue、预加载脚本和 Electron 主进程已连通。
const version = ref('读取中…')
const backendStatus = ref('尚未检查')
const backendMessage = ref('')
const checking = ref(false)

async function checkBackend(): Promise<void> {
  if (checking.value) return
  if (!window.nexora) {
    backendStatus.value = '仅桌面端可检查'
    backendMessage.value = '请在 Electron 桌面应用中检查后端连接。'
    return
  }
  checking.value = true
  backendStatus.value = '正在连接…'
  backendMessage.value = ''
  try {
    const result = await window.nexora.getBackendHealth()
    backendStatus.value = result.connected ? `已连接 · v${result.version}` : '未连接'
    backendMessage.value = result.connected ? '后端服务运行正常。' : result.message
  } catch {
    backendStatus.value = '检查失败'
    backendMessage.value = '桌面接口调用失败，请重启应用后重试。'
  } finally {
    checking.value = false
  }
}

onMounted(() => { void checkBackend() })

onMounted(async () => {
  if (!window.nexora) {
    version.value = '请在 Electron 中查看'
    return
  }

  try {
    version.value = await window.nexora.getVersion()
  } catch {
    version.value = '读取失败'
  }
})
</script>

<template>
  <!-- 这里只展示框架状态；业务模块和同步能力将在后续开发。 -->
  <main class="shell">
    <div class="brand">N <span>·</span> NEXORA ERP</div>

    <section class="hero">
      <span class="eyebrow">DESKTOP FOUNDATION</span>
      <h1>联光 ERP</h1>
      <p class="lead">Electron + Vue 3 + TypeScript 基础框架已就绪。</p>
      <p class="description">从这里开始构建业务模块、本地数据与可选的同步模式。</p>
    </section>

    <section class="backend" aria-label="后端连接">
      <div role="status" aria-live="polite" :aria-busy="checking">
        <h2>FastAPI 后端 <span>{{ backendStatus }}</span></h2>
        <p>{{ backendMessage || '正在检查后端服务，请稍候。' }}</p>
      </div>
      <button type="button" :disabled="checking" @click="checkBackend">
        {{ checking ? '检查中…' : '重新检查连接' }}
      </button>
    </section>

    <section class="status" aria-label="框架状态">
      <div class="status-item">
        <span class="status-label">应用版本</span>
        <strong>{{ version }}</strong>
      </div>
      <div class="status-item">
        <span class="status-label">桌面容器</span>
        <strong>Electron</strong>
      </div>
      <div class="status-item">
        <span class="status-label">界面框架</span>
        <strong>Vue 3 + TS</strong>
      </div>
    </section>

    <p class="footnote">当前为项目骨架，尚未实现 ERP 业务功能或数据同步。</p>
  </main>
</template>
