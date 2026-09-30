<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { NModal } from 'naive-ui'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import JournalHistory from './JournalHistory.vue'
import { journalStatusLabels } from './journal-display'
import './ledger-reports.css'
import './journals.css'

const store = usePiniaAppStore()
const { ledgerReportQuery: query, ledgerReportResult: result, ledgerReportAccounts: accounts,
  ledgerReportLoading: loading, ledgerReportError: error, connectionLost,
  ledgerReportJournal: journal, ledgerReportJournalLoading: journalLoading,
  ledgerReportJournalError: journalError } = storeToRefs(store)
const { can, loadLedgerReportOptions, queryLedgerReport, exportLedgerReport,
  openLedgerReportJournal, closeLedgerReportJournal, loadJournalChanges } = store
const moneyKeys = ['opening_debit', 'opening_credit', 'debit', 'credit', 'closing_debit', 'closing_credit', 'balance']
const columns = computed(() => (result.value?.columns ?? []).map(column => ({ ...column,
  width: moneyKeys.includes(column.key) ? '170' : ['summary', 'account', 'reference', 'name'].includes(column.key) ? '220' : '130' })))
const balanceRows = computed(() => result.value ? [
  { phase: '期初余额', debit: result.value.totals.opening_debit, credit: result.value.totals.opening_credit },
  { phase: '本期发生额', debit: result.value.totals.debit, credit: result.value.totals.credit },
  { phase: '期末余额', debit: result.value.totals.closing_debit, credit: result.value.totals.closing_credit }
] : [])
const balanceColumns = [{ key: 'phase', title: '核对项目' }, { key: 'debit', title: '借方合计（元）' }, { key: 'credit', title: '贷方合计（元）' }]
const journalColumns = [{ key: 'position', title: '序号' }, { key: 'account_name', title: '科目快照' },
  { key: 'summary', title: '摘要' }, { key: 'debit', title: '借方（元）' }, { key: 'credit', title: '贷方（元）' }]
const mayQuery = computed(() => can('journal.view') && !connectionLost.value && !loading.value &&
  !!query.value.from_date && !!query.value.to_date && (query.value.kind === 'trial_balance' || !!query.value.account_id))
function changeKind(): void { query.value.account_id = null }
async function drillAccount(id: string): Promise<void> {
  query.value = { ...query.value, kind: 'account_ledger', account_id: Number(id) }
  await queryLedgerReport()
}
async function trialBalance(): Promise<void> {
  query.value = { ...query.value, kind: 'trial_balance', account_id: null }
  await queryLedgerReport()
}
onMounted(() => { void loadLedgerReportOptions() })
</script>

