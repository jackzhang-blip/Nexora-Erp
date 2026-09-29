<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../../../store/app-store'
import { buildPermissionTree } from '../../../utils/permission-tree'

const { busy, permissions, permissionLabelDrafts, savePermissionLabel } = useAppStore()
// 目录单独成页，仍复用服务端返回的模块、单据、操作三级关系。
const permissionModules = computed(() => buildPermissionTree(permissions.value))
</script>

<template>
  <section class="stack">
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
