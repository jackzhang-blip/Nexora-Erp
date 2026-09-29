import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  demoDashboardSnapshots,
  trendArea,
  trendCoordinates,
  trendLine
} from '../src/renderer/src/views/workspace/home/dashboard-data.ts'

test('两个演示时间范围都提供可画出的趋势和完整构成', () => {
  for (const snapshot of Object.values(demoDashboardSnapshots)) {
    assert.equal(snapshot.metrics.length, 4)
    assert.equal(snapshot.trend.labels.length, snapshot.trend.sales.length)
    assert.equal(snapshot.trend.labels.length, snapshot.trend.purchase.length)
    assert.equal(snapshot.composition.reduce((sum, item) => sum + item.percent, 0), 100)
    assert.ok(snapshot.pipeline.every((item) => item.count >= 0))
  }
  assert.notDeepEqual(demoDashboardSnapshots['7d'].trend, demoDashboardSnapshots['30d'].trend)
})

test('空趋势和单点趋势保持有效 SVG 坐标', () => {
  assert.deepEqual(trendCoordinates([], 0), [])
  assert.equal(trendLine([]), '')
  assert.equal(trendArea([]), '')
  const point = trendCoordinates([5], 0)
  assert.deepEqual(point, [{ x: 320, y: 40 }])
  assert.ok(!trendArea(point).includes('NaN'))
})

test('两条趋势共用纵轴，横轴从左到右且面积闭合', () => {
  const low = trendCoordinates([0, 10, 20], 40)
  const high = trendCoordinates([20, 30, 40], 40)
  assert.deepEqual(low.map((point) => point.x), [28, 320, 612])
  assert.ok(high[0].y < low[0].y)
  assert.match(trendLine(high), /^28,115 /)
  assert.match(trendArea(high), /^M 28 190 L /)
  assert.match(trendArea(high), / L 612 190 Z$/)
})
