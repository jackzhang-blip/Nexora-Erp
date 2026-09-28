<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  warehouses,
  salesOrders,
  shipments,
  shipmentReversalReasons,
  shipmentForm,
  can,
  localTime,
  chooseShipmentOrder,
  createShipment,
  postShipment,
  cancelShipment,
  reverseShipment
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('shipment.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">SALES SHIPMENT</p>
          <h2>新建出库单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="createShipment">
        <div class="form-grid">
          <label
            >销售订单<select
              v-model.number="shipmentForm.sales_order_id"
              required
              @change="chooseShipmentOrder"
            >
              <option :value="0" disabled>选择待出库订单</option>
              <option
                v-for="item in salesOrders.filter((entry) =>
                  ['confirmed', 'partially_shipped'].includes(entry.status)
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · {{ item.customer_name }}
              </option>
            </select></label
          ><label
            >出库仓库<select
              v-model.number="shipmentForm.warehouse_id"
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
            >参考单号（可选）<input
              v-model.trim="shipmentForm.reference"
              maxlength="100"
          /></label>
        </div>
        <p class="muted">
          确认出库时将从所选仓库扣减库存，并再次核对销售订单剩余数量。
        </p>
        <div
          v-for="(line, index) in shipmentForm.lines"
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
            >出库数量<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="shipmentForm.lines.length === 1"
            @click="shipmentForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="shipmentForm.lines.push({ material_id: 0, quantity: '1' })"
          >
            添加明细</button
          ><button
            class="primary"
            type="submit"
            :disabled="
              busy ||
              !materials.length ||
              !salesOrders.some((entry) =>
                ['confirmed', 'partially_shipped'].includes(entry.status)
              )
            "
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">SHIPMENT LOG</p>
          <h2>出库单</h2>
        </div>
      </div>
      <div v-if="!shipments.length" class="muted">暂无出库单。</div>
      <article v-for="item in shipments" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ item.customer_name }} ·
              {{ item.warehouse_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 销售订单 #{{
                item.sales_order_id
              }}
              · 创建人 {{ item.created_by_name }}
              <span v-if="item.reference">· {{ item.reference }}</span
              ><span v-if="item.reversal_id">
                · 冲销 #{{ item.reversal_id }}（{{ item.reversal_reason }} ·
                {{ item.reversed_by_name }}）</span
              >
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              item.reversal_id
                ? '已冲销'
                : item.status === 'posted'
                  ? '已出库'
                  : item.status === 'cancelled'
                    ? '已取消'
                    : '待确认'
            }}</span
            ><button
              v-if="item.status === 'draft' && can('shipment.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postShipment(item.id)"
            >
              确认出库</button
            ><button
              v-if="item.status === 'draft' && can('shipment.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelShipment(item.id)"
            >
              取消
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} ·
            已退 {{ line.returned_quantity }} · 可退
            {{ line.returnable_quantity }}</span
          >
        </div>
        <form
          v-if="
            item.status === 'posted' &&
            !item.reversal_id &&
            can('shipment.reverse')
          "
          class="inline-form"
          @submit.prevent="reverseShipment(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="shipmentReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原出库为何需要冲销" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销已确认出库
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
