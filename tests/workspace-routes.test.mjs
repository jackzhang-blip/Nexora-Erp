import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  canVisitRoute, nextExpandedGroup, resolveWorkspaceRoute, routeByKey, visibleRouteGroups, workspaceRouteGroups, workspaceRoutes
} from '../src/renderer/src/router/workspace-routes.ts'

test('每个工作台页面只有一个路由，且都对应实际页面', () => {
  const shell = readFileSync(new URL('../src/renderer/src/views/WorkspaceShell.vue', import.meta.url), 'utf8')
  const viewImports = new Map([...shell.matchAll(/^import (\w+) from '\.\/workspace\/([^']+\.vue)'$/gm)]
    .map(([, name, path]) => [name, path]))
  const pageEntries = [...shell.matchAll(/^  (\w+): (\w+View),?$/gm)]
  const pageKeys = pageEntries.map(([, key]) => key)

  // 路由、组件映射和实际文件必须同步，避免侧栏出现空白页面。
  assert.equal(workspaceRoutes.length, 21)
  assert.deepEqual(new Set(workspaceRoutes.map(route => route.key)), new Set(pageKeys))
  assert.match(shell, /<component :is="workspaceViews\[activeTab\]" \/>/)
  assert.equal(viewImports.size, workspaceRoutes.length)
  for (const [, key, component] of pageEntries) {
    const path = viewImports.get(component)
    const group = workspaceRouteGroups.find(entry => entry.routes.some(route => route.key === key))
    assert.ok(path?.startsWith(`${group?.key}/`), `${key} 应放在 ${group?.key} 页面目录`)
    assert.ok(existsSync(new URL(`../src/renderer/src/views/workspace/${path}`, import.meta.url)))
  }
  assert.equal(new Set(workspaceRoutes.map(route => route.path)).size, workspaceRoutes.length)
  assert.ok(workspaceRoutes.every(route => route.path.startsWith('/workspace/')))
})

test('侧栏按查看权限分类，隐藏空分类及未授权页面', () => {
  const groups = visibleRouteGroups(['sales.view', 'production_cost.view'])
  assert.deepEqual(groups.map(group => group.label), ['工作台', '销售管理', '生产管理', '系统管理'])
  assert.deepEqual(groups.flatMap(group => group.routes.map(route => route.key)), [
    'home', 'sales', 'shipments', 'salesReturns', 'productionCosts', 'settings'
  ])
  assert.equal(canVisitRoute(routeByKey('home'), []), true)
  assert.equal(canVisitRoute(routeByKey('stock'), ['sales.view']), false)
  assert.equal(canVisitRoute(routeByKey('settings'), []), true)
})

test('首页是登录账号均可见的固定入口与默认页面', () => {
  const sidebar = readFileSync(new URL('../src/renderer/src/components/workspace/WorkspaceSidebar.vue', import.meta.url), 'utf8')
  const state = readFileSync(new URL('../src/renderer/src/store/state.ts', import.meta.url), 'utf8')
  assert.equal(routeByKey('home').path, '/workspace/home')
  assert.match(sidebar, /v-if="group\.key === 'home'"[\s\S]*?@click="navigateToRoute\('home'\)"/)
  assert.match(state, /const activeTab = ref<WorkspaceRouteKey>\('home'\)/)
})

test('直接访问未授权或未知地址时回退到可访问页面', () => {
  const permissions = ['sales.view']
  assert.equal(resolveWorkspaceRoute('#/workspace/shipments', permissions).key, 'shipments')
  assert.equal(resolveWorkspaceRoute('#/workspace/users', permissions).key, 'home')
  assert.equal(resolveWorkspaceRoute('#/workspace/roles', permissions).key, 'home')
  assert.equal(resolveWorkspaceRoute('#/workspace/missing', permissions).key, 'home')
  assert.equal(resolveWorkspaceRoute('#/workspace/stock', []).key, 'home')
})

test('用户管理与权限管理有独立入口，且都要求用户管理权限', () => {
  const routes = visibleRouteGroups(['users.manage']).flatMap(group => group.routes)
  assert.deepEqual(routes.filter(route => ['users', 'roles'].includes(route.key)).map(route => route.label),
    ['用户管理', '权限管理'])
  assert.equal(resolveWorkspaceRoute('#/workspace/roles', ['users.manage']).key, 'roles')

  const userPage = readFileSync(new URL('../src/renderer/src/views/workspace/system/UserManagementView.vue', import.meta.url), 'utf8')
  const rolePage = readFileSync(new URL('../src/renderer/src/views/workspace/system/RolePermissionsView.vue', import.meta.url), 'utf8')
  // 表单分属两页，防止后续修改又把角色授权塞回用户列表。
  assert.match(userPage ?? '', /@submit\.prevent="createUser"/)
  assert.doesNotMatch(userPage ?? '', /@submit\.prevent="createRole"/)
  assert.match(rolePage ?? '', /@submit\.prevent="createRole"/)
  assert.doesNotMatch(rolePage ?? '', /@submit\.prevent="createUser"/)
  // 新建角色不能在管理员勾选前就带有默认业务权限。
  const state = readFileSync(new URL('../src/renderer/src/store/state.ts', import.meta.url), 'utf8')
  assert.match(state, /const newRole = ref\(\{ label: '', permissions: \[\] as string\[\] \}\)/)
})

test('权限被撤销后，当前地址也必须重新核对', () => {
  const route = routeByKey('finance')
  assert.equal(canVisitRoute(route, ['finance.view']), true)
  assert.equal(canVisitRoute(route, []), false)
  assert.equal(resolveWorkspaceRoute('#/workspace/finance', []).key, 'home')
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
  const sidebar = readFileSync(new URL('../src/renderer/src/components/workspace/WorkspaceSidebar.vue', import.meta.url), 'utf8')
  const style = readFileSync(new URL('../src/renderer/src/style.css', import.meta.url), 'utf8')

  // 内容保留在 DOM 中完成收起动画时，必须同步关闭交互与辅助技术访问。
  assert.match(sidebar, /class="nav-panel"[\s\S]*?:aria-hidden="expandedGroupKey !== group\.key"[\s\S]*?:inert="expandedGroupKey !== group\.key \? true : undefined"/)
  assert.match(style, /\.nav-panel \{[^}]*grid-template-rows: 0fr;[^}]*transition: grid-template-rows/)
  assert.match(style, /\.nav-panel\.expanded \{ grid-template-rows: 1fr;/)
  assert.match(style, /@media \(prefers-reduced-motion: reduce\) \{[^}]*\}[^}]*\.nav-panel[^}]*transition: none;/)
})
