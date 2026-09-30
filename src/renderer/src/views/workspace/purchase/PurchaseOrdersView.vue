<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
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
</script>

<template>
  <section class="stack">
    <div v-if="can('purchase_order.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PURCHASE ORDER</p>
          <h2>新建采购订单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="createPurchaseOrder">
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
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">ORDER LOG</p>
          <h2>采购订单</h2>
        </div>
      </div>
      <div v-if="!purchaseOrders.length" class="muted">暂无采购订单。</div>
      <article v-for="item in purchaseOrders" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong>#{{ item.id }} · {{ item.supplier_name }}</strong>
            <span v-if="item.purchase_request_id" class="muted"> · 采购申请 #{{ item.purchase_request_id }}</span>
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }}
              <span v-if="item.reference">· {{ item.reference }}</span> · 总额
              ¥{{ item.total_amount }}
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              {
                draft: '草稿',
                confirmed: '待入库',
                partially_received: '部分入库',
                received: '全部入库',
                cancelled: '已取消'
              }[item.status]
            }}</span
            ><button
              v-if="item.status === 'draft' && can('purchase_order.confirm')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="confirmPurchaseOrder(item.id)"
            >
              确认订单</button
            ><button
              v-if="
                ['draft', 'confirmed'].includes(item.status) &&
                can('purchase_order.cancel')
              "
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelPurchaseOrder(item.id)"
            >
              取消订单
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} 已入 {{ line.received_quantity }}/{{
              line.quantity
            }}
            {{ line.unit }} · 已退 {{ line.returned_quantity }} · 净入
            {{ line.net_received_quantity }} · ¥{{ line.unit_price }}/{{
              line.unit
            }}</span
          >
        </div>
      </article>
    </div>
  </section>
</template>
