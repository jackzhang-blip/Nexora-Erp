<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  workOrders,
  materialIssues,
  materialReturns,
  materialReturnForm,
  can,
  selectedReturnIssue,
  localTime,
  selectReturnIssue,
  createMaterialReturn,
  postMaterialReturn,
  cancelMaterialReturn
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('material_return.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">MATERIAL RETURN</p>
          <h2>新建生产退料单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <p class="muted">
        只退回已确认领料的组件，确认后入原领料仓库，并恢复工单可领数量。请按实际退回数量填写。
      </p>
      <form @submit.prevent="createMaterialReturn">
        <div class="form-grid">
          <label
            >原领料单<select
              v-model.number="materialReturnForm.material_issue_id"
              required
              @change="selectReturnIssue(materialReturnForm.material_issue_id)"
            >
              <option :value="0" disabled>选择可退领料单</option>
              <option
                v-for="item in materialIssues.filter(
                  (entry) =>
                    entry.status === 'posted' &&
                    workOrders.some(
                      (order) =>
                        order.id === entry.work_order_id &&
                        order.status === 'in_progress'
                    ) &&
                    entry.lines.some(
                      (line) => Number(line.returnable_quantity) > 0
                    )
                )"
                :key="item.id"
                :value="item.id"
              >
                #{{ item.id }} · 工单 #{{ item.work_order_id }} ·
                {{ item.warehouse_name }}
              </option>
            </select></label
          ><label
            >退料原因<input
              v-model.trim="materialReturnForm.reason"
              required
              maxlength="200"
          /></label>
        </div>
        <h3>本次退料数量</h3>
        <div
          v-for="line in materialReturnForm.lines"
          :key="line.material_issue_line_id"
          class="line-row"
        >
          <label
            >{{
              selectedReturnIssue?.lines.find(
                (item) => item.id === line.material_issue_line_id
              )?.material_name
            }}
            · 可退
            {{
              selectedReturnIssue?.lines.find(
                (item) => item.id === line.material_issue_line_id
              )?.returnable_quantity
            }}<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              :max="
                selectedReturnIssue?.lines.find(
                  (item) => item.id === line.material_issue_line_id
                )?.returnable_quantity
              "
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="busy"
            @click="
              materialReturnForm.lines = materialReturnForm.lines.filter(
                (item) =>
                  item.material_issue_line_id !== line.material_issue_line_id
              )
            "
          >
            本次不退
          </button>
        </div>
        <button
          class="primary"
          type="submit"
          :disabled="busy || !materialReturnForm.lines.length"
        >
          保存退料草稿
        </button>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">RETURN HISTORY</p>
          <h2>生产退料记录</h2>
        </div>
      </div>
      <div v-if="!materialReturns.length" class="muted">暂无退料单。</div>
      <article v-for="item in materialReturns" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · 原领料 #{{ item.material_issue_id }} · 工单 #{{
                item.work_order_id
              }}
              · {{ item.warehouse_name }}</strong
            >
            <p class="muted">
              {{ localTime(item.created_at) }} · 创建人
              {{ item.created_by_name }} · {{ item.reason }}
            </p>
          </div>
          <div class="receipt-actions">
            <span class="pill" :class="item.status">{{
              { draft: '草稿', posted: '已确认', cancelled: '已取消' }[
                item.status
              ]
            }}</span
            ><button
              v-if="item.status === 'draft' && can('material_return.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postMaterialReturn(item.id)"
            >
              确认退料</button
            ><button
              v-if="item.status === 'draft' && can('material_return.cancel')"
              class="secondary small"
              type="button"
              :disabled="busy"
              @click="cancelMaterialReturn(item.id)"
            >
              取消
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }}
            {{ line.unit }}</span
          >
        </div>
      </article>
    </div>
  </section>
</template>
