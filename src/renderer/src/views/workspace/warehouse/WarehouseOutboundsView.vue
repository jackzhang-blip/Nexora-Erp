<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { busy, connectionLost, materials, warehouses, warehouseOutbounds, otherOutboundForm,
  otherOutboundReversalReasons } = storeToRefs(store)
const { can, localTime, createOtherOutbound, postWarehouseOutbound, cancelOtherOutbound,
  reverseOtherOutbound } = store
const showForm = ref(false)
const query = ref('')
const filtered = computed(() => warehouseOutbounds.value.filter((item) =>
  [item.id, item.reference, item.warehouse_name, item.note, ...item.lines.map((line) => line.material_name)]
    .join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const reasonName = { scrap: '报废', sample: '样品', other: '其他', purchase_return: '采购退货' }
const columns = [
  { key: 'document', title: '单据' }, { key: 'source', title: '仓库与来源' },
  { key: 'lines', title: '物料明细' }, { key: 'actions', title: '操作' }
]
</script>

<template>
  <section class="stack">
    <WorkspaceTable title="仓库出库" :columns="columns" :row-count="filtered.length" :min-table-width="900">
      <template #actions>
        <button v-if="can('other_outbound.create')" class="primary" :disabled="busy || connectionLost" @click="showForm = true">新建仓库出库</button>
      </template>
      <template #filters>
        <label>搜索出库单<input v-model="query" placeholder="单号、仓库或物料" /></label>
      </template>
      <template #beforeTable>
        <form v-if="showForm && can('other_outbound.create')" class="stack" @submit.prevent="createOtherOutbound">
          <h3>其他用途出库</h3>
          <div class="form-grid">
            <label>仓库<select v-model.number="otherOutboundForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
            <label>用途<select v-model="otherOutboundForm.reason" required><option value="scrap">报废</option><option value="sample">样品</option><option value="other">其他</option></select></label>
            <label>参考号<input v-model.trim="otherOutboundForm.reference" maxlength="100" /></label>
            <label>出库说明<input v-model.trim="otherOutboundForm.note" required maxlength="200" /></label>
          </div>
          <div v-for="(line, index) in otherOutboundForm.lines" :key="index" class="line-row">
            <label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
            <label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label>
            <button class="text-button" type="button" :disabled="otherOutboundForm.lines.length === 1" @click="otherOutboundForm.lines.splice(index, 1)">移除</button>
          </div>
          <div class="form-actions">
            <button class="secondary" type="button" @click="otherOutboundForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button>
            <button class="primary" :disabled="busy || connectionLost">保存草稿</button>
            <button class="secondary" type="button" @click="showForm = false">收起</button>
          </div>
          <p class="muted">确认后才扣减库存；其他出库不产生采购应付。</p>
        </form>
      </template>
      <template #rows>
        <tr v-for="item in filtered" :key="item.id">
          <td><strong>#{{ item.id }}</strong><small>{{ localTime(item.created_at) }} · {{ item.created_by_name }}</small><small>{{ item.status === 'draft' ? '待确认' : item.status === 'cancelled' ? '已取消' : item.reversal_id ? '已冲销' : '已出库' }}</small></td>
          <td>{{ item.warehouse_name }} · {{ reasonName[item.reason] }}<small>{{ item.note }}</small><small v-if="item.reference">{{ item.reference }}</small></td>
          <td><div v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }}</div></td>
          <td><div class="form-actions">
            <button v-if="item.status === 'draft' && can('other_outbound.post')" class="primary small" :disabled="busy || connectionLost" @click="postWarehouseOutbound(item.id)">确认出库</button>
            <button v-if="item.status === 'draft' && can('other_outbound.cancel')" class="secondary small" :disabled="busy || connectionLost" @click="cancelOtherOutbound(item.id)">取消</button>
          </div>
          <form v-if="item.status === 'posted' && !item.reversal_id && can('other_outbound.reverse')" class="inline-form" @submit.prevent="reverseOtherOutbound(item.id)">
            <label>冲销原因<input v-model.trim="otherOutboundReversalReasons[item.id]" required maxlength="200" /></label>
            <button class="secondary small" :disabled="busy || connectionLost">冲销</button>
          </form><small v-if="item.reversal_reason">冲销：{{ item.reversal_reason }}</small></td>
        </tr>
      </template>
      <template #empty>{{ query ? '没有匹配的出库单。' : '暂无仓库出库单。' }}</template>
    </WorkspaceTable>
  </section>
</template>
