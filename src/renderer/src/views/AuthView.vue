<script setup lang="ts">
import { useAppStore } from '../store/app-store'

// 管理员初始化和正常登录共用凭据表单，提交分支由当前阶段判断。
const {
  screen,
  server,
  username,
  password,
  busy,
  connectionLost,
  authenticate,
  switchServer
} = useAppStore()
</script>

<template>
  <section class="card auth-card">
    <p class="eyebrow">{{ screen === 'setup' ? '首次使用' : '欢迎回来' }}</p>
    <h2>{{ screen === 'setup' ? '创建首位管理员' : '登录工作台' }}</h2>
    <p class="muted">
      {{
        screen === 'setup'
          ? '管理员可以创建用户并分配角色。请设置至少 12 位的密码。'
          : `使用 ${server?.name || '当前服务端'} 的账号访问采购、库存与用户权限。`
      }}
    </p>
    <form @submit.prevent="authenticate">
      <label
        >用户名<input
          v-model.trim="username"
          autocomplete="username"
          minlength="3"
          maxlength="40"
          required
          placeholder="例如 admin"
      /></label>
      <label
        >密码<input
          v-model="password"
          type="password"
          :autocomplete="
            screen === 'setup' ? 'new-password' : 'current-password'
          "
          :minlength="screen === 'setup' ? 12 : undefined"
          required
          placeholder="输入密码"
      /></label>
      <button class="primary" type="submit" :disabled="busy || connectionLost">
        {{ busy ? '请稍候…' : screen === 'setup' ? '创建管理员' : '登录' }}
      </button>
    </form>
    <button class="text-button auth-switch" type="button" @click="switchServer">
      切换服务端
    </button>
  </section>
</template>
