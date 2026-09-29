<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import type { Supplier } from '../../../../../shared/erp-api'
import { usePiniaAppStore } from '../../../store/app-store'
import './catalog.css'

const store = usePiniaAppStore()
const { busy, connectionLost, suppliers, materials, supplierMaterials } = storeToRefs(store)
const { can, saveSupplier, deleteSupplier } = store
const query = ref('')
const editingId = ref<number | undefined>()
const showForm = ref(false)
const form = reactive({ name: '' })
const filtered = computed(() => suppliers.value.filter(item => [item.name].join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
function edit(item?: Supplier): void {
  editingId.value = item?.id
  Object.assign(form, item ? { name: item.name } : { name: '' })
  showForm.value = true
}
async function save(): Promise<void> {
  if (await saveSupplier({ ...form }, editingId.value)) showForm.value = false
}
const selectedId = ref(0)
const materialQuery = ref('')
const boundQuery = ref('')
const materialId = ref(0)
const selectedSupplier = computed(() => suppliers.value.find(item => item.id === selectedId.value))
const boundIds = computed(() => new Set(supplierMaterials.value.filter(link => link.supplier_id === selectedId.value).map(link => link.material_id)))
const boundMaterials = computed(() => materials.value.filter(item => boundIds.value.has(item.id) && `${item.sku} ${item.name}`.toLowerCase().includes(boundQuery.value.trim().toLowerCase())))
const availableMaterials = computed(() => materials.value.filter(item => !boundIds.value.has(item.id) && `${item.sku} ${item.name}`.toLowerCase().includes(materialQuery.value.trim().toLowerCase())))
watch(selectedId, () => { materialId.value = 0; materialQuery.value = ''; boundQuery.value = '' })
async function bindMaterial(): Promise<void> {
  if (!materialId.value || !selectedSupplier.value) return
  await store.setSupplierMaterial(selectedId.value, materialId.value, true)
  if (boundIds.value.has(materialId.value)) materialId.value = 0
}
</script>

<template>
  <section class="stack catalog-page">
    <div class="card">
      <div class="section-heading">
        <div><p class="eyebrow">SUPPLIERS</p><h2>供应商列表 <span class="pill">{{ suppliers.length }}</span></h2></div>
        <button v-if="can('catalog.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增供应商</button>
      </div>
      <label class="catalog-search">搜索供应商<input v-model="query" placeholder="输入名称搜索" /></label>
      <form v-if="showForm && can('catalog.manage')" class="catalog-editor" @submit.prevent="save">
        <h3>{{ editingId ? '编辑供应商' : '新增供应商' }}</h3>
        <div class="form-grid">
          <label>供应商名称<input v-model.trim="form.name" required maxlength="120" /></label>
        </div>
        <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">保存</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
      </form>
      <p class="muted">选择“供货物料”管理供应商与现有物料的绑定。</p>
      <div class="table-wrap"><table>
        <thead><tr><th>供应商名称</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in filtered" :key="item.id">
            <td>{{ item.name }}</td>
            <td><div class="catalog-actions"><button class="text-button" type="button" @click="selectedId = item.id">供货物料</button>
              <template v-if="can('catalog.manage')">
                <button class="text-button" :disabled="busy || connectionLost" @click="edit(item)">编辑</button>
                <NPopconfirm positive-text="确认" negative-text="取消" @positive-click="deleteSupplier(item.id)">
                  <template #trigger><button class="text-button" :disabled="busy || connectionLost">删除</button></template>
                  确认删除“{{ item.name }}”？关联的供货关系将一并移除。已被业务记录引用的资料不能删除。
                </NPopconfirm>
              </template>
            </div></td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="2" class="muted">{{ query ? '没有匹配的供应商。' : '暂无供应商，请先新增。' }}</td></tr>
        </tbody>
      </table></div>
    </div>
    <div v-if="selectedSupplier" class="card">
      <div class="section-heading"><h2>{{ selectedSupplier.name }} · 供货物料</h2><button class="text-button" @click="selectedId = 0">关闭</button></div>
      <p class="muted">绑定现有物料；同一物料可以同时绑定多家供应商。解绑只移除供货关系。</p>
      <form v-if="can('catalog.manage')" class="inline-form" @submit.prevent="bindMaterial">
        <label>搜索可绑定物料<input v-model="materialQuery" placeholder="物料编码、名称或规格" /></label>
        <label>选择物料<select v-model.number="materialId" required>
          <option :value="0" disabled>请选择物料</option>
          <option v-for="item in availableMaterials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }} · {{ item.unit }}</option>
        </select></label>
        <button class="primary" :disabled="busy || connectionLost || !materialId">绑定物料</button>
        <span v-if="!availableMaterials.length" class="muted">没有匹配的未绑定物料，可先到物料管理添加。</span>
      </form>
      <label class="catalog-search">搜索已绑定物料<input v-model="boundQuery" placeholder="物料编码、名称或规格" /></label>
      <div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>单位</th><th>操作</th></tr></thead><tbody>
        <tr v-for="item in boundMaterials" :key="item.id"><td>{{ item.sku }}</td><td>{{ item.name }}</td><td>{{ item.unit }}</td><td>
          <NPopconfirm positive-text="确认" negative-text="取消" v-if="can('catalog.manage')" @positive-click="store.setSupplierMaterial(selectedId, item.id, false)">
            <template #trigger><button class="text-button" :disabled="busy || connectionLost">解绑</button></template>解除此物料与供应商的供货关系？
          </NPopconfirm>
        </td></tr>
        <tr v-if="!boundMaterials.length"><td colspan="4" class="muted">{{ boundQuery ? '没有匹配的已绑定物料。' : '尚未绑定物料。' }}</td></tr>
      </tbody></table></div>
    </div>
  </section>
</template>
