<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  activeTab,
  busy,
  receivablesPayables,
  financeAccounts,
  paymentRecords,
  paymentForm,
  reversalReasons,
  can,
  localTime,
  financialSource,
  createPaymentRecord,
  reversePaymentRecord,
  paymentActionLabel
} = useAppStore()
</script>

<template>
  <section v-if="activeTab === 'finance' && receivablesPayables" class="stack">
    <div class="summary-grid">
      <div class="metric">
        <span>业务应收净额</span
        ><strong>¥{{ receivablesPayables.receivable_amount }}</strong>
      </div>
      <div class="metric">
        <span>业务应付净额</span
        ><strong>¥{{ receivablesPayables.payable_amount }}</strong>
      </div>
      <div class="metric">
        <span>待定价明细</span
        ><strong>{{ receivablesPayables.unpriced_count }}</strong>
      </div>
    </div>
    <div v-if="can('finance.record')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PAYMENT RECORD</p>
          <h2>登记收付款</h2>
        </div>
      </div>
      <p class="muted">
        选择订单后登记真实发生的收付款。退款只在退货产生贷方余额时允许；录错请在下方冲销并重新登记。
      </p>
      <form @submit.prevent="createPaymentRecord">
        <div class="form-grid">
          <label
            >往来类别<select
              v-model="paymentForm.kind"
              @change="paymentForm.order_id = 0"
            >
              <option value="receivable">客户应收</option>
              <option value="payable">供应商应付</option>
            </select></label
          >
          <label
            >关联订单<select v-model.number="paymentForm.order_id" required>
              <option :value="0" disabled>选择已发生业务的订单</option>
              <option
                v-for="item in financeAccounts.filter(
                  (entry) => entry.kind === paymentForm.kind
                )"
                :key="`${item.kind}-${item.order_id}`"
                :value="item.order_id"
              >
                #{{ item.order_id }} · {{ item.party_name }} · 未结 ¥{{
                  item.outstanding_amount
                }}
              </option>
            </select></label
          >
          <label
            >业务动作<select v-model="paymentForm.action">
              <option value="settlement">
                {{
                  paymentForm.kind === 'receivable'
                    ? '收到客户款'
                    : '支付供应商'
                }}
              </option>
              <option value="refund">
                {{
                  paymentForm.kind === 'receivable'
                    ? '退还客户'
                    : '收到供应商退款'
                }}
              </option>
            </select></label
          >
          <label
            >金额（元）<input
              v-model.trim="paymentForm.amount"
              type="number"
              min="0.01"
              max="1000000000000"
              step="0.01"
              required
          /></label>
          <label
            >银行或收据参考号<input
              v-model.trim="paymentForm.reference"
              required
              maxlength="100"
          /></label>
          <label
            >备注（可选）<input v-model.trim="paymentForm.note" maxlength="200"
          /></label>
        </div>
        <button
          class="primary"
          type="submit"
          :disabled="busy || !financeAccounts.length"
        >
          登记收付款
        </button>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">OPEN BALANCES</p>
          <h2>订单核对</h2>
        </div>
      </div>
      <p class="muted">
        未结金额 = 已确认业务净额 −
        收付款净额。负数表示应退客户或应收供应商退款。
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>类别</th>
              <th>往来单位</th>
              <th>订单</th>
              <th>业务净额</th>
              <th>收付款净额</th>
              <th>未结金额</th>
              <th>来源明细</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in financeAccounts"
              :key="`${item.kind}-${item.order_id}`"
            >
              <td>{{ item.kind === 'receivable' ? '应收' : '应付' }}</td>
              <td>{{ item.party_name }}</td>
              <td>#{{ item.order_id }}</td>
              <td>¥{{ item.business_amount }}</td>
              <td>¥{{ item.settled_amount }}</td>
              <td>
                <strong>¥{{ item.outstanding_amount }}</strong>
              </td>
              <td>{{ item.source_keys.length }} 笔</td>
            </tr>
            <tr v-if="!financeAccounts.length">
              <td colspan="7" class="muted">暂无可核对的订单金额。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PAYMENT AUDIT</p>
          <h2>收付款与冲销记录</h2>
        </div>
      </div>
      <div v-if="!paymentRecords.length" class="muted">暂无收付款记录。</div>
      <article v-for="item in paymentRecords" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ paymentActionLabel(item) }} ·
              {{ item.party_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} ·
              {{ item.kind === 'receivable' ? '销售订单' : '采购订单' }} #{{
                item.order_id
              }}
              · ¥{{ item.amount }} · 参考号 {{ item.reference }} · 操作人
              {{ item.created_by_name }}
              <span v-if="item.reverses_id"
                >· 冲销记录 #{{ item.reverses_id }}</span
              >
              <span v-if="item.note">· {{ item.note }}</span>
            </p>
          </div>
        </div>
        <form
          v-if="
            item.action !== 'reversal' &&
            !paymentRecords.some((entry) => entry.reverses_id === item.id) &&
            can('finance.reverse')
          "
          class="inline-form"
          @submit.prevent="reversePaymentRecord(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="reversalReasons[item.id]"
              required
              maxlength="200" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销此记录
          </button>
        </form>
      </article>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">DOCUMENT RECONCILIATION</p>
          <h2>应收应付来源</h2>
        </div>
      </div>
      <p class="muted">
        金额按已确认的出库、入库与退货明细计算，单位为人民币；无采购单价的历史入库显示“待核价”。
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>确认时间</th>
              <th>类别</th>
              <th>往来单位</th>
              <th>来源单据</th>
              <th>物料</th>
              <th>金额变动</th>
              <th>操作人</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in receivablesPayables.entries" :key="item.key">
              <td>{{ localTime(item.posted_at) }}</td>
              <td>{{ item.kind === 'receivable' ? '应收' : '应付' }}</td>
              <td>{{ item.party_name }}</td>
              <td>
                {{ financialSource(item)
                }}<small v-if="item.order_id">
                  · 订单 #{{ item.order_id }}</small
                >
              </td>
              <td>{{ item.sku }} × {{ item.quantity }}</td>
              <td>{{ item.amount === null ? '待核价' : `¥${item.amount}` }}</td>
              <td>
                {{
                  item.posted_by_name ??
                  (item.posted_by === null ? '未知' : `#${item.posted_by}`)
                }}
              </td>
            </tr>
            <tr v-if="!receivablesPayables.entries.length">
              <td colspan="7" class="muted">暂无已确认的金额来源单据。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
