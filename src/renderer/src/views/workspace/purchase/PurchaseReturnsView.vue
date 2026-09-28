<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  receipts,
  purchaseReturns,
  purchaseReturnForm,
  purchaseReturnReversalReasons,
  can,
  selectedPurchaseReturnReceipt,
  localTime,
  choosePurchaseReturnReceipt,
  createPurchaseReturn,
  postPurchaseReturn,
  cancelPurchaseReturn,
  reversePurchaseReturn
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('purchase_return.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PURCHASE RETURN</p>
          <h2>新建采购退货</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <p class="muted">
        退货从原入库仓库扣减。若货物已调走，请先调回；未关联采购订单的历史入库单不显示退货金额。
      </p>
      <form @submit.prevent="createPurchaseReturn">
        <div class="form-grid">
          <label
            >原入库单<select
              v-model.number="purchaseReturnForm.receipt_id"
              required
              @change="choosePurchaseReturnReceipt"
            >
              <option :value="0" disabled>选择可退货的入库单</option>
              <option
                v-for="item in receipts.filter(
                  (entry) =>
                    entry.status === 'posted' &&
                    entry.lines.some(
                      (line) => Number(line.returnable_quantity) > 0
                    )
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · {{ item.supplier_name }} ·
                {{ item.warehouse_name }}
              </option>
            </select></label
          ><label
            >退货原因<input
              v-model.trim="purchaseReturnForm.reason"
              required
              maxlength="200"
          /></label>
        </div>
        <h3>退货明细</h3>
        <div
          v-for="(line, index) in purchaseReturnForm.lines"
          :key="line.receipt_line_id"
          class="line-row"
        >
          <label
            >原入库物料<input
              :value="
                selectedPurchaseReturnReceipt?.lines.find(
                  (item) => item.id === line.receipt_line_id
                )?.material_name
              "
              disabled /></label
          ><label
            >退货数量（最多
            {{
              selectedPurchaseReturnReceipt?.lines.find(
                (item) => item.id === line.receipt_line_id
              )?.returnable_quantity
            }}）<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              :max="
                selectedPurchaseReturnReceipt?.lines.find(
                  (item) => item.id === line.receipt_line_id
                )?.returnable_quantity
              "
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            @click="purchaseReturnForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="primary"
            type="submit"
            :disabled="busy || !purchaseReturnForm.lines.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">RETURN LOG</p>
          <h2>采购退货记录</h2>
        </div>
      </div>
      <div v-if="!purchaseReturns.length" class="muted">暂无采购退货单。</div>
      <article v-for="item in purchaseReturns" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ item.supplier_name }} ·
              {{ item.warehouse_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 原入库单 #{{
                item.receipt_id
              }}
              · {{ item.reason }} · 创建人 {{ item.created_by_name }} · 原价金额
              {{
                item.total_amount === null ? '待核对' : `¥${item.total_amount}`
              }}<span v-if="item.reversal_id">
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
                  ? '已退供应商'
                  : item.status === 'cancelled'
                    ? '已取消'
                    : '待确认'
            }}</span
            ><button
              v-if="item.status === 'draft' && can('purchase_return.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postPurchaseReturn(item.id)"
            >
              确认退货</button
            ><button
              v-if="item.status === 'draft' && can('purchase_return.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelPurchaseReturn(item.id)"
            >
              取消
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} ·
            {{
              line.line_total === null ? '金额待核对' : `¥${line.line_total}`
            }}</span
          >
        </div>
        <form
          v-if="
            item.status === 'posted' &&
            !item.reversal_id &&
            can('purchase_return.reverse')
          "
          class="inline-form"
          @submit.prevent="reversePurchaseReturn(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="purchaseReturnReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原退货为何需要冲销" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销已确认退货
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
