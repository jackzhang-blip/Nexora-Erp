<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { busy, connectionLost, warehouses, materials, ledgerQuery, ledgerResult } = storeToRefs(store)
const { queryLedger, localTime } = store
const columns = [
  { key: 'time', title: '时间' }, { key: 'warehouse', title: '仓库' },
  { key: 'material', title: '物料' }, { key: 'source', title: '来源单据' },
  { key: 'quantity', title: '变动' }, { key: 'balance', title: '筛选范围结余' }
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
  stocktake: '盘点', stocktake_reversal: '盘点冲销',
  material_issue: '生产领料', material_return: '生产退料',
  production_completion: '生产完工', production_completion_reversal: '生产完工冲销'
}
const sourceOptions = Object.entries(sourceLabels)
// 页面首次打开读取服务端结果；筛选和表格使用同一份台账快照。
onMounted(() => { void queryLedger() })
</script>

<template>
  <section class="stack">
    <WorkspaceTable title="库存台账" description="按仓库和物料核对期初、每笔变动及期末。选择来源后显示该来源范围内的累计数量。"
      :columns="columns" :row-count="ledgerResult.rows.length" :loading="busy" :min-table-width="1000">
      <template #filters>
        <label>仓库<select v-model.number="ledgerQuery.warehouse_id"><option :value="null">全部仓库</option><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label>物料<select v-model.number="ledgerQuery.material_id"><option :value="null">全部物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
        <label>开始日期<input v-model="ledgerQuery.from_date" type="date" /></label>
        <label>结束日期<input v-model="ledgerQuery.to_date" type="date" /></label>
        <label>来源<select v-model="ledgerQuery.source_type"><option :value="null">全部来源</option><option v-for="[key, label] in sourceOptions" :key="key" :value="key">{{ label }}</option></select></label>
        <button class="primary" :disabled="busy || connectionLost" @click="queryLedger">查询</button>
      </template>
      <template #beforeTable>
        <div v-if="ledgerResult.groups.length" class="table-wrap">
          <table aria-label="库存台账期初期末"><thead><tr><th>仓库</th><th>物料</th><th>期初</th><th>期末</th></tr></thead>
            <tbody><tr v-for="item in ledgerResult.groups" :key="`${item.warehouse_id}-${item.material_id}`">
              <td>{{ item.warehouse_name }}</td><td>{{ item.sku }} · {{ item.material_name }}</td>
              <td>{{ item.opening_quantity }} {{ item.unit }}</td><td>{{ item.closing_quantity }} {{ item.unit }}</td>
            </tr></tbody></table>
        </div>
      </template>
      <template #rows>
        <tr v-for="item in ledgerResult.rows" :key="item.id">
          <td>{{ localTime(item.created_at) }}<small>{{ item.created_by_name }}</small></td>
          <td>{{ item.warehouse_name }}</td><td>{{ item.sku }} · {{ item.material_name }}</td>
          <td>{{ sourceLabels[item.source_type] ?? item.source_type }} #{{ item.source_id }}<small>明细 #{{ item.source_line_id }}</small></td>
          <td>{{ item.quantity.startsWith('-') ? '' : '+' }}{{ item.quantity }} {{ item.unit }}</td>
          <td>{{ item.balance_quantity }} {{ item.unit }}</td>
        </tr>
      </template>
      <template #empty>筛选范围内暂无库存流水。</template>
    </WorkspaceTable>
  </section>
</template>
