<script setup lang="ts">
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { recordColumns, matchesRecordQuery } from '../../../utils/workspace-records'
import { computed, ref } from 'vue'
import { NModal } from 'naive-ui'
import { useAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  error,
  notice,
  busy,
  warehouses,
  shipments,
  salesReturns,
  salesReturnReversalReasons,
  salesReturnForm,
  can,
  selectedSalesReturnShipment,
  localTime,
  chooseSalesReturnShipment,
  createSalesReturn,
  postSalesReturn,
  cancelSalesReturn,
  reverseSalesReturn
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createSalesReturn, { busy, error, notice }, createOpen)
}
// 只筛选当前列表快照，原有单据状态与跨页面草稿保持不变。
const recordQuery = ref('')
const filteredRecords = computed(() =>
  salesReturns.value.filter((item) =>
    matchesRecordQuery(recordQuery.value, [
      item.id,
      item.customer_name,
      item.warehouse_name,
      item.created_by_name,
      item.reason,
      ...item.lines.map((line) => line.material_name)
    ])
  )
)
</script>

<template>
  <section class="stack">
    <NModal v-if="can('sales_return.create')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">SALES RETURN</p>
          <h2>新建销售退货单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="submitCreate">
        <div class="form-grid">
          <label
            >原出库单<select
              v-model.number="salesReturnForm.shipment_id"
              required
              @change="chooseSalesReturnShipment"
            >
              <option :value="0" disabled>选择可退货的出库单</option>
              <option
                v-for="item in shipments.filter(
                  (entry) =>
                    entry.status === 'posted' &&
                    entry.lines.some(
                      (line) => Number(line.returnable_quantity) > 0
                    )
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · {{ item.customer_name }} ·
                {{ item.warehouse_name }}
              </option>
            </select></label
          ><label
            >退回仓库<select
              v-model.number="salesReturnForm.warehouse_id"
              required
            >
              <option
                v-for="item in warehouses"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option>
            </select></label
          ><label
            >退货原因<input
              v-model.trim="salesReturnForm.reason"
              required
              maxlength="200"
          /></label>
        </div>
        <p class="muted">
          退货关联原出库明细；确认后新增入库流水，不修改原出库记录。金额按原销售单价计算，应收调整将在财务模块处理。
        </p>
        <div
          v-for="(line, index) in salesReturnForm.lines"
          :key="line.shipment_line_id"
          class="line-row"
        >
          <label
            >原出库物料<input
              :value="
                selectedSalesReturnShipment?.lines.find(
                  (item) => item.id === line.shipment_line_id
                )?.material_name
              "
              disabled /></label
          ><label
            >退货数量（最多
            {{
              selectedSalesReturnShipment?.lines.find(
                (item) => item.id === line.shipment_line_id
              )?.returnable_quantity
            }}）<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              :max="
                selectedSalesReturnShipment?.lines.find(
                  (item) => item.id === line.shipment_line_id
                )?.returnable_quantity
              "
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            @click="salesReturnForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="primary"
            type="submit"
            :disabled="
              busy || !salesReturnForm.lines.length || !warehouses.length
            "
          >
            保存草稿
          </button>
        </div>
      </form>
    </NModal>
    <!-- 主标题由工作台提供，列表复用仓库管理的筛选区、状态和单元格布局。 -->
    <WorkspaceTable
      :show-title="false"
      title="销售退货"
      :data="filteredRecords"
      :columns="recordColumns"
      :min-table-width="1100"
    >
      <template #actions>
        <button
          v-if="can('sales_return.create')"
          class="primary"
          type="button"
          :disabled="busy"
          @click="createOpen = true"
        >
          新建销售退货单
        </button>
      </template>
      <template #filters>
        <label>
          搜索销售退货
          <input v-model="recordQuery" placeholder="单号、名称或物料" />
        </label>
      </template>

      <template #cell-document="{ row: item }">
        <div>
          <strong>#{{ item.id }} · {{ item.customer_name }} · {{ item.warehouse_name }}</strong>
          <p class="muted">
            {{ localTime(item.created_at) }} · 原出库单 #{{ item.shipment_id }} · {{ item.reason }} ·
            创建人 {{ item.created_by_name }} · 原价金额 ¥{{ item.total_amount }}
            <span v-if="item.reversal_id">
              · 冲销 #{{ item.reversal_id }}（{{ item.reversal_reason }} ·
              {{ item.reversed_by_name }}）
            </span>
          </p>
        </div>
      </template>
      <template #cell-status="{ row: item }">
        <span class="pill" :class="item.status">
          {{
            item.reversal_id
              ? '已冲销'
              : item.status === 'posted'
                ? '已退货入库'
                : item.status === 'cancelled'
                  ? '已取消'
                  : '待确认'
          }}
        </span>
      </template>
      <template #cell-details="{ row: item }">
        <div class="workspace-record-lines">
          <span v-for="line in item.lines" :key="line.id">
            {{ line.material_name }} × {{ line.quantity }} {{ line.unit }} · ¥{{ line.line_total }}
          </span>
        </div>
      </template>
      <template #cell-actions="{ row: item }">
        <div class="form-actions">
          <button
            v-if="item.status === 'draft' && can('sales_return.post')"
            class="primary small"
            type="button"
            :disabled="busy"
            @click="postSalesReturn(item.id)"
          >
            确认退货
          </button>
          <button
            v-if="item.status === 'draft' && can('sales_return.cancel')"
            class="secondary small"
            type="button"
            :disabled="busy"
            @click="cancelSalesReturn(item.id)"
          >
            取消
          </button>
        </div>
        <form
          v-if="item.status === 'posted' && !item.reversal_id && can('sales_return.reverse')"
          class="inline-form"
          @submit.prevent="reverseSalesReturn(item.id)"
        >
          <label>
            冲销原因
            <input
              v-model.trim="salesReturnReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原退货为何需要冲销"
            />
          </label>
          <button class="secondary small" type="submit" :disabled="busy">冲销已确认退货</button>
        </form>
      </template>
      <template #empty>
        <strong>{{ recordQuery ? '没有匹配的记录' : '暂无销售退货记录' }}</strong>
        <span>
          {{
            recordQuery
              ? '可调整单号、名称或物料关键词后重新搜索。'
              : '业务记录生成后，可在这里查看明细与处理状态。'
          }}
        </span>
      </template>
    </WorkspaceTable>
  </section>
</template>
