<script setup lang="ts">
// 输入框统一外观，必填、长度与数字范围仍由真实输入元素校验。
import AppInput from '../../../components/app/AppInput.vue'
// 页面按钮统一复用 Naive UI 封装，显式区分表单提交与普通操作。
import AppButton from '../../../components/app/AppButton.vue'
// 日期直接使用 Naive UI，保持后端字符串格式以及原有必填和范围校验。
import { NDatePicker } from 'naive-ui'
import { datePickerString, vDateField, dateOutsideRange } from '../../../utils/date-field'
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
const filtered = computed(() =>
  accountingPeriods.value.filter((item) =>
    [item.code, item.name, item.start_date, item.end_date]
      .join(' ')
      .toLowerCase()
      .includes(query.value.trim().toLowerCase())
  )
)
const columns = [
  { key: 'code', title: '期间编码' },
  { key: 'name', title: '名称' },
  { key: 'start_date', title: '开始日期' },
  { key: 'end_date', title: '结束日期' },
  { key: 'status', title: '状态' },
  { key: 'version', title: '版本' },
  { key: 'actions', title: '操作' }
]
function edit(item?: AccountingPeriod): void {
  editAccountingPeriod(item)
  showForm.value = true
}
async function save(): Promise<void> {
  if (busy.value || connectionLost.value || !can('accounting_period.manage')) return
  if (await saveAccountingPeriod()) showForm.value = false
}
</script>

<template>
  <section class="stack ledger-metadata-page">
    <WorkspaceTable
      title="会计期间"
      :show-title="false"
      :columns="columns"
      :data="filtered"
      :min-table-width="900"
    >
      <template #actions
        ><AppButton
          v-if="can('accounting_period.manage')"
          :disabled="busy || connectionLost"
          @click="edit()"
          variant="primary"
          type="button"
          >新增期间</AppButton
        ></template
      >
      <template #filters>
        <label class="ledger-search"
          >搜索期间<AppInput v-model="query" placeholder="输入编码、名称或日期"
        /></label>
        <span class="muted">共 {{ accountingPeriods.length }} 个期间</span>
      </template>
      <template #cell-status="{ row }">{{ row.status === 'open' ? '开放' : '已关闭' }}</template>
      <template #cell-actions="{ row }">
        <div class="ledger-actions">
          <AppButton
            v-if="can('accounting_period.manage') && row.status === 'open'"
            :disabled="busy || connectionLost"
            @click="edit(row)"
            variant="text"
            type="button"
            >编辑名称</AppButton
          >
          <AppButton :disabled="connectionLost" @click="history = row" variant="text" type="button"
            >变更记录</AppButton
          >
        </div>
      </template>
      <template #empty>{{
        query ? '没有匹配的期间。' : '暂无会计期间。请先确定公司使用的日期范围。'
      }}</template>
    </WorkspaceTable>
    <NModal
      v-model:show="showForm"
      preset="card"
      :title="form.id === null ? '新增会计期间' : '编辑期间名称'"
      :mask-closable="!busy"
      :style="{
        width: 'min(760px, calc(100vw - 32px))',
        maxHeight: 'calc(100vh - 48px)',
        overflowY: 'auto'
      }"
    >
      <form
        v-if="showForm && can('accounting_period.manage')"
        class="ledger-editor"
        @submit.prevent="save"
      >
        <p class="muted">范围包含开始和结束日期，不可与其他期间重叠。编码及日期保存后固定。</p>
        <div class="form-grid">
          <label
            >期间编码<AppInput
              v-model.trim="form.code"
              required
              maxlength="32"
              :disabled="form.id !== null"
              placeholder="例如 2026-01"
          /></label>
          <label>期间名称<AppInput v-model.trim="form.name" required maxlength="100" /></label>
          <label
            >开始日期<NDatePicker
              to="body"
              :formatted-value="form.start_date || null"
              type="date"
              format="yyyy-MM-dd"
              value-format="yyyy-MM-dd"
              v-date-field="{ required: true }"
              @update:formatted-value="
                (value) => {
                  form.start_date = datePickerString(value)
                }
              "
              :disabled="form.id !== null"
          /></label>
          <label
            >结束日期<NDatePicker
              to="body"
              :formatted-value="form.end_date || null"
              type="date"
              format="yyyy-MM-dd"
              value-format="yyyy-MM-dd"
              v-date-field="{ required: true, min: form.start_date }"
              @update:formatted-value="
                (value) => {
                  form.end_date = datePickerString(value)
                }
              "
              :disabled="form.id !== null"
              :is-date-disabled="
                (timestamp: number) => dateOutsideRange(timestamp, form.start_date, undefined)
              "
          /></label>
          <label
            >建立依据 / 修改原因<AppInput
              v-model.trim="form.reason"
              required
              maxlength="200"
              placeholder="填写期间方案依据或修改原因"
          /></label>
        </div>
        <div class="form-actions">
          <AppButton :disabled="busy || connectionLost" variant="primary" type="submit">{{
            busy ? '正在保存…' : '保存期间'
          }}</AppButton
          ><AppButton type="button" :disabled="busy" @click="showForm = false" variant="secondary"
            >取消</AppButton
          >
        </div>
      </form>
    </NModal>
    <NModal
      :show="history !== null"
      preset="card"
      :title="history ? `${history.code} · 变更记录` : '变更记录'"
      :style="{ width: 'min(1000px, calc(100vw - 32px))' }"
      @update:show="
        (value) => {
          if (!value) history = null
        }
      "
    >
      <MetadataHistory
        v-if="history"
        :key="history.id"
        :load="() => loadAccountingPeriodChanges(history!.id)"
      />
    </NModal>
  </section>
</template>
