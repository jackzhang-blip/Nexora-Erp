<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  warehouses,
  stocktakes,
  stocktakeForm,
  stocktakeReversalReasons,
  can,
  localTime,
  createStocktake,
  postStocktake,
  cancelStocktake,
  reverseStocktake
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('stocktake.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">STOCKTAKE</p>
          <h2>新建盘点单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="createStocktake">
        <div class="form-grid">
          <label
            >盘点仓库<select
              v-model.number="stocktakeForm.warehouse_id"
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
            >盘点批次或备注（可选）<input
              v-model.trim="stocktakeForm.reference"
              maxlength="100"
          /></label>
        </div>
        <p class="muted">
          只填写实际清点数量。保存时记录账面数量；若确认前库存发生变化，系统会要求重新盘点。
        </p>
        <div
          v-for="(line, index) in stocktakeForm.lines"
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
            >实盘数量<input
              v-model.trim="line.counted_quantity"
              type="number"
              min="0"
              max="1000000"
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="stocktakeForm.lines.length === 1"
            @click="stocktakeForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="
              stocktakeForm.lines.push({
                material_id: 0,
                counted_quantity: '0'
              })
            "
          >
            添加明细</button
          ><button
            class="primary"
            type="submit"
            :disabled="busy || !materials.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">COUNT RECORDS</p>
          <h2>盘点记录</h2>
        </div>
      </div>
      <div v-if="!stocktakes.length" class="muted">暂无盘点单。</div>
      <article v-for="item in stocktakes" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong>#{{ item.id }} · {{ item.warehouse_name }}</strong>
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }}
              <span v-if="item.reference">· {{ item.reference }}</span>
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              item.reversal_id
                ? '已冲销'
                : item.status === 'posted'
                  ? '已确认'
                  : item.status === 'cancelled'
                    ? '已取消'
                    : '待确认'
            }}</span
            ><button
              v-if="item.status === 'draft' && can('stocktake.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postStocktake(item.id)"
            >
              确认差异</button
            ><button
              v-if="item.status === 'draft' && can('stocktake.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelStocktake(item.id)"
            >
              取消
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} · 账面 {{ line.book_quantity }} → 实盘
            {{ line.counted_quantity }} {{ line.unit }} · 差异
            {{ line.difference }}</span
          ><span v-if="item.reversal_id"
            >冲销 #{{ item.reversal_id }} · {{ item.reversal_reason }} ·
            {{ item.reversed_by_name }} ·
            {{ localTime(item.reversed_at!) }}</span
          >
        </div>
        <form
          v-if="
            item.status === 'posted' &&
            !item.reversal_id &&
            can('stocktake.reverse')
          "
          class="inline-form"
          @submit.prevent="reverseStocktake(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="stocktakeReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原盘点差异为何需要冲销" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销已确认盘点
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
