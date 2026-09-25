<script setup lang="ts">
import { onMounted, ref } from 'vue'

// 读取主进程版本号，验证 Vue、预加载脚本和 Electron 主进程已连通。
const version = ref('读取中…')

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
