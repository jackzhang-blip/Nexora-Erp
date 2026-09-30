<script setup lang="ts">
import { ref } from 'vue'
import { NModal } from 'naive-ui'
import { useAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  error,
  notice,
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
// 财务两张核对表沿用同一表格实现，来源与金额仍按现有快照展示。
const accountColumns = [
  { key: 'kind', title: '类别' }, { key: 'party', title: '往来单位' },
  { key: 'order', title: '订单' }, { key: 'business', title: '业务净额' },
  { key: 'settled', title: '收付款净额' }, { key: 'outstanding', title: '未结金额' },
  { key: 'sources', title: '来源明细' }
]
const sourceColumns = [
  { key: 'time', title: '确认时间' }, { key: 'kind', title: '类别' },
  { key: 'party', title: '往来单位' }, { key: 'source', title: '来源单据' },
  { key: 'material', title: '物料' }, { key: 'amount', title: '金额变动' },
  { key: 'actor', title: '操作人' }
]

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createPaymentRecord, { busy, error, notice }, createOpen)
}
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
    <div class="form-actions"><button v-if="can('finance.record')" class="primary" type="button" :disabled="busy" @click="createOpen = true">登记收付款</button></div>
    <NModal v-if="can('finance.record')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">PAYMENT RECORD</p>
          <h2>登记收付款</h2>
        </div>
      </div>
      <p class="muted">
        选择订单后登记真实发生的收付款。退款只在退货产生贷方余额时允许；录错请在下方冲销并重新登记。
      </p>
      <form @submit.prevent="submitCreate">
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
    </NModal>
    <WorkspaceTable title="订单核对" :columns="accountColumns" :data="financeAccounts" :min-table-width="980">
      <template #heading><p class="eyebrow">OPEN BALANCES</p><h2>订单核对</h2></template>
      <template #beforeTable><p class="muted">
        未结金额 = 已确认业务净额 −
        收付款净额。负数表示应退客户或应收供应商退款。
      </p></template>
      <template #cell-kind="{ row: item }">{{ item.kind === 'receivable' ? '应收' : '应付' }}</template>
      <template #cell-party="{ row: item }">{{ item.party_name }}</template>
      <template #cell-order="{ row: item }">#{{ item.order_id }}</template>
      <template #cell-business="{ row: item }">¥{{ item.business_amount }}</template>
      <template #cell-settled="{ row: item }">¥{{ item.settled_amount }}</template>
      <template #cell-outstanding="{ row: item }"><strong>¥{{ item.outstanding_amount }}</strong></template>
      <template #cell-sources="{ row: item }">{{ item.source_keys.length }} 笔</template>
      <template #empty>暂无可核对的订单金额。</template>
    </WorkspaceTable>
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
    <WorkspaceTable title="应收应付来源" :columns="sourceColumns" :data="receivablesPayables.entries" :min-table-width="980">
      <template #heading><p class="eyebrow">DOCUMENT RECONCILIATION</p><h2>应收应付来源</h2></template>
      <template #beforeTable><p class="muted">
        金额按已确认的出库、入库与退货明细计算，单位为人民币；无采购单价的历史入库显示“待核价”。
      </p></template>
      <template #cell-time="{ row: item }">{{ localTime(item.posted_at) }}</template>
      <template #cell-kind="{ row: item }">{{ item.kind === 'receivable' ? '应收' : '应付' }}</template>
      <template #cell-party="{ row: item }">{{ item.party_name }}</template>
      <template #cell-source="{ row: item }">{{ financialSource(item)
                }}<small v-if="item.order_id">
                  · 订单 #{{ item.order_id }}</small
                ></template>
      <template #cell-material="{ row: item }">{{ item.sku }} × {{ item.quantity }}</template>
      <template #cell-amount="{ row: item }">{{ item.amount === null ? '待核价' : `¥${item.amount}` }}</template>
      <template #cell-actor="{ row: item }">{{
                  item.posted_by_name ??
                  (item.posted_by === null ? '未知' : `#${item.posted_by}`)
                }}</template>
      <template #empty>暂无已确认的金额来源单据。</template>
    </WorkspaceTable>
  </section>
</template>
