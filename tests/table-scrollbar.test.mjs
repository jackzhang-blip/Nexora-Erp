import assert from 'node:assert/strict'
import { test } from 'node:test'
import { tableScrollbarMetrics } from '../src/renderer/src/utils/table-scrollbar.ts'

test('表格不超出容器时不显示横向滚动条', () => {
  assert.deepEqual(tableScrollbarMetrics(800, 700), { max: 0, thumbWidth: 800 })
})

test('窄窗口按可见比例计算滚动范围和手柄宽度', () => {
  assert.deepEqual(tableScrollbarMetrics(580, 1000), { max: 420, thumbWidth: 336 })
  // 表格特别宽时仍保留可拖动的手柄，不让滚动入口消失。
  assert.deepEqual(tableScrollbarMetrics(100, 10000), { max: 9900, thumbWidth: 44 })
})
