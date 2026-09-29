<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import VxeColumn from 'vxe-table/es/column'
import VxeTable from 'vxe-table/es/table'
import type { Material } from '../../../../../shared/erp-api'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import 'vxe-table/es/table/style.css'
import './catalog.css'

const store = usePiniaAppStore()
const { busy, connectionLost, materials, suppliers, supplierMaterials } = storeToRefs(store)
const { can, saveMaterial, deleteMaterial } = store
const query = ref('')
const editingId = ref<number | undefined>()
const showForm = ref(false)
const form = reactive({ sku: '', name: '', unit: '件' })
const filtered = computed(() => materials.value.filter(item => [item.sku, item.name, item.unit].join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
// 试接只替换物料表格的渲染层，增删改仍经原有 Pinia 操作和服务端权限校验。
function edit(item?: Material): void {
  editingId.value = item?.id
  Object.assign(form, item ? { sku: item.sku, name: item.name, unit: item.unit } : { sku: '', name: '', unit: '件' })
  showForm.value = true
}
async function save(): Promise<void> {
  if (await saveMaterial({ ...form }, editingId.value)) showForm.value = false
}
function supplierNames(id: number): string {
  const ids = new Set(supplierMaterials.value.filter(link => link.material_id === id).map(link => link.supplier_id))
  return suppliers.value.filter(item => ids.has(item.id)).map(item => item.name).join('、') || '未绑定'
}
</script>

<template>
  <section class="stack catalog-page">
    <WorkspaceTable title="物料列表">
      <template #heading>
        <p class="eyebrow">MATERIALS</p><h2>物料列表 <span class="pill">{{ materials.length }}</span></h2>
      </template>
      <template #actions>
        <button v-if="can('catalog.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增物料</button>
      </template>
      <template #filters>
        <label class="catalog-search">搜索物料<input v-model="query" placeholder="输入名称或编码搜索" /></label>
      </template>
      <template #beforeTable>
        <form v-if="showForm && can('catalog.manage')" class="catalog-editor" @submit.prevent="save">
          <h3>{{ editingId ? '编辑物料' : '新增物料' }}</h3>
          <div class="form-grid">
            <label>物料编码<input v-model.trim="form.sku" required maxlength="40" /></label>
            <label>名称（可包含规格型号）<input v-model.trim="form.name" required maxlength="120" /></label>
            <label>单位<input v-model.trim="form.unit" required maxlength="20" /></label>
          </div>
          <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">保存</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
        </form>
        <p class="muted">请按规格建立独立物料编码，同一规格无需为不同供应商重复建档。</p>
      </template>
      <template #table>
        <VxeTable class="catalog-vxe-table" aria-label="物料列表" row-id="id" :data="filtered" :style="{ minWidth: '680px' }">
          <VxeColumn field="sku" title="物料编码" min-width="125" />
          <VxeColumn field="name" title="名称（可包含规格型号）" min-width="220" />
          <VxeColumn field="unit" title="单位" min-width="80" />
          <VxeColumn title="供应商" min-width="140">
            <template #default="{ row }">{{ supplierNames(row.id) }}</template>
          </VxeColumn>
          <VxeColumn title="操作" min-width="115">
            <template #default="{ row }">
              <div class="catalog-actions" v-if="can('catalog.manage')">
                <button class="text-button" :disabled="busy || connectionLost" @click="edit(row)">编辑</button>
                <NPopconfirm positive-text="确认" negative-text="取消" @positive-click="deleteMaterial(row.id)">
                  <template #trigger><button class="text-button" :disabled="busy || connectionLost">删除</button></template>
                  确认删除“{{ row.name }}”？关联的供货关系将一并移除。已被业务记录引用的资料不能删除。
                </NPopconfirm>
              </div>
            </template>
          </VxeColumn>
          <template #empty>{{ query ? '没有匹配的物料。' : '暂无物料，请先新增。' }}</template>
        </VxeTable>
      </template>
    </WorkspaceTable>
  </section>
</template>
