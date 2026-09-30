<script lang="ts">
import { VxeUI } from '@vxe-ui/core'
import zhCN from 'vxe-table/es/locale/lang/zh-CN'

// 分组件加载时显式安装中文文案，避免表格内置提示回退为语言键。
VxeUI.setI18n('zh-CN', zhCN)
</script>

<script setup lang="ts" generic="TRow extends object">
import VxeColumn from 'vxe-table/es/column'
import VxeTable from 'vxe-table/es/table'
import 'vxe-table/es/table/style.css'

interface WorkspaceTableColumn {
  key: string
  title: string
  width?: string
}

withDefaults(defineProps<{
  title: string
  description?: string
  columns?: readonly WorkspaceTableColumn[]
  data?: TRow[]
  emptyText?: string
  loading?: boolean
  minTableWidth?: number
}>(), {
  description: '',
  columns: () => [],
  data: () => [],
  emptyText: '暂无数据',
  loading: false,
  minTableWidth: 580
})

// 数据类型从页面传入的行推断，业务单元格继续获得原本的字段类型。
defineSlots<{
  heading?: () => unknown
  actions?: () => unknown
  filters?: () => unknown
  beforeTable?: () => unknown
  empty?: () => unknown
  footer?: () => unknown
  [name: `cell-${string}`]: (props: { row: TRow }) => unknown
}>()

// 所有业务列表只提供数据与单元格插槽；表格的渲染、空状态和加载状态由这里统一管理。
</script>

<template>
  <section class="card workspace-table">
    <header class="workspace-table-heading">
      <div>
        <slot name="heading">
          <h2>{{ title }}</h2>
          <p v-if="description" class="muted">{{ description }}</p>
        </slot>
      </div>
      <div v-if="$slots.actions" class="workspace-table-actions">
        <slot name="actions" />
      </div>
    </header>
    <div v-if="$slots.filters" class="workspace-table-filters">
      <slot name="filters" />
    </div>
    <div v-if="$slots.beforeTable" class="workspace-table-before">
      <slot name="beforeTable" />
    </div>
    <div class="table-wrap">
      <span v-if="loading" class="workspace-table-status" role="status">正在加载…</span>
      <VxeTable class="workspace-vxe-table" :aria-label="title" :aria-busy="loading" :data="data" :loading="loading" :style="{ minWidth: `${minTableWidth}px` }">
        <VxeColumn v-for="column in columns" :key="column.key" :field="column.key" :title="column.title" :width="column.width">
          <template v-if="$slots[`cell-${column.key}`]" #default="{ row }">
            <slot :name="`cell-${column.key}`" :row="row" />
          </template>
        </VxeColumn>
        <template #empty><slot v-if="!loading" name="empty">{{ emptyText }}</slot></template>
        <template #loading><div class="workspace-table-loading" role="status">正在加载…</div></template>
      </VxeTable>
    </div>
    <footer v-if="$slots.footer" class="workspace-table-footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.workspace-table-heading { display: flex; justify-content: space-between; align-items: start; gap: 18px; }
.workspace-table-heading h2 { margin: 0; }
.workspace-table-heading .muted { margin: 8px 0 0; }
.workspace-table-actions, .workspace-table-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.workspace-table-filters { margin: 21px 0 16px; }
.workspace-table-before { margin-bottom: 20px; }
.workspace-table-before:empty { display: none; }
.workspace-table-heading + .table-wrap { margin-top: 20px; }
.workspace-table-footer { margin-top: 16px; }
.workspace-table-status { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.workspace-table-loading { padding: 20px; color: var(--vxe-ui-font-color); text-align: center; }
@media (max-width: 650px) {
  .workspace-table-heading { align-items: stretch; flex-direction: column; }
}
</style>

<style>
/* 公共表格统一匹配工作台明暗主题，并撤销原生表格规则对 vxe 行高的影响。 */
.workspace-vxe-table {
  --vxe-ui-font-color: #263950;
  --vxe-ui-font-primary-color: #197d79;
  --vxe-ui-layout-background-color: #fff;
  --vxe-ui-table-header-background-color: #f5f7f9;
  --vxe-ui-table-border-color: #edf0f3;
}
.workspace-vxe-table table { border-collapse: separate; border-spacing: 0; }
.workspace-vxe-table :is(th, td) { padding: 0; border-bottom: 0; vertical-align: middle; }
:root[data-theme='dark'] .workspace-vxe-table {
  --vxe-ui-font-color: #e6edf8;
  --vxe-ui-font-primary-color: #7dd8cf;
  --vxe-ui-layout-background-color: #142238;
  --vxe-ui-table-header-background-color: #203047;
  --vxe-ui-table-border-color: #2d3e57;
}
</style>
