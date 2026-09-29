<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import type { Material } from '../../../../../shared/erp-api'
import { usePiniaAppStore } from '../../../store/app-store'
import './catalog.css'

const store = usePiniaAppStore()
const { busy, connectionLost, materials, suppliers, supplierMaterials } = storeToRefs(store)
const { can, saveMaterial, deleteMaterial } = store
const query = ref('')
const editingId = ref<number | undefined>()
const showForm = ref(false)
const form = reactive({ sku: '', name: '', unit: '件' })
const filtered = computed(() => materials.value.filter(item => [item.sku, item.name, item.unit].join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
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
    <div class="card">
      <div class="section-heading">
        <div><p class="eyebrow">MATERIALS</p><h2>物料列表 <span class="pill">{{ materials.length }}</span></h2></div>
        <button v-if="can('catalog.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增物料</button>
      </div>
      <label class="catalog-search">搜索物料<input v-model="query" placeholder="输入名称或编码搜索" /></label>
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
      <div class="table-wrap"><table>
        <thead><tr><th>物料编码</th><th>名称（可包含规格型号）</th><th>单位</th><th>供应商</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in filtered" :key="item.id">
            <td>{{ item.sku }}</td><td>{{ item.name }}</td><td>{{ item.unit }}</td><td>{{ supplierNames(item.id) }}</td>
            <td><div class="catalog-actions">
              <template v-if="can('catalog.manage')">
                <button class="text-button" :disabled="busy || connectionLost" @click="edit(item)">编辑</button>
                <NPopconfirm positive-text="确认" negative-text="取消" @positive-click="deleteMaterial(item.id)">
                  <template #trigger><button class="text-button" :disabled="busy || connectionLost">删除</button></template>
                  确认删除“{{ item.name }}”？关联的供货关系将一并移除。已被业务记录引用的资料不能删除。
                </NPopconfirm>
              </template>
            </div></td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="5" class="muted">{{ query ? '没有匹配的物料。' : '暂无物料，请先新增。' }}</td></tr>
        </tbody>
      </table></div>
    </div>
  </section>
</template>
