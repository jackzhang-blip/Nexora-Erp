<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NPopconfirm } from 'naive-ui'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { busy, connectionLost, materials, suppliers, purchaseRequests, purchaseRequestForm,
  requestConversionForm, requestRejectReasons } = storeToRefs(store)
const { can, localTime, editPurchaseRequest, savePurchaseRequest, submitPurchaseRequest,
  approvePurchaseRequest, rejectPurchaseRequest, cancelPurchaseRequest,
  selectRequestConversion, convertPurchaseRequest } = store
const query = ref('')
const showForm = ref(false)
const filtered = computed(() => purchaseRequests.value.filter((item) =>
  [item.id, item.reference, item.note, item.status, ...item.lines.map((line) => line.material_name)]
    .join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const selectedRequest = computed(() => purchaseRequests.value.find((item) => item.id === requestConversionForm.value.requestId))
const columns = [
  { key: 'id', title: '申请' }, { key: 'status', title: '状态' },
  { key: 'lines', title: '明细与待转数量' }, { key: 'actions', title: '操作' }
]
const statusName = { draft: '草稿', submitted: '待审批', approved: '已批准', rejected: '已驳回', cancelled: '已取消' }

function openEditor(requestId?: number): void {
  editPurchaseRequest(requestId)
  showForm.value = true
}

async function save(): Promise<void> {
  await savePurchaseRequest()
  // 写入失败时保留输入；只有服务端刷新后的申请已存在才关闭表单。
  if (!store.error && !store.connectionLost) showForm.value = false
}
</script>

<template>
  <section class="stack">
    <WorkspaceTable title="采购申请" :columns="columns" :row-count="filtered.length" :min-table-width="940">
      <template #actions>
        <button v-if="can('purchase_request.create')" class="primary" :disabled="busy || connectionLost || !materials.length" @click="openEditor()">新建采购申请</button>
      </template>
      <template #filters>
        <label>搜索申请<input v-model="query" placeholder="单号、物料或状态" /></label>
      </template>
      <template #beforeTable>
        <form v-if="showForm && can('purchase_request.create')" class="stack" @submit.prevent="save">
          <h3>{{ purchaseRequestForm.requestId ? '修改采购申请' : '新建采购申请' }}</h3>
          <div class="form-grid">
            <label>参考单号<input v-model.trim="purchaseRequestForm.reference" maxlength="100" /></label>
            <label>采购说明<input v-model.trim="purchaseRequestForm.note" maxlength="500" /></label>
          </div>
          <div v-for="(line, index) in purchaseRequestForm.lines" :key="index" class="line-row">
            <label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option>
              <option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option>
            </select></label>
            <label>申请数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label>
            <button class="text-button" type="button" :disabled="purchaseRequestForm.lines.length === 1" @click="purchaseRequestForm.lines.splice(index, 1)">移除</button>
          </div>
          <div class="form-actions">
            <button class="secondary" type="button" @click="purchaseRequestForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button>
            <button class="primary" :disabled="busy || connectionLost">保存草稿</button>
            <button class="secondary" type="button" @click="showForm = false">收起</button>
          </div>
        </form>
        <form v-if="selectedRequest && can('purchase_order.create')" class="stack" @submit.prevent="convertPurchaseRequest">
          <h3>申请 #{{ selectedRequest.id }} 转采购订单</h3>
          <div class="form-grid">
            <label>供应商<select v-model.number="requestConversionForm.supplier_id" required><option :value="0" disabled>选择供应商</option>
              <option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select></label>
            <label>参考单号<input v-model.trim="requestConversionForm.reference" maxlength="100" /></label>
          </div>
          <p class="muted">本批不采购的明细填 0；可再次从剩余数量生成其他订单。</p>
          <div v-for="line in requestConversionForm.lines" :key="line.purchase_request_line_id" class="line-row">
            <span>{{ selectedRequest.lines.find((item) => item.id === line.purchase_request_line_id)?.material_name }}</span>
            <label>本次数量<input v-model.trim="line.quantity" type="number" min="0" max="1000000" step="0.001" required /></label>
            <label>单价（元）<input v-model.trim="line.unit_price" type="number" min="0" max="1000000000" step="0.0001" required /></label>
          </div>
          <div class="form-actions">
            <button class="primary" :disabled="busy || connectionLost || !requestConversionForm.lines.some((line) => Number(line.quantity) > 0)">生成订单草稿</button>
            <button class="secondary" type="button" @click="selectRequestConversion(0)">收起</button>
          </div>
        </form>
      </template>
      <template #rows>
        <tr v-for="item in filtered" :key="item.id">
          <td><strong>#{{ item.id }}</strong><small v-if="item.reference">{{ item.reference }}</small><small>{{ localTime(item.created_at) }} · {{ item.created_by_name }}</small></td>
          <td><span class="pill" :class="item.status">{{ statusName[item.status] }}</span><small v-if="item.review_reason">{{ item.review_reason }}</small></td>
          <td><div v-for="line in item.lines" :key="line.id">{{ line.material_name }}：申请 {{ line.quantity }} {{ line.unit }}，待转 {{ line.remaining_quantity }}</div></td>
          <td><div class="form-actions">
            <button v-if="['draft', 'rejected'].includes(item.status) && can('purchase_request.create')" class="text-button" :disabled="busy || connectionLost" @click="openEditor(item.id)">修改</button>
            <button v-if="item.status === 'draft' && can('purchase_request.submit')" class="text-button" :disabled="busy || connectionLost" @click="submitPurchaseRequest(item.id)">提交审批</button>
            <button v-if="item.status === 'submitted' && can('purchase_request.review')" class="text-button" :disabled="busy || connectionLost" @click="approvePurchaseRequest(item.id)">批准</button>
            <button v-if="item.status === 'approved' && can('purchase_order.create') && item.lines.some((line) => Number(line.remaining_quantity) > 0)" class="text-button" :disabled="busy || connectionLost" @click="selectRequestConversion(item.id)">转订单</button>
            <NPopconfirm v-if="item.status !== 'cancelled' && can('purchase_request.cancel')" positive-text="确认" negative-text="返回" @positive-click="cancelPurchaseRequest(item.id)">
              <template #trigger><button class="text-button" :disabled="busy || connectionLost">取消申请</button></template>
              已关联有效订单的申请无法取消。确认取消这张申请？
            </NPopconfirm>
          </div>
          <form v-if="item.status === 'submitted' && can('purchase_request.review')" class="inline-form" @submit.prevent="rejectPurchaseRequest(item.id)">
            <label>驳回原因<input v-model.trim="requestRejectReasons[item.id]" required maxlength="200" /></label>
            <button class="secondary small" :disabled="busy || connectionLost">驳回</button>
          </form></td>
        </tr>
      </template>
      <template #empty>{{ query ? '没有匹配的采购申请。' : '暂无采购申请。' }}</template>
    </WorkspaceTable>
  </section>
</template>
