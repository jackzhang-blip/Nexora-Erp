<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from './WorkspaceTable.vue'
import { usePiniaAppStore } from '../../store/app-store'

const props = defineProps<{ domain: 'purchase' | 'inventory' }>()
const store = usePiniaAppStore()
const { busy, connectionLost, suppliers, warehouses, materials,
  purchaseReportQuery, inventoryReportQuery,
  purchaseReportResult, inventoryReportResult } = storeToRefs(store)
const { queryPurchaseReport, queryInventoryReport,
  exportPurchaseReport, exportInventoryReport } = store
const query = computed(() => props.domain === 'purchase' ? purchaseReportQuery.value : inventoryReportQuery.value)
const result = computed(() => props.domain === 'purchase' ? purchaseReportResult.value : inventoryReportResult.value)
const kinds = props.domain === 'purchase'
  ? [{ value: 'purchase_requests', label: '采购申请执行' },
    { value: 'purchase_orders', label: '采购订单执行' },
    { value: 'receiving_returns', label: '采购收退货' }]
  : [{ value: 'inventory_balance', label: '库存余额' },
    { value: 'stock_flow', label: '收发存' }]
const title = props.domain === 'purchase' ? '采购报表' : '库存报表'
const run = (): Promise<void> => props.domain === 'purchase' ? queryPurchaseReport() : queryInventoryReport()
const exportCsv = (): Promise<void> => props.domain === 'purchase' ? exportPurchaseReport() : exportInventoryReport()
// 筛选变化后清除旧快照，避免用户把旧行误认为新条件的查询结果。
watch(query, () => {
  if (props.domain === 'purchase') purchaseReportResult.value = null
  else inventoryReportResult.value = null
}, { deep: true })
onMounted(() => { void run() })
</script>

<template>
  <WorkspaceTable :show-title="false" :title="title"
    :columns="result?.columns ?? []" :data="result?.rows ?? []" :loading="busy" :min-table-width="1050">
    <template #actions>
      <button class="secondary" :disabled="busy || connectionLost || !result" @click="exportCsv">导出 CSV</button>
    </template>
    <template #filters>
      <label>报表<select v-model="query.kind"><option v-for="item in kinds" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
      <label v-if="domain === 'purchase'">供应商<select v-model.number="query.supplier_id"><option :value="null">全部供应商</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label v-if="domain === 'inventory' || query.kind === 'receiving_returns'">仓库<select v-model.number="query.warehouse_id"><option :value="null">全部仓库</option><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label>物料<select v-model.number="query.material_id"><option :value="null">全部物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
      <label v-if="query.kind !== 'inventory_balance'">开始日期<input v-model="query.from_date" type="date" /></label>
      <label>{{ query.kind === 'inventory_balance' ? '截至日期' : '结束日期' }}<input v-model="query.to_date" type="date" /></label>
    </template>
    <template #filterActions><button class="primary" :disabled="busy || connectionLost" @click="run">查询</button></template>
    <template #empty>筛选范围内暂无记录。</template>
  </WorkspaceTable>
</template>
