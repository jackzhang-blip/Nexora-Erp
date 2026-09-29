<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import type { Warehouse } from '../../../../../shared/erp-api'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import './catalog.css'

const store = usePiniaAppStore()
const { busy, connectionLost, warehouses } = storeToRefs(store)
const { can, saveWarehouse, deleteWarehouse } = store
const query = ref('')
const editingId = ref<number | undefined>()
const showForm = ref(false)
const form = reactive({ code: '', name: '' })
const filtered = computed(() => warehouses.value.filter(item => [item.code, item.name].join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
// 列头和空状态由公共组件渲染，仓库限制仍在页面操作中判断。
const columns = [
  { key: 'code', title: '仓库编码' },
  { key: 'name', title: '仓库名称' },
  { key: 'actions', title: '操作' }
]
function edit(item?: Warehouse): void {
  editingId.value = item?.id
  Object.assign(form, item ? { code: item.code, name: item.name } : { code: '', name: '' })
  showForm.value = true
}
async function save(): Promise<void> {
  if (await saveWarehouse({ ...form }, editingId.value)) showForm.value = false
}
</script>

<template>
  <section class="stack catalog-page">
    <WorkspaceTable title="仓库列表" :columns="columns" :row-count="filtered.length" :min-table-width="440">
      <template #heading>
        <p class="eyebrow">WAREHOUSES</p><h2>仓库列表 <span class="pill">{{ warehouses.length }}</span></h2>
      </template>
      <template #actions>
        <button v-if="can('warehouse.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增仓库</button>
      </template>
      <template #filters>
        <label class="catalog-search">搜索仓库<input v-model="query" placeholder="输入名称或编码搜索" /></label>
      </template>
      <template #beforeTable>
        <form v-if="showForm && can('warehouse.manage')" class="catalog-editor" @submit.prevent="save">
          <h3>{{ editingId ? '编辑仓库' : '新增仓库' }}</h3>
          <div class="form-grid">
            <label>仓库编码<input v-model.trim="form.code" required maxlength="40" pattern="[A-Za-z0-9_-]+" /></label>
            <label>仓库名称<input v-model.trim="form.name" required maxlength="80" /></label>
          </div>
          <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">保存</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
        </form>
        <p class="muted">默认主仓库以及已被业务单据引用的仓库不能删除。</p>
      </template>
      <template #rows>
        <tr v-for="item in filtered" :key="item.id">
          <td>{{ item.code }}</td><td>{{ item.name }}</td>
          <td><div class="catalog-actions">
            <template v-if="can('warehouse.manage')">
              <button class="text-button" :disabled="busy || connectionLost" @click="edit(item)">编辑</button>
              <NPopconfirm positive-text="确认" negative-text="取消" @positive-click="deleteWarehouse(item.id)">
                <template #trigger><button class="text-button" :disabled="busy || connectionLost || item.id === 1">删除</button></template>
                确认删除“{{ item.name }}”？已被业务记录引用的资料不能删除。
              </NPopconfirm>
            </template>
          </div></td>
        </tr>
      </template>
      <template #empty>{{ query ? '没有匹配的仓库。' : '暂无仓库，请先新增。' }}</template>
    </WorkspaceTable>
  </section>
</template>
