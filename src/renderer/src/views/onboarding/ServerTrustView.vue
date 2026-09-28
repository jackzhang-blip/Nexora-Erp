<script setup lang="ts">
import { useAppStore } from '../../store/app-store'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const { busy, candidate, trustChecked, host, go, approveTrust } = useAppStore()
</script>

<template>
  <section v-if="candidate" class="onboard-panel trust-panel">
    <span class="trust-icon">◇</span>
    <h2>
      {{ candidate.changed ? '服务端证书已变化' : '首次连接，需要确认身份' }}
    </h2>
    <p>
      请到服务端电脑的“服务端已就绪”页面，核对以下完整 SHA-256
      指纹。不要只凭本页面显示的名称判断身份。
    </p>
    <div class="fingerprint">{{ candidate.fingerprint }}</div>
    <p class="muted">
      {{ candidate.name }} · {{ candidate.host }}:{{ candidate.port }}
    </p>
    <label class="check trust-check"
      ><input
        v-model="trustChecked"
        type="checkbox"
      />我已通过服务端电脑或可信渠道核对完整指纹</label
    >
    <div class="onboard-actions">
      <button class="secondary" type="button" @click="go('manual')">取消</button
      ><button
        class="primary"
        type="button"
        :disabled="!trustChecked || busy"
        @click="approveTrust"
      >
        确认身份并连接
      </button>
    </div>
  </section>
</template>
