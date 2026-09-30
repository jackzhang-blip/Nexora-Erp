<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { NModal, NPopconfirm } from 'naive-ui'
import type { Supplier } from '../../../../../shared/erp-api'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'
import { usePagedQuery } from '../../../composables/use-paged-query'
import './catalog.css'

const store = usePiniaAppStore()
const { busy, error, notice, connectionLost, suppliers, materials, supplierMaterials } = storeToRefs(store)
const { can, saveSupplier, deleteSupplier } = store
const query = ref('')
const editingId = ref<number | undefined>()
const showForm = ref(false)
const form = reactive({ name: '' })
// 列表从服务端分页获取；全量供应商快照仅供其他业务选项和供货关系使用。
const { rows, total, page, pageSize, loading, error: queryError, load, search } = usePagedQuery<Supplier>(async params => {
  if (!window.nexora) throw new Error('服务连接不可用，请重新连接后重试。')
  return window.nexora.callApi('querySuppliers', params)
})
watch(query, search)
// 写入后的统一快照刷新、断线恢复都会重新查询当前页。
watch([suppliers, connectionLost], () => { void load() }, { immediate: true })
// 主列表与供货物料明细共用表格外壳，绑定关系的操作仍留在本页。
const supplierColumns = [
  { key: 'name', title: '供应商名称' },
  { key: 'actions', title: '操作' }
]
const materialColumns = [
  { key: 'sku', title: '编码' },
  { key: 'name', title: '名称' },
  { key: 'unit', title: '单位' },
  { key: 'actions', title: '操作' }
]
function edit(item?: Supplier): void {
  editingId.value = item?.id
  Object.assign(form, item ? { name: item.name } : { name: '' })
  showForm.value = true
}
async function save(): Promise<void> {
  if (await saveSupplier({ ...form }, editingId.value)) showForm.value = false
}
const selectedId = ref(0)
const bindOpen = ref(false)
const materialQuery = ref('')
const boundQuery = ref('')
const materialId = ref(0)
const selectedSupplier = computed(() => suppliers.value.find(item => item.id === selectedId.value))
const boundIds = computed(() => new Set(supplierMaterials.value.filter(link => link.supplier_id === selectedId.value).map(link => link.material_id)))
const boundMaterials = computed(() => materials.value.filter(item => boundIds.value.has(item.id) && `${item.sku} ${item.name}`.toLowerCase().includes(boundQuery.value.trim().toLowerCase())))
const availableMaterials = computed(() => materials.value.filter(item => !boundIds.value.has(item.id) && `${item.sku} ${item.name}`.toLowerCase().includes(materialQuery.value.trim().toLowerCase())))
watch(selectedId, () => { bindOpen.value = false; materialId.value = 0; materialQuery.value = ''; boundQuery.value = '' })
async function bindMaterial(): Promise<void> {
  if (!materialId.value || !selectedSupplier.value) return
  await store.setSupplierMaterial(selectedId.value, materialId.value, true)
  if (boundIds.value.has(materialId.value)) materialId.value = 0
}
async function submitBinding(): Promise<void> {
  await submitCreateDialog(bindMaterial, { busy, error, notice }, bindOpen)
}
</script>

