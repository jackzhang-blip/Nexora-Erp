<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  suppliers,
  receipts,
  purchaseOrders,
  warehouses,
  receiptForm,
  receiptReversalReasons,
  can,
  localTime,
  addLine,
  removeLine,
  createReceipt,
  chooseReceiptOrder,
  postReceipt,
  reverseReceipt
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('receipt.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PURCHASE RECEIPT</p>
          <h2>新建入库单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="createReceipt">
        <div class="form-grid">
          <label
            >关联采购订单（可选）<select
              v-model.number="receiptForm.purchase_order_id"
              @change="chooseReceiptOrder"
            >
              <option :value="null">不关联订单</option>
              <option
                v-for="item in purchaseOrders.filter((entry) =>
                  ['confirmed', 'partially_received'].includes(entry.status)
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · {{ item.supplier_name }}
              </option>
            </select></label
          ><label
            >供应商<select
              v-model.number="receiptForm.supplier_id"
              :disabled="receiptForm.purchase_order_id !== null"
              required
            >
              <option :value="0" disabled>选择供应商</option>
              <option v-for="item in suppliers" :key="item.id" :value="item.id">
                {{ item.name }}
              </option>
            </select></label
          ><label
            >入库仓库<select v-model.number="receiptForm.warehouse_id" required>
              <option
                v-for="item in warehouses"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option>
            </select></label
          ><label
            >外部单号（可选）<input
              v-model.trim="receiptForm.reference"
              maxlength="100"
              placeholder="采购单或送货单号"
          /></label>
        </div>
        <h3>入库明细</h3>
        <div
          v-for="(line, index) in receiptForm.lines"
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
          ><button
            class="text-button"
            type="button"
            :disabled="receiptForm.lines.length === 1"
            @click="removeLine(index)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button class="secondary" type="button" @click="addLine">
            添加明细</button
          ><button
            class="primary"
            type="submit"
            :disabled="busy || !materials.length || !suppliers.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">RECEIPT LOG</p>
          <h2>入库单</h2>
        </div>
      </div>
      <div v-if="!receipts.length" class="muted">暂无入库单。</div>
      <article v-for="item in receipts" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ item.supplier_name }} ·
              {{ item.warehouse_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }}
              <span v-if="item.purchase_order_id"
                >· 采购订单 #{{ item.purchase_order_id }}</span
              >
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
                  ? '已入库'
                  : '待确认'
            }}</span
            ><button
              v-if="item.status === 'draft' && can('receipt.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postReceipt(item.id)"
            >
              确认入库
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} ·
            已退 {{ line.returned_quantity }}</span
          >
        </div>
        <form
          v-if="
            item.status === 'posted' &&
            !item.reversal_id &&
            can('receipt.reverse')
          "
          class="inline-form"
          @submit.prevent="reverseReceipt(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="receiptReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原入库为何需要冲销" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销已确认入库
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
