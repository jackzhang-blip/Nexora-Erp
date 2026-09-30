<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NModal } from 'naive-ui'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

const store = usePiniaAppStore()
const { busy, error, notice, connectionLost, inventoryValuation,
  inventoryCostInputs, inventoryCostForm } = storeToRefs(store)
const { can, localTime, recordInventoryCost, refreshData, perform } = store
const showForm = ref(false)
const search = ref('')
const columns = [
  { key: 'material', title: '物料' }, { key: 'quantity', title: '现存数量' },
  { key: 'average', title: '移动平均单价' }, { key: 'amount', title: '库存金额' }
]
const sourceColumns = [
  { key: 'movement', title: '待核价流水' }, { key: 'material', title: '物料' },
  { key: 'quantity', title: '入库数量' }, { key: 'source', title: '来源' }
]
const historyColumns = [
  { key: 'movement', title: '流水' }, { key: 'price', title: '核定单价' },
  { key: 'reference', title: '依据与原因' }, { key: 'actor', title: '操作人及时间' }
]
const materials = computed(() => inventoryValuation.value?.materials.filter((item) =>
  `${item.sku} ${item.name}`.toLowerCase().includes(search.value.trim().toLowerCase())) ?? [])
const unpriced = computed(() => inventoryValuation.value?.movements.filter((item) =>
  inventoryValuation.value?.unpriced_movement_ids.includes(item.id)) ?? [])
const priceable = computed(() => inventoryValuation.value?.movements.filter((item) =>
  ['receipt', 'other_inbound', 'stocktake', 'adjustment', 'production_completion'].includes(item.source_type) &&
  (unpriced.value.some((missing) => missing.id === item.id) || item.cost_source === 'manual')) ?? [])
const materialName = (id: number): string => inventoryValuation.value?.materials.find(
  (item) => item.id === id)?.name ?? `物料 #${id}`

async function submitPrice(): Promise<void> {
  await submitCreateDialog(recordInventoryCost, { busy, error, notice }, showForm)
}
</script>

<template>
  <section class="stack">
    <!-- 页面说明随主标题展示，刷新和核价按钮共用筛选工具栏。 -->
    <WorkspaceTable :show-title="false" title="库存计价"
      :columns="columns" :data="materials">
      <template #actions>
        <button class="secondary" :disabled="busy" @click="perform(refreshData, '库存金额已刷新。')">刷新</button>
        <button v-if="can('inventory_valuation.record') && priceable.length" class="primary"
          :disabled="busy || connectionLost" @click="showForm = true">登记核价</button>
      </template>
      <template #filters><label>搜索物料<input v-model="search" placeholder="编码或名称" /></label></template>
      <template #beforeTable>
        <div class="summary-grid">
          <div class="metric"><span>库存总金额</span><strong>{{ inventoryValuation?.total_amount === null ? '待核价' : `¥${inventoryValuation?.total_amount ?? '0.00'}` }}</strong></div>
          <div class="metric"><span>待核价入库流水</span><strong>{{ unpriced.length }}</strong></div>
          <div class="metric"><span>核价修订记录</span><strong>{{ inventoryCostInputs.length }}</strong></div>
        </div>
        <NModal v-model:show="showForm" preset="card" :mask-closable="!busy"
          :style="{ width: 'min(680px, calc(100vw - 32px))' }">
          <form v-if="showForm && can('inventory_valuation.record')" class="stack" @submit.prevent="submitPrice">
            <h3>登记库存核价</h3>
            <p class="muted">每次修订都会保留原核价、依据、原因与操作人，并重算后续库存金额。</p>
            <div class="form-grid">
              <label>入库流水<select v-model.number="inventoryCostForm.movement_id" required>
                <option :value="0" disabled>选择待核价流水</option>
                <option v-for="item in priceable" :key="item.id" :value="item.id">#{{ item.id }} · {{ materialName(item.material_id) }} · {{ item.quantity }}{{ item.cost_source === 'manual' ? ' · 已核价，可修订' : '' }}</option>
              </select></label>
              <label>核定单价<input v-model="inventoryCostForm.unit_cost" type="number" min="0" max="1000000000" step="0.0001" required /></label>
              <label>依据编号<input v-model.trim="inventoryCostForm.reference" maxlength="100" required /></label>
              <label>核价原因<input v-model.trim="inventoryCostForm.reason" maxlength="200" required /></label>
            </div>
            <div class="form-actions">
              <button class="primary" :disabled="busy || connectionLost">保存核价</button>
              <button type="button" class="secondary" @click="showForm = false">取消</button>
            </div>
          </form>
        </NModal>
      </template>
      <template #cell-material="{ row: item }"><strong>{{ item.sku }}</strong><small>{{ item.name }}</small></template>
      <template #cell-quantity="{ row: item }">{{ item.quantity }} {{ item.unit }}</template>
      <template #cell-average="{ row: item }">{{ item.average_unit_cost ?? '待核价' }}</template>
      <template #cell-amount="{ row: item }">{{ item.amount === null ? '待核价' : `¥${item.amount}` }}</template>
    </WorkspaceTable>
    <WorkspaceTable title="待核价来源" description="历史无价入库、赠品及其他没有成本依据的入库需要人工核价。"
      :columns="sourceColumns" :data="unpriced">
      <template #cell-movement="{ row: item }">#{{ item.id }}</template>
      <template #cell-material="{ row: item }">{{ materialName(item.material_id) }}</template>
      <template #cell-quantity="{ row: item }">{{ item.quantity }}</template>
      <template #cell-source="{ row: item }">{{ item.source_type }} #{{ item.source_id }}</template>
    </WorkspaceTable>
    <WorkspaceTable title="核价修订历史" description="最新一条核价生效，历史记录仍可追溯。"
      :columns="historyColumns" :data="inventoryCostInputs">
      <template #cell-movement="{ row: item }">#{{ item.movement_id }}</template>
      <template #cell-price="{ row: item }">¥{{ item.unit_cost }}</template>
      <template #cell-reference="{ row: item }">{{ item.reference }}<small>{{ item.reason }}</small></template>
      <template #cell-actor="{ row: item }">{{ item.created_by_name }}<small>{{ localTime(item.created_at) }}</small></template>
    </WorkspaceTable>
  </section>
</template>
