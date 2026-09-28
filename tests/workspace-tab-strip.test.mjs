import assert from 'node:assert/strict'
import { test } from 'node:test'
import { scrollActiveTabIntoView, visibleTabScrollLeft } from '../src/renderer/src/utils/workspace-tab-strip.ts'

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

test('标签超出窗口时对真实容器发出滚动，已可见时不重复滚动', () => {
  const targets = []
  const tab = { getBoundingClientRect: () => ({ left: 450, right: 560 }) }
  const strip = {
    scrollLeft: 0,
    clientWidth: 300,
    querySelector: () => tab,
    getBoundingClientRect: () => ({ left: 100, right: 400 }),
    scrollTo: options => targets.push(options)
  }

  // 第一次进入最右侧标签时必须真正驱动容器；回到可视区后不产生额外滚动。
  scrollActiveTabIntoView(strip)
  assert.deepEqual(targets, [{ left: 160, behavior: 'auto' }])
  strip.scrollLeft = 160
  tab.getBoundingClientRect = () => ({ left: 290, right: 400 })
  scrollActiveTabIntoView(strip)
  assert.equal(targets.length, 1)
})
