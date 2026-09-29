<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 入库确认沿用原单据接口；新建采购入库草稿由采购收货确认时自动完成。
const {
  busy,
  receipts,
  receiptReversalReasons,
  can,
  localTime,
  postReceipt,
  reverseReceipt
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">RECEIPT LOG</p>
          <h2>入库单</h2>
        </div>
      </div>
      <p class="muted">确认采购收货后，合格数量会生成待入库单；仓库在此确认实物入库。</p>
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
              <span v-if="item.goods_receipt_id">· 采购收货 #{{ item.goods_receipt_id }}</span>
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
