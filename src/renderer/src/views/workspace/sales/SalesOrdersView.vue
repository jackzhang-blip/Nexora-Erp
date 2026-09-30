<script setup lang="ts">
import { ref } from 'vue'
import { NModal } from 'naive-ui'
import { useAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  error,
  notice,
  busy,
  materials,
  customers,
  salesOrders,
  customerForm,
  salesForm,
  can,
  localTime,
  createCustomer,
  createSalesOrder,
  confirmSalesOrder,
  cancelSalesOrder
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
const customerOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createSalesOrder, { busy, error, notice }, createOpen)
}
async function submitCustomer(): Promise<void> {
  await submitCreateDialog(createCustomer, { busy, error, notice }, customerOpen)
}
</script>

<template>
  <section class="stack">
    <div v-if="can('customer.manage')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">CUSTOMERS</p>
          <h2>客户资料</h2>
        </div>
        <button class="primary" type="button" :disabled="busy" @click="customerOpen = true">新增客户</button>
      </div>
      <NModal v-model:show="customerOpen" preset="card" title="新增客户" :mask-closable="!busy" :style="{ width: 'min(560px, calc(100vw - 32px))' }">
      <form class="inline-form" @submit.prevent="submitCustomer">
        <label
          >客户名称<input
            v-model.trim="customerForm.name"
            required
            maxlength="120"
            placeholder="输入客户名称" /></label
        ><button class="primary" type="submit" :disabled="busy">
          添加客户
        </button>
      </form>
      </NModal>
      <div class="receipt-lines">
        <span v-for="item in customers" :key="item.id">{{ item.name }}</span>
      </div>
    </div>
    <div class="form-actions"><button v-if="can('sales_order.create')" class="primary" type="button" :disabled="busy" @click="createOpen = true">新建销售订单</button></div>
    <NModal v-if="can('sales_order.create')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">SALES ORDER</p>
          <h2>新建销售订单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="submitCreate">
        <div class="form-grid">
          <label
            >客户<select v-model.number="salesForm.customer_id" required>
              <option :value="0" disabled>选择客户</option>
              <option v-for="item in customers" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select></label
          ><label
            >参考单号（可选）<input
              v-model.trim="salesForm.reference"
              maxlength="100"
          /></label>
        </div>
        <h3>销售明细</h3>
        <div
          v-for="(line, index) in salesForm.lines"
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
            :disabled="salesForm.lines.length === 1"
            @click="salesForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="
              salesForm.lines.push({
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
            :disabled="busy || !customers.length || !materials.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </NModal>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">SALES LOG</p>
          <h2>销售订单</h2>
        </div>
      </div>
      <div v-if="!salesOrders.length" class="muted">暂无销售订单。</div>
      <article v-for="item in salesOrders" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong>#{{ item.id }} · {{ item.customer_name }}</strong>
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
                confirmed: '待出库',
                partially_shipped: '部分出库',
                shipped: '全部出库',
                cancelled: '已取消'
              }[item.status]
            }}</span
            ><button
              v-if="item.status === 'draft' && can('sales_order.confirm')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="confirmSalesOrder(item.id)"
            >
              确认订单</button
            ><button
              v-if="
                ['draft', 'confirmed'].includes(item.status) &&
                can('sales_order.cancel')
              "
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelSalesOrder(item.id)"
            >
              取消订单
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} · 已出库 {{ line.shipped_quantity }}/{{
              line.quantity
            }}
            · 已退 {{ line.returned_quantity }} · 净交付
            {{ line.net_delivered_quantity }} {{ line.unit }} · ¥{{
              line.unit_price
            }}/{{ line.unit }}</span
          >
        </div>
      </article>
    </div>
  </section>
</template>
