<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAppStore } from '../../../store/app-store'
import { buildPermissionTree } from '../../../utils/permission-tree'

const { busy, permissions, permissionLabelDrafts, savePermissionLabel, loadPermissions, displayError } = useAppStore()
// 目录单独成页，仍复用服务端返回的模块、单据、操作三级关系。
const permissionModules = computed(() => buildPermissionTree(permissions.value))
const loading = ref(false)
const loadError = ref('')

async function retryLoad(): Promise<void> {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    await loadPermissions()
  } catch (cause) {
    loadError.value = displayError(cause)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // 登录时全局业务刷新失败后，目录页面仍可单独恢复自己的数据。
  if (permissions.value.length === 0) void retryLoad()
})
</script>

<template>
  <section class="stack">
    <div class="card">
      <!-- 页面说明已移到外部标题区，保留权限树与名称编辑。 -->
      <div class="permission-catalog">
        <p v-if="loading" class="muted">正在加载权限目录...</p>
        <div v-else-if="loadError && permissionModules.length === 0" role="alert">
          <p>权限目录加载失败：{{ loadError }}</p>
          <button class="secondary small" type="button" @click="retryLoad">重试</button>
        </div>
        <p v-else-if="permissionModules.length === 0" class="muted">暂无权限项目。</p>
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