<template>
  <section class="stack ledger-reports-page">
    <form @submit.prevent="queryLedgerReport">
      <WorkspaceTable class="ledger-report-table" title="总账报表" :show-title="false" :columns="columns"
        :data="result?.rows ?? []" :loading="loading" :error="error" :min-table-width="query.kind === 'trial_balance' ? 1370 : 1910">
        <template #filters>
          <label>报表<select v-model="query.kind" @change="changeKind"><option value="trial_balance">试算平衡</option><option value="account_ledger">科目明细</option></select></label>
          <label v-if="query.kind === 'account_ledger'">科目<select v-model.number="query.account_id" required><option :value="null" disabled>选择科目</option><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.code }} · {{ account.name }}{{ account.is_active ? '' : '（停用）' }}</option></select></label>
          <label>开始日期<input v-model="query.from_date" type="date" required /></label>
          <label>结束日期<input v-model="query.to_date" type="date" required :min="query.from_date || undefined" /></label>
        </template>
        <template #filterActions><button class="primary" :disabled="!mayQuery">{{ loading ? '正在查询…' : '查询' }}</button></template>
        <template #actions><button type="button" class="secondary" :disabled="connectionLost || loading || !result" @click="exportLedgerReport">导出 CSV</button><button v-if="query.kind === 'account_ledger'" type="button" class="secondary" :disabled="connectionLost || loading" @click="loadLedgerReportOptions">重新读取科目</button></template>
        <template #beforeTable>
          <p class="muted ledger-report-note">仅计入已过账凭证；草稿、待审核及已批准凭证不计入。期初从开始日前的已过账分录累计，未结账数据可随后续过账变化。</p>
          <p v-if="result" class="ledger-report-caption">{{ result.filters.from_date }} 至 {{ result.filters.to_date }} · {{ result.kind === 'trial_balance' ? '全科目 · 人民币' : `${result.totals.code} · ${result.totals.name} · 人民币` }} · {{ result.rows.length }} 行 · 生成于 {{ new Date(result.generated_at).toLocaleString() }}</p>
          <p v-if="result?.kind === 'trial_balance'" :role="result.totals.balanced ? undefined : 'alert'">{{ result.totals.balanced ? '期初、本期发生额与期末借贷合计均相等。' : '借贷合计不相等，请核对凭证和数据完整性。' }}</p>
          <button v-if="result?.kind === 'account_ledger'" type="button" class="text-button" :disabled="loading || connectionLost" @click="trialBalance">返回同日期试算平衡</button>
        </template>
        <template #cell-code="{ row }"><button type="button" class="text-button" :disabled="loading || connectionLost" @click="drillAccount(row.account_id!)">{{ row.code }}</button></template>
        <template #cell-journal_id="{ row }"><button type="button" class="text-button" :disabled="connectionLost" @click="openLedgerReportJournal(Number(row.journal_id))">记-{{ row.journal_id }}</button></template>
        <template #cell-source="{ row }"><button v-if="row.reversal_of_id" type="button" class="text-button" :disabled="connectionLost" @click="openLedgerReportJournal(Number(row.reversal_of_id))">{{ row.source }}</button><span v-else>{{ row.source }}</span></template>
        <template v-for="key in moneyKeys" :key="key" #[`cell-${key}`]="{ row }"><span class="ledger-report-money">{{ row[key] }}</span></template>
        <template #empty>{{ result ? '此范围内暂无记录；期初与期末余额见下方核对。' : '选择日期范围并查询。科目明细须先选择科目。' }}</template>
        <template #errorActions><button type="button" class="secondary" :disabled="connectionLost || loading" @click="queryLedgerReport">重试查询</button></template>
        <template #footer><p v-if="result" class="muted ledger-report-note">覆盖期间：{{ result.periods.map(period => `${period.code}（${period.status === 'open' ? '开放' : '已关闭'}）`).join('、') || '无对应期间' }}。当前尚无正式期初余额录入、期间结账或业务自动凭证。</p></template>
      </WorkspaceTable>
    </form>
    <WorkspaceTable v-if="result" class="ledger-report-table" title="余额核对" :columns="balanceColumns" :data="balanceRows" :min-table-width="600">
      <template #cell-debit="{ row }"><span class="ledger-report-money">{{ row.debit }}</span></template><template #cell-credit="{ row }"><span class="ledger-report-money">{{ row.credit }}</span></template>
    </WorkspaceTable>
    <NModal :show="!!journal || journalLoading || !!journalError" preset="card" :title="journal ? `记-${journal.id} · ${journalStatusLabels[journal.status]}` : '凭证详情'"
      :style="{ width: 'min(1100px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }" @update:show="value => { if (!value) closeLedgerReportJournal() }">
      <p v-if="journalLoading" role="status">正在读取凭证…</p><p v-if="journalError" role="alert">{{ journalError }}</p>
      <div v-if="journal" class="stack"><p>{{ journal.journal_date }} · 期间 {{ journal.period_code }} · 依据 {{ journal.reference }} · 建单人 {{ journal.created_by_name }} · 版本 {{ journal.version }}</p><p v-if="journal.note">备注：{{ journal.note }}</p>
        <p v-if="journal.reversal_of_id">冲销原凭证：<button type="button" class="text-button" :disabled="connectionLost" @click="openLedgerReportJournal(journal.reversal_of_id)">记-{{ journal.reversal_of_id }}</button></p>
        <p v-if="journal.reversal_journal_id">关联冲销：<button type="button" class="text-button" :disabled="connectionLost" @click="openLedgerReportJournal(journal.reversal_journal_id)">记-{{ journal.reversal_journal_id }}</button>（须过账后才抵销）。</p>
        <WorkspaceTable class="ledger-report-table" title="凭证分录" :columns="journalColumns" :data="journal.lines" :min-table-width="800"><template #cell-account_name="{ row }">{{ row.account_code }} · {{ row.account_name }}</template></WorkspaceTable>
        <JournalHistory :key="`${journal.id}:${journal.version}`" :load="() => loadJournalChanges(journal!.id)" />
      </div>
    </NModal>
  </section>
</template>
