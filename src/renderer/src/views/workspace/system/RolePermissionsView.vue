<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  roles,
  permissions,
  rolePermissionDrafts,
  roleLabelDrafts,
  newRole,
  createRole,
  saveRole
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">权限管理</p>
          <h2>创建角色并分配权限</h2>
        </div>
      </div>
      <form class="inline-form" @submit.prevent="createRole">
        <label
          >角色名称<input
            v-model.trim="newRole.label"
            required
            maxlength="40"
            placeholder="例如 库存专员"
        /></label>
        <fieldset>
          <legend>授权范围</legend>
          <label
            v-for="permission in permissions"
            :key="permission.code"
            class="check"
            ><input
              v-model="newRole.permissions"
              type="checkbox"
              :value="permission.code"
            />{{ permission.label }}</label
          >
        </fieldset>
        <button class="primary" type="submit" :disabled="busy">创建角色</button>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">角色授权</p>
          <h2>角色权限</h2>
        </div>
      </div>
      <div v-for="role in roles" :key="role.code" class="role-row">
        <div>
          <strong>{{ role.label }}</strong
          ><small>{{
            role.is_builtin ? '内置角色 · 只读' : '自定义角色'
          }}</small>
        </div>
        <div v-if="role.is_builtin" class="muted">
          {{
            role.permissions
              .map(
                (code) =>
                  permissions.find((item) => item.code === code)?.label ??
                  '未命名权限（请升级服务端）'
              )
              .join(' · ')
          }}
        </div>
        <div v-else class="role-editor">
          <label
            >名称<input
              v-model.trim="roleLabelDrafts[role.code]"
              maxlength="40"
          /></label>
          <fieldset>
            <legend>权限</legend>
            <label
              v-for="permission in permissions"
              :key="permission.code"
              class="check"
              ><input
                v-model="rolePermissionDrafts[role.code]"
                type="checkbox"
                :value="permission.code"
              />{{ permission.label }}</label
            >
          </fieldset>
          <button
            class="secondary small"
            type="button"
            :disabled="busy || !roleLabelDrafts[role.code]"
            @click="saveRole(role.code)"
          >
            保存权限
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
