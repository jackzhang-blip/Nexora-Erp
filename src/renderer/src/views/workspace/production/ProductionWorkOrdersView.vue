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
  version,
  busy,
  boms,
  workOrders,
  warehouses,
  workOrderForm,
  can,
  localTime,
  createWorkOrder,
  releaseWorkOrder,
  cancelWorkOrder,
  selectIssueOrder,
  selectCompletionOrder
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createWorkOrder, { busy, error, notice }, createOpen)
}
// 只筛选当前列表快照，原有单据状态与跨页面草稿保持不变。
const recordQuery = ref('')
const filteredRecords = computed(() =>
  workOrders.value.filter((item) =>
    matchesRecordQuery(recordQuery.value, [
      item.id,
      item.product_name,
      item.product_sku,
      item.warehouse_name,
      item.created_by_name,
      item.reference,
      ...item.lines.map((line) => line.material_name)
    ])
  )
)
</script>

<template>
  <section class="stack">
    <NModal v-if="can('work_order.create')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PRODUCTION ORDERS</p>
          <h2>新建生产工单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <p class="muted">
        选择已启用的 BOM
        和目标产量。建单时会固定本次组件需求；仓库用于后续完工入库，目前不会改变库存。
      </p>
      <form @submit.prevent="submitCreate">
        <div class="form-grid">
          <label
            >启用的 BOM<select v-model.number="workOrderForm.bom_id" required>
              <option :value="0" disabled>选择成品与版本</option>
              <option
                v-for="item in boms.filter(
                  (entry) => entry.status === 'active'
                )"
                :key="item.id"
                :value="item.id"
              >
                {{ item.product_name }}（{{ item.product_sku }}）· V{{
                  item.version
                }}
              </option>
            </select></label
          ><label
            >完工目标仓库<select
              v-model.number="workOrderForm.warehouse_id"
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
            >目标产量<input
              v-model.trim="workOrderForm.target_quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><label
            >参考号（可选）<input
              v-model.trim="workOrderForm.reference"
              maxlength="100" /></label
          ><label
            >备注（可选）<input
              v-model.trim="workOrderForm.note"
              maxlength="200"
          /></label>
        </div>
        <button
          class="primary"
          type="submit"
          :disabled="
            busy ||
            !boms.some((item) => item.status === 'active') ||
            !warehouses.length
          "
        >
          保存工单草稿
        </button>
      </form>
    </NModal>
    <!-- 主标题由工作台提供，列表复用仓库管理的筛选区、状态和单元格布局。 -->
    <WorkspaceTable
      :show-title="false"
      title="生产工单"
      :data="filteredRecords"
      :columns="recordColumns"
      :min-table-width="1100"
    >
      <template #actions>
        <button
          v-if="can('work_order.create')"
          class="primary"
          type="button"
          :disabled="busy"
          @click="createOpen = true"
        >
          新建生产工单
        </button>
      </template>
      <template #filters>
        <label>
          搜索生产工单
          <input v-model="recordQuery" placeholder="单号、名称或物料" />
        </label>
      </template>

      <template #cell-document="{ row: item }">
        <div>
          <strong>
            #{{ item.id }} · {{ item.product_name }}（{{ item.product_sku }}）· BOM V{{
              item.bom_version
            }}
          </strong>
          <p class="muted">
            {{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} · 目标
            {{ item.target_quantity }} {{ item.product_unit }} · {{ item.warehouse_name }}
            <span v-if="item.reference">· {{ item.reference }}</span>
            <span v-if="item.note">· {{ item.note }}</span>
          </p>
        </div>
      </template>
      <template #cell-status="{ row: item }">
        <span class="pill" :class="item.status">
          {{
            {
              draft: '草稿',
              released: '已下达',
              in_progress: '生产中',
              completed: '已完工',
              cancelled: '已取消'
            }[item.status]
          }}
        </span>
      </template>
      <template #cell-details="{ row: item }">
        <div class="workspace-record-lines">
          <span>
            已报工 {{ item.reported_quantity }} · 合格 {{ item.accepted_quantity }} · 不合格
            {{ item.rejected_quantity }} · 待报工 {{ item.remaining_output_quantity }}
            {{ item.product_unit }}
          </span>
          <span v-for="line in item.lines" :key="line.id">
            {{ line.material_name }} · 需求 {{ line.required_quantity }} · 已领
            {{ line.issued_quantity }} · 剩余 {{ line.remaining_quantity }} {{ line.unit }}
          </span>
        </div>
      </template>
      <template #cell-actions="{ row: item }">
        <div class="form-actions">
          <button
            v-if="item.status === 'draft' && can('work_order.release')"
            class="primary small"
            type="button"
            :disabled="busy"
            @click="releaseWorkOrder(item.id)"
          >
            下达
          </button>
          <button
            v-if="
              (item.status === 'released' || item.status === 'in_progress') &&
              item.lines.some((line) => Number(line.remaining_quantity) > 0) &&
              can('material_issue.create')
            "
            class="secondary small"
            type="button"
            :disabled="busy"
            @click="selectIssueOrder(item.id)"
          >
            创建领料单
          </button>
          <button
            v-if="
              item.status === 'in_progress' &&
              Number(item.remaining_output_quantity) > 0 &&
              can('production_completion.create')
            "
            class="secondary small"
            type="button"
            :disabled="busy"
            @click="selectCompletionOrder(item.id)"
          >
            创建完工单
          </button>
          <button
            v-if="(item.status === 'draft' || item.status === 'released') && can('work_order.cancel')"
            class="secondary small"
            type="button"
            :disabled="busy"
            @click="cancelWorkOrder(item.id)"
          >
            取消
          </button>
        </div>
      </template>
      <template #empty>
        <strong>{{ recordQuery ? '没有匹配的记录' : '暂无生产工单记录' }}</strong>
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
