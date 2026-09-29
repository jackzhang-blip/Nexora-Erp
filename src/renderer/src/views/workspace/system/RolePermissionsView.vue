<script setup lang="ts">
import { computed } from 'vue'
import PermissionTreePicker from '../../../components/workspace/PermissionTreePicker.vue'
import { useAppStore } from '../../../store/app-store'
import { buildPermissionTree } from '../../../utils/permission-tree'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  roles,
  permissions,
  permissionLabelDrafts,
  rolePermissionDrafts,
  roleLabelDrafts,
  newRole,
  createRole,
  saveRole,
  savePermissionLabel
} = useAppStore()

// 页面按服务端提供的模块、单据层级组织操作权限，角色草稿仍只保存叶子代码。
const permissionModules = computed(() => buildPermissionTree(permissions.value))
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
        <fieldset class="permission-tree-fieldset">
          <legend>授权范围</legend>
          <PermissionTreePicker v-model="newRole.permissions" :modules="permissionModules" :disabled="busy" />
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
        <PermissionTreePicker
          v-if="role.is_builtin"
          :model-value="role.permissions"
          :modules="permissionModules"
          readonly
        />
        <div v-else class="role-editor">
          <label
            >名称<input
              v-model.trim="roleLabelDrafts[role.code]"
              maxlength="40"
          /></label>
          <fieldset class="permission-tree-fieldset">
            <legend>权限</legend>
            <PermissionTreePicker
              v-model="rolePermissionDrafts[role.code]"
              :modules="permissionModules"
              :disabled="busy"
            />
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
    <!-- 权限目录只维护中文名称，代码作为只读标识展示。 -->
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">权限目录</p>
          <h2>权限中文名称</h2>
          <p class="muted">名称用于页面展示；内部代码用于服务端授权，不能修改。</p>
        </div>
      </div>
      <div class="permission-catalog">
        <details v-for="module in permissionModules" :key="module.code" class="permission-catalog-group">
          <summary>{{ module.label }}</summary>
          <details v-for="document in module.documents" :key="document.code" class="permission-catalog-document">
            <summary>{{ document.label }}</summary>
            <form
              v-for="permission in document.permissions"
              :key="permission.code"
              class="permission-catalog-row"
              @submit.prevent="savePermissionLabel(permission.code)"
            >
              <small>{{ permission.code }}</small>
              <label>
                中文名称
                <input
                  v-model.trim="permissionLabelDrafts[permission.code]"
                  required
                  maxlength="60"
                />
              </label>
              <button
                class="secondary small"
                type="submit"
                :disabled="busy || !permissionLabelDrafts[permission.code] || permissionLabelDrafts[permission.code] === permission.label"
              >保存名称</button>
            </form>
          </details>
        </details>
      </div>
    </div>
  </section>
</template>
