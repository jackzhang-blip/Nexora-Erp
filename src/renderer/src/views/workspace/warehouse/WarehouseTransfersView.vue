<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  warehouses,
  transfers,
  transferForm,
  transferReversalReasons,
  can,
  localTime,
  createTransfer,
  postTransfer,
  reverseTransfer
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div v-if="can('transfer.create')" class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">WAREHOUSE TRANSFER</p>
          <h2>新建调拨单</h2>
        </div>
        <span class="pill">草稿</span>
      </div>
      <form @submit.prevent="createTransfer">
        <div class="form-grid">
          <label
            >来源仓库<select
              v-model.number="transferForm.from_warehouse_id"
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
            >目标仓库<select
              v-model.number="transferForm.to_warehouse_id"
              required
            >
              <option :value="0" disabled>选择目标仓库</option>
              <option
                v-for="item in warehouses.filter(
                  (entry) => entry.id !== transferForm.from_warehouse_id
                )"
                :key="item.id"
                :value="item.id"
              >
                {{ item.name }}
              </option>
            </select></label
          ><label
            >参考单号（可选）<input
              v-model.trim="transferForm.reference"
              maxlength="100"
          /></label>
        </div>
        <h3>调拨明细</h3>
        <div
          v-for="(line, index) in transferForm.lines"
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
            >数量<input
              v-model.trim="line.quantity"
              type="number"
              min="0.001"
              max="1000000"
              step="0.001"
              required /></label
          ><button
            class="text-button"
            type="button"
            :disabled="transferForm.lines.length === 1"
            @click="transferForm.lines.splice(index, 1)"
          >
            移除
          </button>
        </div>
        <div class="form-actions">
          <button
            class="secondary"
            type="button"
            @click="transferForm.lines.push({ material_id: 0, quantity: '1' })"
          >
            添加明细</button
          ><button
            class="primary"
            type="submit"
            :disabled="busy || warehouses.length < 2 || !materials.length"
          >
            保存草稿
          </button>
        </div>
      </form>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">TRANSFER LOG</p>
          <h2>调拨单</h2>
        </div>
      </div>
      <div v-if="!transfers.length" class="muted">暂无调拨单。</div>
      <article v-for="item in transfers" :key="item.id" class="receipt">
        <div class="receipt-head">
          <div>
            <strong
              >#{{ item.id }} · {{ item.from_warehouse_name }} →
              {{ item.to_warehouse_name }}</strong
            >
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
                  ? '已调拨'
                  : '待确认'
            }}</span
            ><button
              v-if="item.status === 'draft' && can('transfer.post')"
              class="primary small"
              type="button"
              :disabled="busy"
              @click="postTransfer(item.id)"
            >
              确认调拨
            </button>
          </div>
        </div>
        <div class="receipt-lines">
          <span v-for="line in item.lines" :key="line.id"
            >{{ line.material_name }} × {{ line.quantity }}
            {{ line.unit }}</span
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
            can('transfer.reverse')
          "
          class="inline-form"
          @submit.prevent="reverseTransfer(item.id)"
        >
          <label
            >冲销原因<input
              v-model.trim="transferReversalReasons[item.id]"
              required
              maxlength="200"
              placeholder="说明原调拨为何需要冲销" /></label
          ><button class="secondary small" type="submit" :disabled="busy">
            冲销已确认调拨
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
