<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { user, busy, connectionLost, warehouses, materials, stockAdjustments,
  adjustmentForm, adjustmentDecisionReasons, adjustmentReversalReasons } = storeToRefs(store)
const { can, localTime, createStockAdjustment, submitStockAdjustment,
  approveStockAdjustment, rejectStockAdjustment, cancelStockAdjustment,
  postStockAdjustment, reverseStockAdjustment } = store
const showForm = ref(false)
const query = ref('')
const filtered = computed(() => stockAdjustments.value.filter((item) =>
  [item.id, item.warehouse_name, item.reason, item.reference, ...item.lines.map((line) => line.material_name)]
    .join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const statusLabel = { draft: '草稿', submitted: '待审批', approved: '待仓库确认',
  rejected: '已驳回', cancelled: '已取消', posted: '已确认' }
const columns = [
  { key: 'document', title: '单据' }, { key: 'source', title: '仓库与原因' },
  { key: 'lines', title: '调整明细' }, { key: 'actions', title: '操作' }
]
</script>

<template>
  <section class="stack">
    <WorkspaceTable title="库存调整" description="调整量可正可负；建单人不能审批自己的单据。审批通过后由仓库确认才记库存流水。"
      :columns="columns" :row-count="filtered.length" :min-table-width="1050">
      <template #actions>
        <button v-if="can('adjustment.create')" class="primary" :disabled="busy || connectionLost" @click="showForm = true">新建调整</button>
      </template>
      <template #filters><label>搜索调整单<input v-model="query" placeholder="单号、仓库或物料" /></label></template>
      <template #beforeTable>
        <form v-if="showForm && can('adjustment.create')" class="stack" @submit.prevent="createStockAdjustment">
          <div class="form-grid">
            <label>仓库<select v-model.number="adjustmentForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
            <label>调整原因<input v-model.trim="adjustmentForm.reason" required maxlength="200" /></label>
            <label>参考号<input v-model.trim="adjustmentForm.reference" maxlength="100" /></label>
          </div>
          <div v-for="(line, index) in adjustmentForm.lines" :key="index" class="line-row">
            <label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
            <label>调整量<input v-model.trim="line.quantity" type="number" min="-1000000" max="1000000" step="0.001" required /></label>
            <button class="text-button" type="button" :disabled="adjustmentForm.lines.length === 1" @click="adjustmentForm.lines.splice(index, 1)">移除</button>
          </div>
          <div class="form-actions">
            <button class="secondary" type="button" @click="adjustmentForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button>
            <button class="primary" :disabled="busy || connectionLost">保存草稿</button>
            <button class="secondary" type="button" @click="showForm = false">收起</button>
          </div>
          <p class="muted">正数为增加，负数为减少；零调整量不会保存。</p>
        </form>
      </template>
      <template #rows>
        <tr v-for="item in filtered" :key="item.id">
          <td><strong>#{{ item.id }}</strong><small>{{ statusLabel[item.status] }}{{ item.reversal_id ? ' · 已冲销' : '' }}</small><small>{{ localTime(item.created_at) }} · {{ item.created_by_name }}</small><small v-if="item.reviewed_by_name">审批：{{ item.reviewed_by_name }}</small></td>
          <td>{{ item.warehouse_name }}<small>{{ item.reason }}</small><small v-if="item.reference">{{ item.reference }}</small><small v-if="item.review_reason">驳回：{{ item.review_reason }}</small></td>
          <td><div v-for="line in item.lines" :key="line.id">{{ line.material_name }} {{ line.quantity.startsWith('-') ? '' : '+' }}{{ line.quantity }} {{ line.unit }}</div></td>
          <td>
            <div class="form-actions">
              <button v-if="item.status === 'draft' && can('adjustment.submit')" class="primary small" :disabled="busy || connectionLost" @click="submitStockAdjustment(item.id)">提交</button>
              <button v-if="item.status === 'submitted' && can('adjustment.review') && user?.id !== item.created_by" class="primary small" :disabled="busy || connectionLost" @click="approveStockAdjustment(item.id)">批准</button>
              <button v-if="item.status === 'approved' && can('adjustment.post')" class="primary small" :disabled="busy || connectionLost" @click="postStockAdjustment(item.id)">仓库确认</button>
              <button v-if="['draft', 'submitted', 'approved', 'rejected'].includes(item.status) && can('adjustment.cancel')" class="secondary small" :disabled="busy || connectionLost" @click="cancelStockAdjustment(item.id)">取消</button>
            </div>
            <form v-if="item.status === 'submitted' && can('adjustment.review') && user?.id !== item.created_by" class="inline-form" @submit.prevent="rejectStockAdjustment(item.id)">
              <label>驳回原因<input v-model.trim="adjustmentDecisionReasons[item.id]" required maxlength="200" /></label><button class="secondary small" :disabled="busy || connectionLost">驳回</button>
            </form>
            <form v-if="item.status === 'posted' && !item.reversal_id && can('adjustment.reverse')" class="inline-form" @submit.prevent="reverseStockAdjustment(item.id)">
              <label>冲销原因<input v-model.trim="adjustmentReversalReasons[item.id]" required maxlength="200" /></label><button class="secondary small" :disabled="busy || connectionLost">冲销</button>
            </form><small v-if="item.reversal_reason">冲销：{{ item.reversal_reason }}</small>
          </td>
        </tr>
      </template>
      <template #empty>{{ query ? '没有匹配的库存调整单。' : '暂无库存调整单。' }}</template>
    </WorkspaceTable>
  </section>
</template>
