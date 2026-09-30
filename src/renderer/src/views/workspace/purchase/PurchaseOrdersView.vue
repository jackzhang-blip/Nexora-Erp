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
  materials,
  suppliers,
  purchaseOrders,
  purchaseForm,
  can,
  localTime,
  createPurchaseOrder,
  confirmPurchaseOrder,
  cancelPurchaseOrder
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createPurchaseOrder, { busy, error, notice }, createOpen)
}
// 只筛选当前列表快照，原有单据状态与跨页面草稿保持不变。
const recordQuery = ref('')
const filteredRecords = computed(() =>
  purchaseOrders.value.filter((item) =>
    matchesRecordQuery(recordQuery.value, [
      item.id,
      item.supplier_name,
      item.created_by_name,
      item.reference,
      ...item.lines.map((line) => line.material_name)
    ])
  )
)
</script>

<template>
  <section class="stack">
    <NModal v-if="can('purchase_order.create')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PURCHASE ORDER</p>
          <h2>新建采购订单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="submitCreate">
        <div class="form-grid">
          <label
            >供应商<select v-model.number="purchaseForm.supplier_id" required>
              <option :value="0" disabled>选择供应商</option>
              <option v-for="item in suppliers" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select></label
          ><label
            >参考单号（可选）<input
              v-model.trim="purchaseForm.reference"
              maxlength="100"
          /></label>
        </div>
        <h3>采购明细</h3>
        <div
          v-for="(line, index) in purchaseForm.lines"
          :key="index"
          class="line-row"
        >
          <label
            >物料<select v-model.number="line.material_id" required>
              <option :value="0" disabled>选择物料</option>
              <option v-for="item in materials" :key="item.id" :value="item.id">
                {{ item.sku }} · {{ item.name }}
              </option>
            </select></label
          ><label
            >数量<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><label
            >单价（元）<input
              v-model.trim="line.unit_price"
              type="number"
              min="0"
              max="1000000000"
              step="0.0001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="purchaseForm.lines.length === 1"
            @click="purchaseForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="
              purchaseForm.lines.push({
                material_id: 0,
                quantity: '1',
                unit_price: '0'
              })
            "
          >
            添加明细</button
          ><button
            class="primary"
            type="submit"
            :disabled="busy || !suppliers.length || !materials.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </NModal>
    <!-- 主标题由工作台提供，列表复用仓库管理的筛选区、状态和单元格布局。 -->
    <WorkspaceTable
      :show-title="false"
      title="采购订单"
      :data="filteredRecords"
      :columns="recordColumns"
      :min-table-width="1100"
    >
      <template #actions>
        <button
          v-if="can('purchase_order.create')"
          class="primary"
          type="button"
          :disabled="busy"
          @click="createOpen = true"
        >
          新建采购订单
        </button>
      </template>
      <template #filters>
        <label>
          搜索采购订单
          <input v-model="recordQuery" placeholder="单号、名称或物料" />
        </label>
      </template>

      <template #cell-document="{ row: item }">
        <div>
          <strong>#{{ item.id }} · {{ item.supplier_name }}</strong>
          <span v-if="item.purchase_request_id" class="muted">
            · 采购申请 #{{ item.purchase_request_id }}
          </span>
          <p class="muted">
            {{ localTime(item.created_at) }} · 创建人
            {{ item.created_by_name }}
            <span v-if="item.reference">· {{ item.reference }}</span>
            · 总额 ¥{{ item.total_amount }}
          </p>
        </div>
      </template>
      <template #cell-status="{ row: item }">
        <span class="pill" :class="item.status">
          {{
            {
              draft: '草稿',
              confirmed: '待入库',
              partially_received: '部分入库',
              received: '全部入库',
              cancelled: '已取消'
            }[item.status]
          }}
        </span>
      </template>
      <template #cell-details="{ row: item }">
        <div class="workspace-record-lines">
          <span v-for="line in item.lines" :key="line.id">
            {{ line.material_name }} 已入 {{ line.received_quantity }}/{{ line.quantity }}
            {{ line.unit }} · 已退 {{ line.returned_quantity }} · 净入
            {{ line.net_received_quantity }} · ¥{{ line.unit_price }}/{{ line.unit }}
          </span>
        </div>
      </template>
      <template #cell-actions="{ row: item }">
        <div class="form-actions">
          <button
            v-if="item.status === 'draft' && can('purchase_order.confirm')"
            class="primary small"
            type="button"
            :disabled="busy"
            @click="confirmPurchaseOrder(item.id)"
          >
            确认订单
          </button>
          <button
            v-if="['draft', 'confirmed'].includes(item.status) && can('purchase_order.cancel')"
            class="secondary small"
            type="button"
            :disabled="busy"
            @click="cancelPurchaseOrder(item.id)"
          >
            取消订单
          </button>
        </div>
      </template>
      <template #empty>
        <strong>{{ recordQuery ? '没有匹配的记录' : '暂无采购订单记录' }}</strong>
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
