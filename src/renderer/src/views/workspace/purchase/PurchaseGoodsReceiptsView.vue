<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'

const store = usePiniaAppStore()
const { busy, connectionLost, purchaseOrders, goodsReceipts, warehouses, goodsReceiptForm } = storeToRefs(store)
const { can, localTime, chooseGoodsReceiptOrder, createGoodsReceipt, confirmGoodsReceipt,
  cancelGoodsReceipt } = store
const query = ref('')
const showForm = ref(false)
const selectedOrder = computed(() => purchaseOrders.value.find((item) => item.id === goodsReceiptForm.value.purchase_order_id))
const filtered = computed(() => goodsReceipts.value.filter((item) =>
  [item.id, item.purchase_order_id, item.supplier_name, item.reference, ...item.lines.map((line) => line.material_name)]
    .join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const columns = [
  { key: 'document', title: '收货单' }, { key: 'warehouse', title: '仓库与状态' },
  { key: 'lines', title: '收货明细' }, { key: 'actions', title: '操作' }
]
</script>

<template>
  <section class="stack">
    <WorkspaceTable title="采购收货" :columns="columns" :row-count="filtered.length" :min-table-width="940">
      <template #actions>
        <button v-if="can('purchase_receiving.create')" class="primary" :disabled="busy || connectionLost" @click="showForm = true">新建收货单</button>
      </template>
      <template #filters>
        <label>搜索收货单<input v-model="query" placeholder="单号、供应商或物料" /></label>
      </template>
      <template #beforeTable>
        <form v-if="showForm && can('purchase_receiving.create')" class="stack" @submit.prevent="createGoodsReceipt">
          <h3>记录本批采购收货</h3>
          <div class="form-grid">
            <label>采购订单<select v-model.number="goodsReceiptForm.purchase_order_id" required @change="chooseGoodsReceiptOrder">
              <option :value="0" disabled>选择待收货订单</option>
              <option v-for="order in purchaseOrders.filter((item) => ['confirmed', 'partially_received'].includes(item.status))" :key="order.id" :value="order.id">#{{ order.id }} · {{ order.supplier_name }}</option>
            </select></label>
            <label>目标仓库<select v-model.number="goodsReceiptForm.warehouse_id" required>
              <option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select></label>
            <label>送货参考号<input v-model.trim="goodsReceiptForm.reference" maxlength="100" /></label>
          </div>
          <p class="muted">仅合格实收数量生成待入库单；拒收数量不增加库存，须填写原因。</p>
          <div v-for="(line, index) in goodsReceiptForm.lines" :key="line.purchase_order_line_id" class="line-row">
            <span>{{ selectedOrder?.lines.find((item) => item.id === line.purchase_order_line_id)?.material_name }}</span>
            <label>合格实收<input v-model.trim="line.accepted_quantity" type="number" min="0" max="1000000" step="0.001" required /></label>
            <label>拒收数量<input v-model.trim="line.rejected_quantity" type="number" min="0" max="1000000" step="0.001" required /></label>
            <label>拒收原因<input v-model.trim="line.rejection_reason" maxlength="200" :required="Number(line.rejected_quantity) > 0" /></label>
            <button class="text-button" type="button" :disabled="goodsReceiptForm.lines.length === 1" @click="goodsReceiptForm.lines.splice(index, 1)">移除</button>
          </div>
          <div class="form-actions">
            <button class="primary" :disabled="busy || connectionLost || !goodsReceiptForm.lines.length">保存收货草稿</button>
            <button class="secondary" type="button" @click="showForm = false">收起</button>
          </div>
        </form>
      </template>
      <template #rows>
        <tr v-for="item in filtered" :key="item.id">
          <td><strong>#{{ item.id }} · {{ item.supplier_name }}</strong><small>{{ localTime(item.created_at) }}</small><small>采购订单 #{{ item.purchase_order_id }}<span v-if="item.reference"> · {{ item.reference }}</span></small></td>
          <td>{{ item.warehouse_name }}<small>{{ item.status === 'draft' ? '待确认收货' : item.status === 'cancelled' ? '已取消' : item.inbound_receipt_id ? '已确认收货' : '全数拒收' }}</small><small v-if="item.inbound_receipt_id">入库单 #{{ item.inbound_receipt_id }} · {{ item.inbound_reversal_id ? '已冲销' : item.inbound_status === 'posted' ? '已入库' : '待入库' }}</small></td>
          <td><div v-for="line in item.lines" :key="line.id">{{ line.material_name }}：合格 {{ line.accepted_quantity }}，拒收 {{ line.rejected_quantity }} {{ line.unit }}<small v-if="line.rejection_reason">{{ line.rejection_reason }}</small></div></td>
          <td><div class="form-actions">
            <button v-if="item.status === 'draft' && can('purchase_receiving.confirm')" class="primary small" :disabled="busy || connectionLost" @click="confirmGoodsReceipt(item.id)">确认收货</button>
            <button v-if="item.status === 'draft' && can('purchase_receiving.cancel')" class="secondary small" :disabled="busy || connectionLost" @click="cancelGoodsReceipt(item.id)">取消草稿</button>
          </div></td>
        </tr>
      </template>
      <template #empty>{{ query ? '没有匹配的采购收货单。' : '暂无采购收货单。' }}</template>
    </WorkspaceTable>
  </section>
</template>
