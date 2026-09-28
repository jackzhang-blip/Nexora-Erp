<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  productionCostReport,
  materialValuationForm,
  productionChargeForm,
  costReversalReasons,
  can,
  localTime,
  recordMaterialValuation,
  recordProductionCharge,
  reverseProductionCost
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PRODUCTION COST</p>
          <h2>工单成本归集</h2>
        </div>
      </div>
      <p class="muted">
        材料单价由财务按凭据人工核定，金额按已领减已退数量计算。存在待核价领料时，总成本显示待核价；这不是库存计价或总账凭证。
      </p>
      <div v-if="!productionCostReport?.orders.length" class="muted">
        暂无生产工单。
      </div>
      <article
        v-for="item in productionCostReport?.orders ?? []"
        :key="item.work_order_id"
        class="receipt"
      >
        <div class="receipt-head">
          <strong
            >工单 #{{ item.work_order_id }} · {{ item.product_name }}</strong
          ><span class="pill">{{
            item.work_order_status === 'draft'
              ? '未下达'
              : item.total_amount === null
                ? '待核价'
                : '当前已知'
          }}</span>
        </div>
        <div class="receipt-lines">
          <span>材料已知金额 ¥{{ item.known_material_amount }}</span
          ><span>人工 ¥{{ item.labor_amount }}</span
          ><span>制造费用 ¥{{ item.overhead_amount }}</span
          ><span
            >总成本
            {{
              item.total_amount === null ? '待核价' : `¥${item.total_amount}`
            }}</span
          ><span v-if="item.unpriced_issue_count"
            >待核价领料 {{ item.unpriced_issue_count }} 条</span
          >
        </div>
      </article>
    </div>
    <div v-if="can('production_cost.record')" class="two-columns">
      <div class="card">
        <div class="section-heading"><h2>核定领料单价</h2></div>
        <form @submit.prevent="recordMaterialValuation">
          <div class="form-grid">
            <label
              >待核价领料<select
                v-model.number="materialValuationForm.material_issue_line_id"
                required
              >
                <option :value="0" disabled>选择领料明细</option>
                <option
                  v-for="line in productionCostReport?.unpriced_lines ?? []"
                  :key="line.material_issue_line_id"
                  :value="line.material_issue_line_id"
                >
                  工单 #{{ line.work_order_id }} · 领料 #{{
                    line.material_issue_id
                  }}
                  · {{ line.material_name }} · 净领 {{ line.net_quantity }}
                  {{ line.unit }}
                </option>
              </select></label
            ><label
              >核定单价（元）<input
                v-model.trim="materialValuationForm.unit_cost"
                type="number"
                min="0"
                max="1000000000"
                step="0.0001"
                required /></label
            ><label
              >依据编号<input
                v-model.trim="materialValuationForm.reference"
                maxlength="100"
                required
                placeholder="发票或内部核价单编号" /></label
            ><label
              >说明（可选）<input
                v-model.trim="materialValuationForm.note"
                maxlength="200"
            /></label>
          </div>
          <button
            class="primary"
            type="submit"
            :disabled="busy || !materialValuationForm.material_issue_line_id"
          >
            保存核价
          </button>
        </form>
      </div>
      <div class="card">
        <div class="section-heading"><h2>登记人工或制造费用</h2></div>
        <form @submit.prevent="recordProductionCharge">
          <div class="form-grid">
            <label
              >生产工单<select
                v-model.number="productionChargeForm.work_order_id"
                required
              >
                <option :value="0" disabled>选择已下达工单</option>
                <option
                  v-for="item in (productionCostReport?.orders ?? []).filter(
                    (entry) =>
                      entry.work_order_status !== 'draft' &&
                      entry.work_order_status !== 'cancelled'
                  )"
                  :key="item.work_order_id"
                  :value="item.work_order_id"
                >
                  #{{ item.work_order_id }} · {{ item.product_name }}
                </option>
              </select></label
            ><label
              >费用类别<select v-model="productionChargeForm.kind">
                <option value="labor">人工</option>
                <option value="overhead">制造费用</option>
              </select></label
            ><label
              >金额（元）<input
                v-model.trim="productionChargeForm.amount"
                type="number"
                min="0.01"
                max="1000000000000"
                step="0.01"
                required /></label
            ><label
              >依据编号<input
                v-model.trim="productionChargeForm.reference"
                maxlength="100"
                required /></label
            ><label
              >说明（可选）<input
                v-model.trim="productionChargeForm.note"
                maxlength="200"
            /></label>
          </div>
          <button
            class="primary"
            type="submit"
            :disabled="busy || !productionChargeForm.work_order_id"
          >
            登记费用
          </button>
        </form>
      </div>
    </div>
    <div class="card">
      <div class="section-heading"><h2>成本记录与冲销</h2></div>
      <div v-if="!productionCostReport?.entries.length" class="muted">
        暂无成本记录。
      </div>
      <article
        v-for="item in productionCostReport?.entries ?? []"
        :key="item.id"
        class="receipt"
      >
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · 工单 #{{ item.work_order_id }} ·
              {{
                { material: '材料核价', labor: '人工', overhead: '制造费用' }[
                  item.kind
                ]
              }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · {{ item.created_by_name }} ·
              依据 {{ item.reference }}
            </p>
          </div>
          <span class="pill">{{
            item.status === 'active' ? '有效' : '已冲销'
          }}</span>
        </div>
        <div class="receipt-lines">
          <span v-if="item.kind === 'material'"
            >{{ item.material_name }}（{{ item.material_sku }}）· 净领
            {{ item.net_quantity }} · 单价 ¥{{ item.unit_cost }}</span
          ><span
            >当前计入
            {{
              item.current_amount === null
                ? '已冲销'
                : `¥${item.current_amount}`
            }}</span
          ><span v-if="item.note">{{ item.note }}</span
          ><span v-if="item.reversal_id"
            >冲销原因：{{ item.reversal_reason }} ·
            {{ item.reversed_by_name }} ·
            {{ localTime(item.reversed_at!) }}</span
          >
        </div>
        <form
          v-if="item.status === 'active' && can('production_cost.reverse')"
          class="inline-form"
          @submit.prevent="reverseProductionCost(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="costReversalReasons[item.id]"
              required
              maxlength="200" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销记录
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
