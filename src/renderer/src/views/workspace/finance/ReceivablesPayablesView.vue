<script setup lang="ts">
import { computed, ref } from 'vue'
import { matchesRecordQuery } from '../../../utils/workspace-records'
import { storeToRefs } from 'pinia'
import { usePiniaAppStore } from '../../../store/app-store'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'

// 应收应付只负责汇总与订单核对，三个财务页面仍读取同一份服务端快照。
const store = usePiniaAppStore()
const { receivablesPayables, financeAccounts } = storeToRefs(store)
const { navigateToRoute } = store
const accountQuery = ref('')
const accountColumns = [
  { key: 'kind', title: '类别' },
  { key: 'party', title: '往来单位' },
  { key: 'order', title: '订单' },
  { key: 'business', title: '业务净额' },
  { key: 'settled', title: '收付款净额' },
  { key: 'outstanding', title: '未结金额' },
  { key: 'sources', title: '来源明细' }
]
const filteredAccounts = computed(() =>
  financeAccounts.value.filter((item) =>
    matchesRecordQuery(accountQuery.value, [item.order_id, item.party_name])
  )
)
</script>

<template>
  <section v-if="receivablesPayables" class="stack">
    <WorkspaceTable
      :show-title="false"
      title="订单核对"
      :columns="accountColumns"
      :data="filteredAccounts"
      :min-table-width="980"
    >
      <template #actions>
        <button class="secondary" type="button" @click="navigateToRoute('financePayments')">收付款记录</button>
        <button class="secondary" type="button" @click="navigateToRoute('financeSources')">查看金额来源</button>
      </template>
      <template #filters>
        <label>
          搜索订单
          <input v-model="accountQuery" placeholder="输入编号或名称" />
        </label>
      </template>
      <template #beforeTable>
        <div class="summary-grid">
          <div class="metric">
            <span>业务应收净额</span>
            <strong>¥{{ receivablesPayables.receivable_amount }}</strong>
          </div>
          <div class="metric">
            <span>业务应付净额</span>
            <strong>¥{{ receivablesPayables.payable_amount }}</strong>
          </div>
          <div class="metric">
            <span>待定价明细</span>
            <strong>{{ receivablesPayables.unpriced_count }}</strong>
          </div>
        </div>
        <p class="muted">
          未结金额 = 已确认业务净额 − 收付款净额。负数表示应退客户或应收供应商退款。
        </p>
      </template>
      <template #cell-kind="{ row: item }">
        {{ item.kind === 'receivable' ? '应收' : '应付' }}
      </template>
      <template #cell-party="{ row: item }">{{ item.party_name }}</template>
      <template #cell-order="{ row: item }">#{{ item.order_id }}</template>
      <template #cell-business="{ row: item }">¥{{ item.business_amount }}</template>
      <template #cell-settled="{ row: item }">¥{{ item.settled_amount }}</template>
      <template #cell-outstanding="{ row: item }">
        <strong>¥{{ item.outstanding_amount }}</strong>
      </template>
      <template #cell-sources="{ row: item }">{{ item.source_keys.length }} 笔</template>
      <template #empty>暂无可核对的订单金额。</template>
    </WorkspaceTable>
  </section>
</template>
