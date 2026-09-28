<script setup lang="ts">
import { useAppStore } from '../../store/app-store'
import IconServerLine from '~icons/ri/server-line'
import IconAddLine from '~icons/ri/add-line'

// 此页面只处理当前引导阶段的展示和输入，连接操作由共享状态管理。
const {
  busy,
  username,
  password,
  hostForm,
  host,
  go,
  chooseDataDir,
  createLocalHost,
  restartLocalHost
} = useAppStore()
</script>

<template>
  <section class="onboard-columns create-columns">
    <div v-if="host.configured" class="onboard-panel">
      <div class="panel-heading">
        <span class="panel-icon"><IconServerLine aria-hidden="true" /></span>
        <div>
          <h2>此电脑已有服务端</h2>
          <p>一个电脑只创建一个本机实例。你可以继续使用已有服务端。</p>
        </div>
      </div>
      <div class="onboard-actions">
        <button class="secondary" type="button" @click="go('welcome')">
          返回首页</button
        ><button
          class="primary"
          type="button"
          :disabled="busy"
          @click="restartLocalHost"
        >
          {{ host.running ? '连接本机服务' : '启动本机服务' }}
        </button>
      </div>
    </div>
    <form
      v-else
      class="onboard-panel onboard-form"
      @submit.prevent="createLocalHost"
    >
      <div class="panel-heading">
        <span class="panel-icon"><IconAddLine aria-hidden="true" /></span>
        <div>
          <h2>本机服务配置</h2>
          <p>第一版使用 SQLite，每台电脑只创建一个本机实例。</p>
        </div>
      </div>
      <div class="form-grid">
        <label
          >实例名称<input
            v-model.trim="hostForm.name"
            required
            maxlength="80"
            placeholder="例如 总公司 ERP" /></label
        ><label
          >服务端口<input
            v-model.number="hostForm.port"
            type="number"
            min="1"
            max="65535"
            required
        /></label>
      </div>
      <label
        >数据目录
        <div class="path-picker">
          <input
            v-model.trim="hostForm.dataDir"
            required
            placeholder="选择 SQLite 数据保存位置"
          /><button class="secondary" type="button" @click="chooseDataDir">
            选择
          </button>
        </div></label
      >
      <div class="form-grid">
        <label
          >首位管理员账号<input
            v-model.trim="hostForm.username"
            required
            minlength="3"
            maxlength="40"
            autocomplete="username" /></label
        ><span class="form-hint"
          >已有数据库会原样保留；已有管理员请使用原账号登录。</span
        >
      </div>
      <div class="form-grid">
        <label
          >管理员密码<input
            v-model="hostForm.password"
            type="password"
            required
            minlength="12"
            maxlength="128"
            autocomplete="new-password"
            placeholder="至少 12 位" /></label
        ><label
          >确认密码<input
            v-model="hostForm.confirm"
            type="password"
            required
            minlength="12"
            autocomplete="new-password"
        /></label>
      </div>
      <div class="onboard-actions">
        <button class="secondary" type="button" @click="go('welcome')">
          返回首页</button
        ><button class="primary" type="submit" :disabled="busy">
          {{ busy ? '正在创建服务端…' : '创建并启动' }}
        </button>
      </div>
    </form>
    <aside class="onboard-panel setup-summary">
      <p class="onboard-kicker">DEPLOYMENT SUMMARY</p>
      <h2>这台电脑将成为服务端</h2>
      <dl>
        <div>
          <dt>业务数据库</dt>
          <dd>SQLite</dd>
        </div>
        <div>
          <dt>访问方式</dt>
          <dd>局域网 HTTPS</dd>
        </div>
        <div>
          <dt>后台运行</dt>
          <dd>安装版由系统服务管理</dd>
        </div>
        <div>
          <dt>外部客户端</dt>
          <dd>需核对证书指纹并登录</dd>
        </div>
      </dl>
      <p class="summary-note">
        服务端数据集中保存在此电脑。客户端断网后不能继续编辑或自动同步。
      </p>
    </aside>
  </section>
</template>
