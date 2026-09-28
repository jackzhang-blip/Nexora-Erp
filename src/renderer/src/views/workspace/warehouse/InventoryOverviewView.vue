<script setup lang="ts">
import { useAppStore } from '../../../store/app-store'
import { NButton } from 'naive-ui'
import IconRefreshLine from '~icons/ri/refresh-line'

// 页面直接使用共享状态与操作，切换标签时不会丢失正在填写的草稿。
const {
  busy,
  materials,
  stock,
  movements,
  receipts,
  warehouses,
  selectedWarehouseId,
  localTime,
  movementSource,
  refreshData,
  perform
} = useAppStore()
</script>

<template>
  <section class="stack">
    <div class="summary-grid">
      <div class="metric">
        <span>物料种类</span><strong>{{ materials.length }}</strong>
      </div>
      <div class="metric">
        <span>已确认入库单</span
        ><strong>{{
          receipts.filter((item) => item.status === 'posted').length
        }}</strong>
      </div>
      <div class="metric">
        <span>库存流水</span><strong>{{ movements.length }}</strong>
      </div>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">INVENTORY</p>
          <h2>当前库存</h2>
        </div>
        <label
          >仓库<select
            v-model.number="selectedWarehouseId"
            :disabled="busy"
            @change="perform(refreshData, '库存已切换。')"
          >
            <option :value="0">全部仓库</option>
            <option v-for="item in warehouses" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        >
        <!-- 用 Naive UI 按钮接入现有刷新操作，并以 Tailwind 工具类避免窄屏挤压。 -->
        <NButton
          text
          type="primary"
          class="shrink-0"
          :disabled="busy"
          @click="perform(refreshData, '数据已刷新。')"
          ><template #icon><IconRefreshLine aria-hidden="true" /></template
          >刷新</NButton
        >
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>物料编码</th>
              <th>物料名称</th>
              <th>数量</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in stock" :key="item.id">
              <td class="mono">{{ item.sku }}</td>
              <td>{{ item.name }}</td>
              <td>
                <strong>{{ item.quantity }}</strong> {{ item.unit }}
              </td>
            </tr>
            <tr v-if="!stock.length">
              <td colspan="3" class="muted">暂无物料，先到基础资料中添加。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">AUDIT TRAIL</p>
          <h2>库存流水</h2>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>仓库</th>
              <th>物料</th>
              <th>数量变动</th>
              <th>来源</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in movements" :key="item.id">
              <td>{{ localTime(item.created_at) }}</td>
              <td>{{ item.warehouse_name }}</td>
              <td>
                {{ item.material_name }}
                <small class="mono">{{ item.sku }}</small>
              </td>
              <td>
                {{ item.quantity.startsWith('-') ? '' : '+'
                }}{{ item.quantity }} {{ item.unit }}
              </td>
              <td>{{ movementSource(item) }}</td>
            </tr>
            <tr v-if="!movements.length">
              <td colspan="5" class="muted">
                确认入库、调拨、盘点、出库或退货后，这里会显示库存流水。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
