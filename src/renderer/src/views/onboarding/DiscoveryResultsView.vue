<script setup lang="ts">
import { useAppStore } from '../../store/app-store'
import IconRadarLine from '~icons/ri/radar-line'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const { busy, server, discoveries, host, go, startScan, pickDiscovered } =
  useAppStore()
</script>

<template>
  <section class="onboard-panel">
    <div class="panel-heading">
      <span class="panel-icon"><IconRadarLine aria-hidden="true" /></span>
      <div>
        <h2>发现 {{ discoveries.length }} 个服务端</h2>
        <p>选择在线服务端，下一步核对证书指纹。</p>
      </div>
    </div>
    <div v-if="!discoveries.length" class="onboard-empty">
      当前没有发现可用服务端。请确认两台电脑在同一局域网，或手动填写地址。
    </div>
    <button
      v-for="entry in discoveries"
      :key="entry.id"
      class="server-row"
      type="button"
      :disabled="!entry.online || busy"
      @click="pickDiscovered(entry)"
    >
      <span
        ><strong>{{ entry.name }}</strong
        ><small
          >{{ entry.host }}:{{ entry.port }} · v{{ entry.version }}</small
        ></span
      ><span :class="entry.online ? 'online' : 'offline'">{{
        entry.online ? '在线 · 连接 →' : '离线'
      }}</span>
    </button>
    <div class="onboard-actions">
      <button class="secondary" type="button" @click="go('manual')">
        手动填写</button
      ><button class="primary" type="button" @click="startScan">
        重新扫描
      </button>
    </div>
  </section>
</template>
