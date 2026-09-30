<script setup lang="ts">
import { computed, ref } from 'vue'
import { NModal } from 'naive-ui'
import PermissionTreePicker from '../../../components/workspace/PermissionTreePicker.vue'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { useAppStore } from '../../../store/app-store'
import { buildPermissionTree } from '../../../utils/permission-tree'
import { filterRoleRows, type RoleKindFilter } from '../../../utils/role-table'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  error,
  roles,
  permissions,
  rolePermissionDrafts,
  roleLabelDrafts,
  newRole,
  createRole,
  saveRole
} = useAppStore()

// 页面按服务端提供的模块、单据层级组织操作权限，角色草稿仍只保存叶子代码。
const permissionModules = computed(() => buildPermissionTree(permissions.value))
const roleColumns = [
  { key: 'label', title: '职务名称', width: '34%' },
  { key: 'kind', title: '类型', width: '20%' },
  { key: 'permissions', title: '已授权操作', width: '25%' },
  { key: 'actions', title: '操作', width: '21%' }
]
const search = ref('')
const kind = ref<RoleKindFilter>('all')
const visibleRoles = computed(() => filterRoleRows(roles.value, search.value, kind.value))
const createOpen = ref(false)
const editorOpen = ref(false)
const selectedRoleCode = ref<string | null>(null)
const selectedRole = computed(() => roles.value.find((role) => role.code === selectedRoleCode.value) ?? null)

function openRole(code: string): void {
  selectedRoleCode.value = code
  editorOpen.value = true
}

async function submitNewRole(): Promise<void> {
  await createRole()
  // 共享操作会捕获并展示错误；只有服务端保存成功才关闭编辑窗口。
  if (!error.value) createOpen.value = false
}

async function submitRole(): Promise<void> {
  if (!selectedRole.value || selectedRole.value.is_builtin) return
  await saveRole(selectedRole.value.code)
  if (!error.value) editorOpen.value = false
}
</script>

<template>
  <section class="stack">
    <WorkspaceTable :data="visibleRoles"
      title="职务与权限"
      description="新增职务后可按模块、单据和操作分别授权；内置职务仅供查看。"
      :columns="roleColumns"
      empty-text="没有符合条件的职务"
    >
      <template #actions>
        <button class="primary" type="button" :disabled="busy" @click="createOpen = true">新增职务</button>
      </template>
      <template #filters>
        <label class="role-table-search">搜索职务
          <input v-model.trim="search" type="search" placeholder="输入职务名称" />
        </label>
        <label class="role-table-filter">类型
          <select v-model="kind">
            <option value="all">全部</option>
            <option value="custom">自定义</option>
            <option value="builtin">内置</option>
          </select>
        </label>
        <span class="muted role-table-count">共 {{ visibleRoles.length }} 项</span>
      </template>
      <template #cell-label="{ row: role }"><strong>{{ role.label }}</strong></template>
      <template #cell-kind="{ row: role }">{{ role.is_builtin ? '内置 · 只读' : '自定义' }}</template>
      <template #cell-permissions="{ row: role }">{{ role.permissions.length }} 项操作</template>
      <template #cell-actions="{ row: role }"><button class="secondary small" type="button" @click="openRole(role.code)">
              {{ role.is_builtin ? '查看权限' : '配置权限' }}
            </button></template>
    </WorkspaceTable>

    <NModal v-model:show="createOpen" preset="card" title="新增职务" :mask-closable="!busy" :style="{ width: 'min(760px, calc(100vw - 32px))' }">
      <form class="role-dialog-form" @submit.prevent="submitNewRole">
        <label>职务名称<input v-model.trim="newRole.label" required maxlength="40" placeholder="例如 库存主管" /></label>
        <fieldset class="permission-tree-fieldset role-dialog-tree">
          <legend>授权范围</legend>
          <PermissionTreePicker v-model="newRole.permissions" :modules="permissionModules" :disabled="busy" />
        </fieldset>
        <div class="role-dialog-actions">
          <button class="secondary" type="button" :disabled="busy" @click="createOpen = false">取消</button>
          <button class="primary" type="submit" :disabled="busy">创建职务</button>
        </div>
      </form>
    </NModal>

    <NModal v-model:show="editorOpen" preset="card" :title="selectedRole?.label ?? '职务权限'" :mask-closable="!busy" :style="{ width: 'min(760px, calc(100vw - 32px))' }">
      <form v-if="selectedRole" class="role-dialog-form" @submit.prevent="submitRole">
        <label v-if="!selectedRole.is_builtin">职务名称
          <input v-model.trim="roleLabelDrafts[selectedRole.code]" required maxlength="40" />
        </label>
        <p v-else class="muted">内置职务只读，不能修改授权范围。</p>
        <fieldset class="permission-tree-fieldset role-dialog-tree">
          <legend>授权范围</legend>
          <PermissionTreePicker
            v-if="selectedRole.is_builtin"
            :model-value="selectedRole.permissions"
            :modules="permissionModules"
            readonly
          />
          <PermissionTreePicker
            v-else
            v-model="rolePermissionDrafts[selectedRole.code]"
            :modules="permissionModules"
            :disabled="busy"
          />
        </fieldset>
        <div class="role-dialog-actions">
          <button class="secondary" type="button" :disabled="busy" @click="editorOpen = false">关闭</button>
          <button v-if="!selectedRole.is_builtin" class="primary" type="submit" :disabled="busy">保存权限</button>
        </div>
      </form>
    </NModal>
  </section>
</template>

<style scoped>
.role-table-search { width: min(100%, 280px); }
.role-table-filter { width: 145px; }
.role-table-count { margin-left: auto; white-space: nowrap; }
.role-dialog-form { display: grid; gap: 18px; }
.role-dialog-tree { max-height: min(52vh, 540px); overflow-y: auto; }
.role-dialog-actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 650px) {
  .role-table-search { width: 100%; }
  .role-table-count { margin-left: 0; }
}
</style>
