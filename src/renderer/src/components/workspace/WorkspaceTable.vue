<script setup lang="ts">
export interface WorkspaceTableColumn {
  key: string
  title: string
  width?: string
}

withDefaults(defineProps<{
  title: string
  description?: string
  columns: readonly WorkspaceTableColumn[]
  rowCount: number
  emptyText?: string
  loading?: boolean
}>(), {
  description: '',
  emptyText: '暂无数据',
  loading: false
})

// 功能区与业务行由页面填充，表格统一负责标题、列头、加载和空状态。
</script>

<template>
  <section class="card workspace-table">
    <header class="workspace-table-heading">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="description" class="muted">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="workspace-table-actions">
        <slot name="actions" />
      </div>
    </header>
    <div v-if="$slots.filters" class="workspace-table-filters">
      <slot name="filters" />
    </div>
    <div class="table-wrap">
      <table :aria-label="title">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.key" scope="col" :style="{ width: column.width }">
              {{ column.title }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length" class="workspace-table-message" role="status">正在加载…</td>
          </tr>
          <template v-else-if="rowCount > 0"><slot name="rows" /></template>
          <tr v-else>
            <td :colspan="columns.length" class="workspace-table-message">
              <slot name="empty">{{ emptyText }}</slot>
            </td>
          </tr>
        </tbody>
      </table>
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
.workspace-table-heading + .table-wrap { margin-top: 20px; }
.workspace-table table { min-width: 580px; }
.workspace-table-message { padding: 30px 12px; text-align: center; color: #79889d; }
.workspace-table-footer { margin-top: 16px; }
@media (max-width: 650px) {
  .workspace-table-heading { align-items: stretch; flex-direction: column; }
}
</style>
