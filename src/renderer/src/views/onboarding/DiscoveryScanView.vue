<script setup lang="ts">
import { useAppStore } from '../../store/app-store'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const { discoveries, scanSeconds, scanning, go, startScan, showResults } =
  useAppStore()
</script>

<template>
  <section class="onboard-panel scan-panel">
    <div class="scan-visual">
      <div class="scan-orbit"><span class="scan-core">N</span></div>
    </div>
    <div class="scan-copy">
      <p class="onboard-kicker">LIVE DISCOVERY</p>
      <h2>已扫描 {{ scanSeconds }} 秒</h2>
      <p>
        发现 {{ discoveries.length }} 个可用服务端。结果会随着网络变化更新。
      </p>
      <div class="scan-live">
        <span class="status-dot"></span>{{ scanning ? '正在发现' : '已暂停' }}
      </div>
    </div>
    <div class="onboard-actions scan-actions">
      <button class="secondary" type="button" @click="go('welcome')">
        返回首页</button
      ><button class="secondary" type="button" @click="showResults">
        暂停并查看结果</button
      ><button class="primary" type="button" @click="startScan">
        重新扫描
      </button>
    </div>
  </section>
</template>
