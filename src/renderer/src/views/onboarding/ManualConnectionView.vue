<script setup lang="ts">
import { useAppStore } from '../../store/app-store'
import IconArrowRightUpLine from '~icons/ri/arrow-right-up-line'
import IconHistoryLine from '~icons/ri/history-line'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const {
  busy,
  server,
  recentServers,
  manualForm,
  host,
  go,
  connectManual,
  connectSaved
} = useAppStore()
</script>

<template>
  <section class="onboard-columns">
    <form class="onboard-panel onboard-form" @submit.prevent="connectManual">
      <div class="panel-heading">
        <span class="panel-icon"
          ><IconArrowRightUpLine aria-hidden="true"
        /></span>
        <div>
          <h2>服务端地址</h2>
          <p>只支持本机和局域网地址，连接将使用 HTTPS。</p>
        </div>
      </div>
      <label
        >IP 地址或主机名<input
          v-model.trim="manualForm.address"
          required
          placeholder="例如 192.168.1.100"
          autocomplete="off" /></label
      ><label
        >端口<input
          v-model.number="manualForm.port"
          type="number"
          min="1"
          max="65535"
          required
      /></label>
      <div class="onboard-actions">
        <button class="secondary" type="button" @click="go('welcome')">
          返回首页</button
        ><button class="primary" type="submit" :disabled="busy">
          {{ busy ? '正在检查…' : '检查并连接' }}
        </button>
      </div>
    </form>
    <div class="onboard-panel">
      <div class="panel-heading">
        <span class="panel-icon"><IconHistoryLine aria-hidden="true" /></span>
        <div>
          <h2>最近连接</h2>
          <p>仅保存地址和已核对的证书，不保存密码。</p>
        </div>
      </div>
      <div v-if="!recentServers.length" class="onboard-empty">
        还没有连接记录。可以填写地址，或扫描局域网。
      </div>
      <button
        v-for="entry in recentServers"
        :key="entry.id"
        class="server-row"
        type="button"
        :disabled="busy"
        @click="connectSaved(entry)"
      >
        <span
          ><strong>{{ entry.name }}</strong
          ><small>{{ entry.host }}:{{ entry.port }}</small></span
        ><span class="server-row-action">连接 →</span>
      </button>
    </div>
  </section>
</template>
