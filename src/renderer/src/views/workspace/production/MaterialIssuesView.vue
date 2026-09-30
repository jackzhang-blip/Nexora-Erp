<script setup lang="ts">
import { ref } from 'vue'
import { NModal } from 'naive-ui'
import { useAppStore } from '../../../store/app-store'
import { submitCreateDialog } from '../../../utils/create-dialog'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  error,
  notice,
  busy,
  workOrders,
  materialIssues,
  warehouses,
  materialIssueForm,
  can,
  selectedIssueOrder,
  localTime,
  selectIssueOrder,
  createMaterialIssue,
  postMaterialIssue,
  cancelMaterialIssue,
  selectReturnIssue
} = useAppStore()

// 保存失败时保留弹窗和草稿，方便直接修正后重试。
const createOpen = ref(false)
async function submitCreate(): Promise<void> {
  await submitCreateDialog(createMaterialIssue, { busy, error, notice }, createOpen)
}
</script>

<template>
  <section class="stack">
    <div class="form-actions"><button v-if="can('material_issue.create')" class="primary" type="button" :disabled="busy" @click="createOpen = true">新建领料单</button></div>
    <NModal v-if="can('material_issue.create')" v-model:show="createOpen" preset="card" :mask-closable="!busy" :style="{ width: 'min(900px, calc(100vw - 32px))', maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }">
      <div class="section-heading">
        <div>
          <p class="eyebrow">MATERIAL ISSUE</p>
          <h2>新建领料单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <p class="muted">
        按工单剩余需料分批建单。草稿不预留库存；确认时服务端再次检查源仓库存与剩余需料。
      </p>
      <form @submit.prevent="submitCreate">
        <div class="form-grid">
          <label
            >生产工单<select
              v-model.number="materialIssueForm.work_order_id"
              required
              @change="selectIssueOrder(materialIssueForm.work_order_id)"
            >
              <option :value="0" disabled>选择已下达工单</option>
              <option
                v-for="item in workOrders.filter(
                  (entry) =>
                    (entry.status === 'released' ||
                      entry.status === 'in_progress') &&
                    entry.lines.some(
                      (line) => Number(line.remaining_quantity) > 0
                    )
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · {{ item.product_name }} ·
                {{ item.target_quantity }} {{ item.product_unit }}
              </option>
            </select></label
          ><label
            >领料源仓库<select
              v-model.number="materialIssueForm.warehouse_id"
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
            >参考号（可选）<input
              v-model.trim="materialIssueForm.reference"
              maxlength="100"
          /></label>
        </div>
        <h3>本次领料数量</h3>
        <div
          v-for="line in materialIssueForm.lines"
          :key="line.work_order_line_id"
          class="line-row"
        >
          <label
            >{{
              selectedIssueOrder?.lines.find(
                (item) => item.id === line.work_order_line_id
              )?.material_name
            }}
            · 剩余
            {{
              selectedIssueOrder?.lines.find(
                (item) => item.id === line.work_order_line_id
              )?.remaining_quantity
            }}<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              :max="
                selectedIssueOrder?.lines.find(
                  (item) => item.id === line.work_order_line_id
                )?.remaining_quantity
              "
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="busy"
            @click="
              materialIssueForm.lines = materialIssueForm.lines.filter(
                (item) => item.work_order_line_id !== line.work_order_line_id
              )
            "
          >
            本次不领
          </button>
        </div>
        <button
          class="primary"
          type="submit"
          :disabled="
            busy || !materialIssueForm.lines.length || !warehouses.length
          "
        >
          保存领料草稿
        </button>
      </form>
    </NModal>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">ISSUE HISTORY</p>
          <h2>领料记录</h2>
        </div>
      </div>
      <div v-if="!materialIssues.length" class="muted">暂无领料单。</div>
      <article v-for="item in materialIssues" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · 工单 #{{ item.work_order_id }} ·
              {{ item.warehouse_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }}
              <span v-if="item.reference">· {{ item.reference }}</span>
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              { draft: '草稿', posted: '已确认', cancelled: '已取消' }[
                item.status
              ]
            }}</span
            ><button
              v-if="item.status === 'draft' && can('material_issue.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postMaterialIssue(item.id)"
            >
              确认领料</button
            ><button
              v-if="item.status === 'draft' && can('material_issue.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelMaterialIssue(item.id)"
            >
              取消</button
            ><button
              v-if="
                item.status === 'posted' &&
                item.lines.some(
                  (line) => Number(line.returnable_quantity) > 0
                ) &&
                can('material_return.create')
              "
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="selectReturnIssue(item.id)"
            >
              创建退料单
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} · 已领 {{ line.quantity }} · 已退
            {{ line.returned_quantity }} · 可退 {{ line.returnable_quantity }}
            {{ line.unit }}</span
          >
        </div>
      </article>
    </div>
  </section>
</template>
