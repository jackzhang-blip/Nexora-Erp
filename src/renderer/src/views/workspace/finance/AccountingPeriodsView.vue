<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NModal } from 'naive-ui'
import type { AccountingPeriod } from '../../../../../shared/erp-api'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import MetadataHistory from './MetadataHistory.vue'
import './ledger-metadata.css'

const store = usePiniaAppStore()
const { busy, connectionLost, accountingPeriods, accountingPeriodForm: form } = storeToRefs(store)
const { can, editAccountingPeriod, saveAccountingPeriod, loadAccountingPeriodChanges } = store
const query = ref('')
const showForm = ref(false)
const history = ref<AccountingPeriod | null>(null)
const filtered = computed(() => accountingPeriods.value.filter(item =>
  [item.code, item.name, item.start_date, item.end_date].join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const columns = [
  { key: 'code', title: '期间编码' }, { key: 'name', title: '名称' },
  { key: 'start_date', title: '开始日期' }, { key: 'end_date', title: '结束日期' },
  { key: 'status', title: '状态' }, { key: 'version', title: '版本' }, { key: 'actions', title: '操作' }
]
function edit(item?: AccountingPeriod): void { editAccountingPeriod(item); showForm.value = true }
async function save(): Promise<void> {
  if (busy.value || connectionLost.value || !can('accounting_period.manage')) return
  if (await saveAccountingPeriod()) showForm.value = false
}
</script>

<template>
  <section class="stack ledger-metadata-page">
    <WorkspaceTable title="会计期间" :show-title="false" :columns="columns" :data="filtered" :min-table-width="900">
      <template #actions><button v-if="can('accounting_period.manage')" class="primary" :disabled="busy || connectionLost" @click="edit()">新增期间</button></template>
      <template #filters>
        <label class="ledger-search">搜索期间<input v-model="query" placeholder="输入编码、名称或日期" /></label>
        <span class="muted">共 {{ accountingPeriods.length }} 个期间</span>
      </template>
      <template #cell-status="{ row }">{{ row.status === 'open' ? '开放' : '已关闭' }}</template>
      <template #cell-actions="{ row }">
        <div class="ledger-actions">
          <button v-if="can('accounting_period.manage') && row.status === 'open'" class="text-button" :disabled="busy || connectionLost" @click="edit(row)">编辑名称</button>
          <button class="text-button" :disabled="connectionLost" @click="history = row">变更记录</button>
        </div>
      </template>
      <template #empty>{{ query ? '没有匹配的期间。' : '暂无会计期间。请先确定公司使用的日期范围。' }}</template>
    </WorkspaceTable>
    <NModal v-model:show="showForm" preset="card" :title="form.id === null ? '新增会计期间' : '编辑期间名称'" :mask-closable="!busy" :style="{ width: 'min(760px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <form v-if="showForm && can('accounting_period.manage')" class="ledger-editor" @submit.prevent="save">
        <p class="muted">范围包含开始和结束日期，不可与其他期间重叠。编码及日期保存后固定。</p>
        <div class="form-grid">
          <label>期间编码<input v-model.trim="form.code" required maxlength="32" :disabled="form.id !== null" placeholder="例如 2026-01" /></label>
          <label>期间名称<input v-model.trim="form.name" required maxlength="100" /></label>
          <label>开始日期<input v-model="form.start_date" type="date" required :disabled="form.id !== null" /></label>
          <label>结束日期<input v-model="form.end_date" type="date" required :min="form.start_date" :disabled="form.id !== null" /></label>
          <label>建立依据 / 修改原因<input v-model.trim="form.reason" required maxlength="200" placeholder="填写期间方案依据或修改原因" /></label>
        </div>
        <div class="form-actions"><button class="primary" :disabled="busy || connectionLost">{{ busy ? '正在保存…' : '保存期间' }}</button><button class="secondary" type="button" :disabled="busy" @click="showForm = false">取消</button></div>
      </form>
    </NModal>
    <NModal :show="history !== null" preset="card" :title="history ? `${history.code} · 变更记录` : '变更记录'" :style="{ width: 'min(1000px, calc(100vw - 32px))' }" @update:show="value => { if (!value) history = null }">
      <MetadataHistory v-if="history" :key="history.id" :load="() => loadAccountingPeriodChanges(history!.id)" />
    </NModal>
  </section>
</template>
