import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  canVisitRoute, nextExpandedGroup, resolveWorkspaceRoute, routeByKey, visibleRouteGroups, workspaceRoutes
} from '../src/renderer/src/workspace-routes.ts'

test('每个工作台页面只有一个路由，且都对应实际页面', () => {
  const app = readFileSync(new URL('../src/renderer/src/App.vue', import.meta.url), 'utf8')
  const pageKeys = [...app.matchAll(/<section v-if="activeTab === '([^']+)'/g)].map(match => match[1])

  // 路由登记与页面必须同步，避免出现可以点击却无法打开的入口。
  assert.equal(workspaceRoutes.length, 19)
  assert.deepEqual(new Set(workspaceRoutes.map(route => route.key)), new Set(pageKeys))
  assert.equal(new Set(workspaceRoutes.map(route => route.path)).size, workspaceRoutes.length)
  assert.ok(workspaceRoutes.every(route => route.path.startsWith('/workspace/')))
})

test('侧栏按查看权限分类，隐藏空分类及未授权页面', () => {
  const groups = visibleRouteGroups(['sales.view', 'production_cost.view'])
  assert.deepEqual(groups.map(group => group.label), ['销售管理', '生产管理', '系统管理'])
  assert.deepEqual(groups.flatMap(group => group.routes.map(route => route.key)), [
    'sales', 'shipments', 'salesReturns', 'productionCosts', 'settings'
  ])
  assert.equal(canVisitRoute(routeByKey('stock'), ['sales.view']), false)
  assert.equal(canVisitRoute(routeByKey('settings'), []), true)
})

test('直接访问未授权或未知地址时回退到可访问页面', () => {
  const permissions = ['sales.view']
  assert.equal(resolveWorkspaceRoute('#/workspace/shipments', permissions).key, 'shipments')
  assert.equal(resolveWorkspaceRoute('#/workspace/users', permissions).key, 'sales')
  assert.equal(resolveWorkspaceRoute('#/workspace/missing', permissions).key, 'sales')
  assert.equal(resolveWorkspaceRoute('#/workspace/stock', []).key, 'settings')
})

test('权限被撤销后，当前地址也必须重新核对', () => {
  const route = routeByKey('finance')
  assert.equal(canVisitRoute(route, ['finance.view']), true)
  assert.equal(canVisitRoute(route, []), false)
  assert.equal(resolveWorkspaceRoute('#/workspace/finance', []).key, 'settings')
})

test('分类默认收起，同一时间只能展开一个分类', () => {
  let expanded = null
  expanded = nextExpandedGroup(expanded, 'warehouse')
  assert.equal(expanded, 'warehouse')
  expanded = nextExpandedGroup(expanded, 'finance')
  assert.equal(expanded, 'finance')
  expanded = nextExpandedGroup(expanded, 'finance')
  assert.equal(expanded, null)
})

test('收起的页面入口不可聚焦，动效遵循减少动态效果设置', () => {
  const app = readFileSync(new URL('../src/renderer/src/App.vue', import.meta.url), 'utf8')
  const style = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')

  // 内容保留在 DOM 中完成收起动画时，必须同步关闭交互与辅助技术访问。
  assert.match(app, /class="nav-panel"[^>]*:aria-hidden="expandedGroupKey !== group\.key"[^>]*:inert="expandedGroupKey !== group\.key"/)
  assert.match(style, /\.nav-panel \{[^}]*grid-template-rows: 0fr;[^}]*transition: grid-template-rows/)
  assert.match(style, /\.nav-panel\.expanded \{ grid-template-rows: 1fr;/)
  assert.match(style, /@media \(prefers-reduced-motion: reduce\) \{[^}]*\}[^}]*\.nav-panel[^}]*transition: none;/)
})