<template>
  <section class="stack catalog-page">
    <!-- 主标题和说明统一由工作台外壳展示。 -->
    <WorkspaceTable :show-title="false" :data="rows" :loading="loading" :error="queryError" :pagination="{ page, pageSize, total, disabled: connectionLost }" @page-change="load" title="供应商列表" :columns="supplierColumns" :min-table-width="360">
      <template #actions>
        <button v-if="can('catalog.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增供应商</button>
      </template>
      <template #filters>
        <label class="catalog-search">搜索供应商<input v-model="query" placeholder="输入名称搜索" maxlength="120" /></label>
      </template>
      <template #errorActions><button class="secondary" type="button" :disabled="loading || connectionLost" @click="load()">重新查询</button></template>
      <template #beforeTable>
        <NModal v-model:show="showForm" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
        <form v-if="showForm && can('catalog.manage')" class="catalog-editor" @submit.prevent="save">
          <h3>{{ editingId ? '编辑供应商' : '新增供应商' }}</h3>
          <div class="form-grid">
            <label>供应商名称<input v-model.trim="form.name" required maxlength="120" /></label>
          </div>
          <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">保存</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
        </form>
        </NModal>

      </template>
      <template #cell-name="{ row: item }">{{ item.name }}</template>
      <template #cell-actions="{ row: item }"><div class="catalog-actions"><button class="text-button" type="button" @click="selectedId = item.id">供货物料</button>
            <template v-if="can('catalog.manage')">
              <button class="text-button" :disabled="busy || connectionLost" @click="edit(item)">编辑</button>
              <NPopconfirm positive-text="确认" negative-text="取消" @positive-click="deleteSupplier(item.id)">
                <template #trigger><button class="text-button" :disabled="busy || connectionLost">删除</button></template>
                确认删除“{{ item.name }}”？关联的供货关系将一并移除。已被业务记录引用的资料不能删除。
              </NPopconfirm>
            </template>
          </div></template>
      <template #empty>{{ query ? '没有匹配的供应商。' : '暂无供应商，请先新增。' }}</template>
    </WorkspaceTable>
    <WorkspaceTable :data="boundMaterials" v-if="selectedSupplier" :title="`${selectedSupplier.name} · 供货物料`" description="绑定现有物料；同一物料可以同时绑定多家供应商。解绑只移除供货关系。" :columns="materialColumns" :min-table-width="580">
      <template #actions>
        <button v-if="can('catalog.manage')" class="primary" type="button" :disabled="busy || connectionLost" @click="bindOpen = true">绑定物料</button>
        <button class="text-button" type="button" @click="selectedId = 0">关闭</button>
      </template>
      <!-- 辅助列表也使用同一工具栏，说明和弹窗不占用筛选条件区域。 -->
      <template #filters>
        <label class="catalog-search">搜索已绑定物料<input v-model="boundQuery" placeholder="物料编码、名称或规格" /></label>
      </template>
      <template #beforeTable>
          <NModal v-model:show="bindOpen" preset="card" title="绑定物料" :mask-closable="!busy" :style="{ width: 'min(760px, calc(100vw - 32px))' }">
          <form v-if="can('catalog.manage')" class="inline-form" @submit.prevent="submitBinding">
            <label>搜索可绑定物料<input v-model="materialQuery" placeholder="物料编码、名称或规格" /></label>
            <label>选择物料<select v-model.number="materialId" required>
              <option :value="0" disabled>请选择物料</option>
              <option v-for="item in availableMaterials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }} · {{ item.unit }}</option>
            </select></label>
            <button class="primary" :disabled="busy || connectionLost || !materialId">绑定物料</button>
            <span v-if="!availableMaterials.length" class="muted">没有匹配的未绑定物料，可先到物料管理添加。</span>
          </form>
          </NModal>
      </template>
      <template #cell-sku="{ row: item }">{{ item.sku }}</template>
      <template #cell-name="{ row: item }">{{ item.name }}</template>
      <template #cell-unit="{ row: item }">{{ item.unit }}</template>
      <template #cell-actions="{ row: item }"><NPopconfirm v-if="can('catalog.manage')" positive-text="确认" negative-text="取消" @positive-click="store.setSupplierMaterial(selectedId, item.id, false)">
            <template #trigger><button class="text-button" :disabled="busy || connectionLost">解绑</button></template>解除此物料与供应商的供货关系？
          </NPopconfirm></template>
      <template #empty>{{ boundQuery ? '没有匹配的已绑定物料。' : '尚未绑定物料。' }}</template>
    </WorkspaceTable>
  </section>
</template>
