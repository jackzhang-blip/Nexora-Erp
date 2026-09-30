<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { busy, connectionLost, error, warehouses, materials, ledgerQuery, ledgerResult } = storeToRefs(store)
const { queryLedger, localTime } = store
const ledgerError = ref('')
const columns = [
  { key: 'time', title: '时间' }, { key: 'warehouse', title: '仓库' },
  { key: 'material', title: '物料' }, { key: 'source', title: '来源单据' },
  { key: 'quantity', title: '变动' }, { key: 'balance', title: '筛选范围结余' }
]
// 期初期末汇总同样通过公共表格展示，避免查询页保留第二种表格实现。
const groupColumns = [
  { key: 'warehouse_name', title: '仓库' }, { key: 'material', title: '物料' },
  { key: 'opening', title: '期初' }, { key: 'closing', title: '期末' }
]
const sourceLabels: Record<string, string> = {
  receipt: '采购入库', receipt_reversal: '采购入库冲销',
  other_inbound: '其他入库', other_inbound_reversal: '其他入库冲销',
  other_outbound: '其他出库', other_outbound_reversal: '其他出库冲销',
  shipment: '销售出库', shipment_reversal: '销售出库冲销',
  purchase_return: '采购退货', purchase_return_reversal: '采购退货冲销',
  sales_return: '销售退货', sales_return_reversal: '销售退货冲销',
  transfer_in: '调拨入库', transfer_out: '调拨出库',
  transfer_reversal_in: '调拨入库冲销', transfer_reversal_out: '调拨出库冲销',
  adjustment: '库存调整', adjustment_reversal: '库存调整冲销',
  stocktake: '盘点', stocktake_reversal: '盘点冲销',
  material_issue: '生产领料', material_return: '生产退料',
  production_completion: '生产完工', production_completion_reversal: '生产完工冲销'
}
const sourceOptions = Object.entries(sourceLabels)
// 查询失败时隐藏上次筛选的结果，避免把旧流水误读为本次查询结果。
async function runLedgerQuery(): Promise<void> {
  ledgerError.value = ''
  await queryLedger()
  ledgerError.value = error.value
}

// 页面首次打开读取服务端结果；筛选和表格使用同一份台账快照。
onMounted(() => { void runLedgerQuery() })
</script>

<template>
  <section class="stack">
    <WorkspaceTable :show-title="false" :data="ledgerResult.rows" title="库存台账"
      :columns="columns" :error="ledgerError" :loading="busy" :min-table-width="1000">
      <template #filters>
        <label>仓库<select v-model.number="ledgerQuery.warehouse_id"><option :value="null">全部仓库</option><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label>物料<select v-model.number="ledgerQuery.material_id"><option :value="null">全部物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
        <label>开始日期<input v-model="ledgerQuery.from_date" type="date" /></label>
        <label>结束日期<input v-model="ledgerQuery.to_date" type="date" /></label>
        <label>来源<select v-model="ledgerQuery.source_type"><option :value="null">全部来源</option><option v-for="[key, label] in sourceOptions" :key="key" :value="key">{{ label }}</option></select></label>
        <button class="primary" :disabled="busy || connectionLost" @click="runLedgerQuery">查询台账</button>
      </template>
      <template #cell-time="{ row: item }">{{ localTime(item.created_at) }}<small>{{ item.created_by_name }}</small></template>
      <template #cell-warehouse="{ row: item }">{{ item.warehouse_name }}</template>
      <template #cell-material="{ row: item }">{{ item.sku }} · {{ item.material_name }}</template>
      <template #cell-source="{ row: item }">{{ sourceLabels[item.source_type] ?? item.source_type }} #{{ item.source_id }}<small>明细 #{{ item.source_line_id }}</small></template>
      <template #cell-quantity="{ row: item }">{{ item.quantity.startsWith('-') ? '' : '+' }}{{ item.quantity }} {{ item.unit }}</template>
      <template #cell-balance="{ row: item }">{{ item.balance_quantity }} {{ item.unit }}</template>
      <template #empty>
        <strong>筛选范围内暂无库存流水</strong>
        <span>可调整仓库、物料或日期后重新查询。</span>
      </template>
      <template #errorActions>
        <button class="secondary small" :disabled="busy || connectionLost" @click="runLedgerQuery">重新查询</button>
      </template>
    </WorkspaceTable>
    <!-- 先筛选再查看流水与汇总，避免期初期末把查询入口挤到页面下方。 -->
    <WorkspaceTable v-if="!ledgerError && ledgerResult.groups.length" title="期初期末" :columns="groupColumns" :data="ledgerResult.groups" :min-table-width="680">
      <template #cell-material="{ row }">{{ row.sku }} · {{ row.material_name }}</template>
      <template #cell-opening="{ row }">{{ row.opening_quantity }} {{ row.unit }}</template>
      <template #cell-closing="{ row }">{{ row.closing_quantity }} {{ row.unit }}</template>
    </WorkspaceTable>
  </section>
</template>
