<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  password,
  passwordChange,
  server,
  host,
  switchServer,
  stopLocalHost,
  restartLocalHost,
  upgradeLocalHost,
  changeOwnPassword
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="card">
      <div class="section-heading">
        <div>
          <h2>当前连接</h2>
        </div>
      </div>
      <dl class="server-details">
        <div>
          <dt>服务端</dt>
          <dd>{{ server?.name }}</dd>
        </div>
        <div>
          <dt>地址</dt>
          <dd>{{ server?.host }}:{{ server?.port }}</dd>
        </div>
        <div>
          <dt>证书指纹</dt>
          <dd class="mono">{{ server?.fingerprint }}</dd>
        </div>
      </dl>
      <button class="secondary" type="button" @click="switchServer">
        切换服务端
      </button>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <h2>修改我的密码</h2>
        </div>
      </div>
      <form class="inline-form" @submit.prevent="changeOwnPassword">
        <div class="form-grid">
          <label
            >当前密码<input
              v-model="passwordChange.current_password"
              type="password"
              required
              autocomplete="current-password" /></label
          ><label
            >新密码<input
              v-model="passwordChange.new_password"
              type="password"
              required
              minlength="12"
              maxlength="128"
              autocomplete="new-password"
              placeholder="至少 12 位"
          /></label>
        </div>
        <p class="muted">修改后所有设备都需要重新登录。</p>
        <button class="primary" type="submit" :disabled="busy">修改密码</button>
      </form>
    </div>
    <div v-if="host.configured" class="card">
      <div class="section-heading">
        <div>
          <h2>本机服务</h2>
        </div>
        <span class="pill" :class="{ posted: host.running }">{{
          host.running ? '运行中' : '已停止'
        }}</span>
      </div>
      <p class="muted">
        {{
          host.systemManaged
            ? '系统服务在关闭窗口、退出应用或无人登录时继续运行。'
            : host.migrationNeeded
              ? '旧版主机需点击启动，以迁移到系统服务。'
              : '开发模式下由桌面进程持有，退出应用后停止。'
        }}
      </p>
      <div class="onboard-actions">
        <button
          v-if="host.running"
          class="secondary"
          type="button"
          :disabled="busy"
          @click="stopLocalHost"
        >
          停止本机服务</button
        ><button
          v-else
          class="primary"
          type="button"
          :disabled="busy"
          @click="restartLocalHost"
        >
          {{
            host.migrationNeeded ? '迁移并启动系统服务' : '启动本机服务'
          }}</button
        ><button
          v-if="host.systemManaged"
          class="secondary"
          type="button"
          :disabled="busy"
          @click="upgradeLocalHost"
        >
          用当前安装包升级服务
        </button>
      </div>
    </div>
  </section>
</template>
