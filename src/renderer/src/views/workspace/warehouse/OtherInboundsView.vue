<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NModal } from 'naive-ui'
import WorkspaceTable from '../../../components/workspace/WorkspaceTable.vue'
import { usePiniaAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

const store = usePiniaAppStore()
const { error, notice, busy, connectionLost, materials, warehouses, otherInbounds, otherInboundForm,
  otherInboundReversalReasons } = storeToRefs(store)
const { can, localTime, createOtherInbound, postOtherInbound, cancelOtherInbound,
  reverseOtherInbound } = store
const showForm = ref(false)
const query = ref('')
const filtered = computed(() => otherInbounds.value.filter((item) =>
  [item.id, item.reference, item.warehouse_name, item.note, ...item.lines.map((line) => line.material_name)]
    .join(' ').toLowerCase().includes(query.value.trim().toLowerCase())))
const reasonName = { opening: '期初补录', gift: '赠品', other: '其他' }
const columns = [
  { key: 'document', title: '单据' }, { key: 'source', title: '仓库与来源' },
  { key: 'lines', title: '物料明细' }, { key: 'actions', title: '操作' }
]
// 写入失败时保留表单，成功后才关闭弹窗。
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createOtherInbound, { busy, error, notice }, showForm)
}
</script>

<template>
  <section class="stack">
    <WorkspaceTable :data="filtered" title="其他入库" :columns="columns" :min-table-width="900">
      <template #actions>
        <button v-if="can('other_inbound.create')" class="primary" :disabled="busy || connectionLost" @click="showForm = true">新建其他入库</button>
      </template>
      <template #filters>
        <label>搜索入库单<input v-model="query" placeholder="单号、仓库或物料" /></label>
      </template>
      <template #beforeTable>
        <NModal v-model:show="showForm" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
        <form v-if="showForm && can('other_inbound.create')" class="stack" @submit.prevent="submitCreate">
          <h3>非采购来源入库</h3>
          <div class="form-grid">
            <label>仓库<select v-model.number="otherInboundForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
            <label>用途<select v-model="otherInboundForm.reason" required><option value="opening">期初补录</option><option value="gift">赠品</option><option value="other">其他</option></select></label>
            <label>参考号<input v-model.trim="otherInboundForm.reference" maxlength="100" /></label>
            <label>入库说明<input v-model.trim="otherInboundForm.note" required maxlength="200" /></label>
          </div>
          <div v-for="(line, index) in otherInboundForm.lines" :key="index" class="line-row">
            <label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label>
            <label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label>
            <button class="text-button" type="button" :disabled="otherInboundForm.lines.length === 1" @click="otherInboundForm.lines.splice(index, 1)">移除</button>
          </div>
          <div class="form-actions">
            <button class="secondary" type="button" @click="otherInboundForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button>
            <button class="primary" :disabled="busy || connectionLost">保存草稿</button>
            <button class="secondary" type="button" @click="showForm = false">收起</button>
          </div>
          <p class="muted">确认后才增加库存；这类入库不产生采购应付。</p>
        </form>
        </NModal>
      </template>
      <template #cell-document="{ row: item }"><strong>#{{ item.id }}</strong><small>{{ localTime(item.created_at) }} · {{ item.created_by_name }}</small><small>{{ item.status === 'draft' ? '待确认' : item.status === 'cancelled' ? '已取消' : item.reversal_id ? '已冲销' : '已入库' }}</small></template>
      <template #cell-source="{ row: item }">{{ item.warehouse_name }} · {{ reasonName[item.reason] }}<small>{{ item.note }}</small><small v-if="item.reference">{{ item.reference }}</small></template>
      <template #cell-lines="{ row: item }"><div v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }}</div></template>
      <template #cell-actions="{ row: item }"><div class="form-actions">
            <button v-if="item.status === 'draft' && can('other_inbound.post')" class="primary small" :disabled="busy || connectionLost" @click="postOtherInbound(item.id)">确认入库</button>
            <button v-if="item.status === 'draft' && can('other_inbound.cancel')" class="secondary small" :disabled="busy || connectionLost" @click="cancelOtherInbound(item.id)">取消</button>
          </div>
          <form v-if="item.status === 'posted' && !item.reversal_id && can('other_inbound.reverse')" class="inline-form" @submit.prevent="reverseOtherInbound(item.id)">
            <label>冲销原因<input v-model.trim="otherInboundReversalReasons[item.id]" required maxlength="200" /></label>
            <button class="secondary small" :disabled="busy || connectionLost">冲销</button>
          </form><small v-if="item.reversal_reason">冲销：{{ item.reversal_reason }}</small></template>
      <template #empty>{{ query ? '没有匹配的入库单。' : '暂无其他入库单。' }}</template>
    </WorkspaceTable>
  </section>
</template>
