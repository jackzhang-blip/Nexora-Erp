<script setup lang="ts">
import { recordColumns, matchesRecordQuery } from '../../../utils/workspace-records'
import { computed, ref } from 'vue'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  productionCostReport,
  materialValuationForm,
  productionChargeForm,
  costReversalReasons,
  can,
  localTime,
  recordMaterialValuation,
  recordProductionCharge,
  reverseProductionCost
} = useAppStore()
// 分别搜索工单与成本记录，不改变待核价及冲销金额的展示。
const costQuery = ref('')
const entryQuery = ref('')
const costColumns = recordColumns.filter((column) => column.key !== 'actions')
const filteredOrders = computed(() =>
  (productionCostReport.value?.orders ?? []).filter((item) =>
    matchesRecordQuery(costQuery.value, [item.work_order_id, item.product_name])
  )
)
const filteredEntries = computed(() =>
  (productionCostReport.value?.entries ?? []).filter((item) =>
    matchesRecordQuery(entryQuery.value, [
      item.id,
      item.work_order_id,
      item.material_name,
      item.reference,
      item.created_by_name
    ])
  )
)
</script>

<template>
  <section class="stack">
    <!-- 成本金额与冲销记录复用共享表格，核价规则保持原样。 -->
    <WorkspaceTable
      :show-title="false"
      title="生产成本"
      :columns="costColumns"
      :data="filteredOrders"
      :min-table-width="800"
    >
      <template #filters>
        <label>
          搜索生产工单
          <input v-model="costQuery" placeholder="输入编号或名称" />
        </label>
      </template>
      <template #cell-document="{ row: item }">
        <strong>工单 #{{ item.work_order_id }} · {{ item.product_name }}</strong>
      </template>
      <template #cell-status="{ row: item }">
        <span class="pill">
          {{
            item.work_order_status === 'draft'
              ? '未下达'
              : item.total_amount === null
                ? '待核价'
                : '当前已知'
          }}
        </span>
      </template>
      <template #cell-details="{ row: item }">
        <div class="workspace-record-lines">
          <span>材料已知金额 ¥{{ item.known_material_amount }}</span>
          <span>人工 ¥{{ item.labor_amount }}</span>
          <span>制造费用 ¥{{ item.overhead_amount }}</span>
          <span>总成本 {{ item.total_amount === null ? '待核价' : `¥${item.total_amount}` }}</span>
          <span v-if="item.unpriced_issue_count">待核价领料 {{ item.unpriced_issue_count }} 条</span>
        </div>
      </template>

      <template #empty>{{ costQuery ? '没有匹配的记录。' : '暂无生产工单。' }}</template>
    </WorkspaceTable>
    <div v-if="can('production_cost.record')" class="two-columns">
      <div class="card">
        <div class="section-heading"><h2>核定领料单价</h2></div>
        <form @submit.prevent="recordMaterialValuation">
          <div class="form-grid">
            <label
              >待核价领料<select
                v-model.number="materialValuationForm.material_issue_line_id"
                required
              >
                <option :value="0" disabled>选择领料明细</option>
                <option
                  v-for="line in productionCostReport?.unpriced_lines ?? []"
                  :key="line.material_issue_line_id"
                  :value="line.material_issue_line_id"
                >
                  工单 #{{ line.work_order_id }} · 领料 #{{
                    line.material_issue_id
                  }}
                  · {{ line.material_name }} · 净领 {{ line.net_quantity }}
                  {{ line.unit }}
                </option>
              </select></label
            ><label
              >核定单价（元）<input
                v-model.trim="materialValuationForm.unit_cost"
                type="number"
                min="0"
                max="1000000000"
                step="0.0001"
                required /></label
            ><label
              >依据编号<input
                v-model.trim="materialValuationForm.reference"
                maxlength="100"
                required
                placeholder="发票或内部核价单编号" /></label
            ><label
              >说明（可选）<input
                v-model.trim="materialValuationForm.note"
                maxlength="200"
            /></label>
          </div>
          <button
            class="primary"
            type="submit"
            :disabled="busy || !materialValuationForm.material_issue_line_id"
          >
            保存核价
          </button>
        </form>
      </div>
      <div class="card">
        <div class="section-heading"><h2>登记人工或制造费用</h2></div>
        <form @submit.prevent="recordProductionCharge">
          <div class="form-grid">
            <label
              >生产工单<select
                v-model.number="productionChargeForm.work_order_id"
                required
              >
                <option :value="0" disabled>选择已下达工单</option>
                <option
                  v-for="item in (productionCostReport?.orders ?? []).filter(
                    (entry) =>
                      entry.work_order_status !== 'draft' &&
                      entry.work_order_status !== 'cancelled'
                  )"
                  :key="item.work_order_id"
                  :value="item.work_order_id"
                >
                  #{{ item.work_order_id }} · {{ item.product_name }}
                </option>
              </select></label
            ><label
              >费用类别<select v-model="productionChargeForm.kind">
                <option value="labor">人工</option>
                <option value="overhead">制造费用</option>
              </select></label
            ><label
              >金额（元）<input
                v-model.trim="productionChargeForm.amount"
                type="number"
                min="0.01"
                max="1000000000000"
                step="0.01"
                required /></label
            ><label
              >依据编号<input
                v-model.trim="productionChargeForm.reference"
                maxlength="100"
                required /></label
            ><label
              >说明（可选）<input
                v-model.trim="productionChargeForm.note"
                maxlength="200"
            /></label>
          </div>
          <button
            class="primary"
            type="submit"
            :disabled="busy || !productionChargeForm.work_order_id"
          >
            登记费用
          </button>
        </form>
      </div>
    </div>
    <!-- 成本金额与冲销记录复用共享表格，核价规则保持原样。 -->
    <WorkspaceTable
      title="成本记录与冲销"
      :columns="recordColumns"
      :data="filteredEntries"
      :min-table-width="1100"
    >
      <template #filters>
        <label>
          搜索成本记录
          <input v-model="entryQuery" placeholder="输入编号或名称" />
        </label>
      </template>
      <template #cell-document="{ row: item }">
        <div>
          <strong>
            #{{ item.id }} · 工单 #{{ item.work_order_id }} ·
            {{ { material: '材料核价', labor: '人工', overhead: '制造费用' }[item.kind] }}
          </strong>
          <p class="muted">
            {{ localTime(item.created_at) }} · {{ item.created_by_name }} · 依据 {{ item.reference }}
          </p>
        </div>
      </template>
      <template #cell-status="{ row: item }">
        <span class="pill">{{ item.status === 'active' ? '有效' : '已冲销' }}</span>
      </template>
      <template #cell-details="{ row: item }">
        <div class="workspace-record-lines">
          <span v-if="item.kind === 'material'">
            {{ item.material_name }}（{{ item.material_sku }}）· 净领 {{ item.net_quantity }} · 单价
            ¥{{ item.unit_cost }}
          </span>
          <span>
            当前计入 {{ item.current_amount === null ? '已冲销' : `¥${item.current_amount}` }}
          </span>
          <span v-if="item.note">{{ item.note }}</span>
          <span v-if="item.reversal_id">
            冲销原因：{{ item.reversal_reason }} · {{ item.reversed_by_name }} ·
            {{ localTime(item.reversed_at!) }}
          </span>
        </div>
      </template>
      <template #cell-actions="{ row: item }">
        <form
          v-if="item.status === 'active' && can('production_cost.reverse')"
          class="inline-form"
          @submit.prevent="reverseProductionCost(item.id)"
        >
          <label>
            冲销原因
            <input v-model.trim="costReversalReasons[item.id]" required maxlength="200" />
          </label>
          <button class="secondary small" type="submit" :disabled="busy">冲销记录</button>
        </form>
      </template>
      <template #empty>{{ entryQuery ? '没有匹配的记录。' : '暂无成本记录。' }}</template>
    </WorkspaceTable>
  </section>
</template>
