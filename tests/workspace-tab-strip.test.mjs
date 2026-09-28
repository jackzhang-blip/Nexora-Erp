import assert from 'node:assert/strict'
import { test } from 'node:test'
import { visibleTabScrollLeft } from '../src/renderer/src/workspace-tab-strip.ts'

// 同时覆盖新增标签向右跟随和切回旧标签向左跟随，防止页面栏停在原位置。
test('新标签超出右边界时滚到可见位置', () => {
  assert.equal(visibleTabScrollLeft(0, 300, 310, 430), 130)
  assert.equal(visibleTabScrollLeft(130, 300, 420, 540), 240)
})

test('切回左侧标签时向前滚动，已可见的标签不移动页面栏', () => {
  assert.equal(visibleTabScrollLeft(240, 300, 70, 180), 70)
  assert.equal(visibleTabScrollLeft(70, 300, 110, 220), 70)
  assert.equal(visibleTabScrollLeft(240, 300, 0, 120), 0)
})
