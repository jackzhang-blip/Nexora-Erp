<script setup lang="ts">
import { ref } from 'vue'
import { NModal } from 'naive-ui'
import { useAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  error,
  notice,
  busy,
  user,
  username,
  password,
  roles,
  users,
  roleDrafts,
  resetPasswords,
  newUser,
  createUser,
  saveRoles,
  setUserStatus,
  resetUserPassword
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createUser, { busy, error, notice }, createOpen)
}
</script>

<template>
  <section class="stack">
    <div class="form-actions"><button class="primary" type="button" :disabled="busy" @click="createOpen = true">创建用户</button></div>
    <NModal v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">用户管理</p>
          <h2>创建用户</h2>
        </div>
      </div>
      <form class="inline-form" @submit.prevent="submitCreate">
        <label
          >用户名<input
            v-model.trim="newUser.username"
            required
            minlength="3"
            maxlength="40"
            placeholder="英文、数字或下划线" /></label
        ><label
          >初始密码<input
            v-model="newUser.password"
            type="password"
            required
            minlength="12"
            maxlength="128"
            autocomplete="new-password"
            placeholder="至少 12 位"
        /></label>
        <fieldset>
          <legend>角色</legend>
          <label v-for="role in roles" :key="role.code" class="check"
            ><input
              v-model="newUser.roles"
              type="checkbox"
              :value="role.code"
            />{{ role.label }}</label
          >
        </fieldset>
        <button
          class="primary"
          type="submit"
          :disabled="busy || !newUser.roles.length"
        >
          创建用户
        </button>
      </form>
    </NModal>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">账号与角色</p>
          <h2>用户与角色</h2>
        </div>
      </div>
      <div v-for="entry in users" :key="entry.id" class="user-row">
        <div>
          <strong>{{ entry.username }}</strong
          ><small
            >#{{ entry.id }} ·
            {{ entry.is_active ? '已启用' : '已停用' }}</small
          >
        </div>
        <div class="user-access">
          <div class="role-picker">
            <label v-for="role in roles" :key="role.code" class="check"
              ><input
                v-model="roleDrafts[entry.id]"
                type="checkbox"
                :value="role.code"
              />{{ role.label }}</label
            >
          </div>
          <label class="reset-field"
            >新密码<input
              v-model="resetPasswords[entry.id]"
              type="password"
              minlength="12"
              maxlength="128"
              autocomplete="new-password"
              placeholder="重置密码至少 12 位"
          /></label>
        </div>
        <div class="user-actions">
          <button
            class="secondary small"
            type="button"
            :disabled="busy || !roleDrafts[entry.id]?.length"
            @click="saveRoles(entry.id)"
          >
            保存角色
          </button>
          <button
            class="secondary small"
            type="button"
            :disabled="
              busy ||
              entry.id === user?.id ||
              !resetPasswords[entry.id] ||
              resetPasswords[entry.id].length < 12
            "
            @click="resetUserPassword(entry.id)"
          >
            重置密码
          </button>
          <button
            class="secondary small"
            type="button"
            :disabled="busy || entry.id === user?.id"
            @click="setUserStatus(entry)"
          >
            {{ entry.is_active ? '停用账号' : '启用账号' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
