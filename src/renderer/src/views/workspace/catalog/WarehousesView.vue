<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import type { Warehouse } from '../../../../../shared/erp-api'
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
    <div class="card">
      <div class="section-heading">
        <div><p class="eyebrow">WAREHOUSES</p><h2>仓库列表 <span class="pill">{{ warehouses.length }}</span></h2></div>
        <button v-if="can('warehouse.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增仓库</button>
      </div>
      <label class="catalog-search">搜索仓库<input v-model="query" placeholder="输入名称或编码搜索" /></label>
      <form v-if="showForm && can('warehouse.manage')" class="catalog-editor" @submit.prevent="save">
        <h3>{{ editingId ? '编辑仓库' : '新增仓库' }}</h3>
        <div class="form-grid">
          <label>仓库编码<input v-model.trim="form.code" required maxlength="40" pattern="[A-Za-z0-9_-]+" /></label>
          <label>仓库名称<input v-model.trim="form.name" required maxlength="80" /></label>
        </div>
        <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">保存</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
      </form>
      <p class="muted">默认主仓库以及已被业务单据引用的仓库不能删除。</p>
      <div class="table-wrap"><table>
        <thead><tr><th>仓库编码</th><th>仓库名称</th><th>操作</th></tr></thead>
        <tbody>
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
          <tr v-if="!filtered.length"><td colspan="3" class="muted">{{ query ? '没有匹配的仓库。' : '暂无仓库，请先新增。' }}</td></tr>
        </tbody>
      </table></div>
    </div>
  </section>
</template>
