<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  stock,
  movements,
  receipts,
  warehouses,
  selectedWarehouseId,
  refreshData,
  perform
} = useAppStore()
// 当前库存统一使用公共表格，数量列保留业务单位。
const columns = [{ key: 'sku', title: '物料编码' }, { key: 'name', title: '物料名称' }, { key: 'quantity', title: '数量' }]
</script>

<template>
  <section class="stack">
    <WorkspaceTable :show-title="false" title="库存总览" description="按仓库查看物料当前库存，数量随已确认的出入库单据更新。" :columns="columns" :data="stock">
      <template #filters>
        <label>仓库<select v-model.number="selectedWarehouseId" :disabled="busy" @change="perform(refreshData, '库存已切换。')">
          <option :value="0">全部仓库</option>
          <option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select></label>
        <button class="primary" :disabled="busy" @click="perform(refreshData, '数据已刷新。')">刷新库存</button>
      </template>
      <template #beforeTable>
        <div class="summary-grid">
          <div class="metric">
            <span>物料种类</span><strong>{{ materials.length }}</strong>
          </div>
          <div class="metric">
            <span>已确认入库单</span
            ><strong>{{
              receipts.filter((item) => item.status === 'posted').length
            }}</strong>
          </div>
          <div class="metric">
            <span>库存流水</span><strong>{{ movements.length }}</strong>
          </div>
        </div>
      </template>
      <template #cell-quantity="{ row }"><strong>{{ row.quantity }}</strong> {{ row.unit }}</template>
      <template #empty>暂无物料，先到基础资料中添加。</template>
    </WorkspaceTable>
  </section>
</template>
