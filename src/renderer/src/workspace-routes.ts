/** 工作台页面地址与查看权限统一在此登记，写操作仍由服务端逐项授权。 */
type RouteIcon = 'stack' | 'archive' | 'file' | 'history' | 'team' | 'settings'

interface RouteEntry {
  key: string
  path: string
  label: string
  permission: string | null
  icon: RouteIcon
}

interface RouteGroup {
  key: string
  label: string
  routes: readonly RouteEntry[]
}

export const workspaceRouteGroups = [
  { key: 'warehouse', label: '仓库管理', routes: [
    { key: 'stock', path: '/workspace/stock', label: '库存总览', permission: 'inventory.view', icon: 'stack' },
    { key: 'transfers', path: '/workspace/transfers', label: '仓库调拨', permission: 'inventory.view', icon: 'stack' },
    { key: 'stocktakes', path: '/workspace/stocktakes', label: '库存盘点', permission: 'inventory.view', icon: 'file' }
  ] },
  { key: 'catalog', label: '基础资料', routes: [
    { key: 'catalog', path: '/workspace/catalog', label: '物料与供应商', permission: 'inventory.view', icon: 'archive' }
  ] },
  { key: 'purchase', label: '采购管理', routes: [
    { key: 'purchase', path: '/workspace/purchase-orders', label: '采购订单', permission: 'inventory.view', icon: 'file' },
    { key: 'receipts', path: '/workspace/receipts', label: '采购入库', permission: 'inventory.view', icon: 'file' },
    { key: 'purchaseReturns', path: '/workspace/purchase-returns', label: '采购退货', permission: 'inventory.view', icon: 'history' }
  ] },
  { key: 'sales', label: '销售管理', routes: [
    { key: 'sales', path: '/workspace/sales-orders', label: '销售订单', permission: 'sales.view', icon: 'file' },
    { key: 'shipments', path: '/workspace/shipments', label: '销售出库', permission: 'sales.view', icon: 'archive' },
    { key: 'salesReturns', path: '/workspace/sales-returns', label: '销售退货', permission: 'sales.view', icon: 'history' }
  ] },
  { key: 'finance', label: '财务管理', routes: [
    { key: 'finance', path: '/workspace/finance', label: '应收应付', permission: 'finance.view', icon: 'file' }
  ] },
  { key: 'production', label: '生产管理', routes: [
    { key: 'boms', path: '/workspace/boms', label: '生产 BOM', permission: 'production.view', icon: 'stack' },
    { key: 'workOrders', path: '/workspace/work-orders', label: '生产工单', permission: 'production.view', icon: 'file' },
    { key: 'materialIssues', path: '/workspace/material-issues', label: '生产领料', permission: 'production.view', icon: 'archive' },
    { key: 'materialReturns', path: '/workspace/material-returns', label: '生产退料', permission: 'production.view', icon: 'history' },
    { key: 'productionCompletions', path: '/workspace/production-completions', label: '完工与质检', permission: 'production.view', icon: 'file' },
    { key: 'productionCosts', path: '/workspace/production-costs', label: '生产成本', permission: 'production_cost.view', icon: 'file' }
  ] },
  { key: 'system', label: '系统管理', routes: [
    { key: 'users', path: '/workspace/users', label: '用户权限', permission: 'users.manage', icon: 'team' },
    { key: 'settings', path: '/workspace/settings', label: '连接与服务', permission: null, icon: 'settings' }
  ] }
] as const satisfies readonly RouteGroup[]

export type WorkspaceRoute = (typeof workspaceRouteGroups)[number]['routes'][number]
export type WorkspaceRouteKey = WorkspaceRoute['key']
export type WorkspaceRouteGroupKey = (typeof workspaceRouteGroups)[number]['key']
export const workspaceRoutes: readonly WorkspaceRoute[] = workspaceRouteGroups.flatMap<WorkspaceRoute>(group => group.routes)

export function nextExpandedGroup(current: WorkspaceRouteGroupKey | null, selected: WorkspaceRouteGroupKey): WorkspaceRouteGroupKey | null {
  // 只保存一个展开项；再次选择同一分类时恢复全部收起状态。
  return current === selected ? null : selected
}

export function canVisitRoute(route: WorkspaceRoute, permissions: readonly string[]): boolean {
  return route.permission === null || permissions.includes(route.permission)
}

export function routeByKey(key: WorkspaceRouteKey): WorkspaceRoute {
  return workspaceRoutes.find(route => route.key === key)!
}

export function resolveWorkspaceRoute(hash: string, permissions: readonly string[]): WorkspaceRoute {
  const requested = workspaceRoutes.find(route => hash === `#${route.path}`)
  if (requested && canVisitRoute(requested, permissions)) return requested
  // 未知地址或权限被撤销时，只回退到当前账号能看的页面。
  return workspaceRoutes.find(route => canVisitRoute(route, permissions))!
}

export function visibleRouteGroups(permissions: readonly string[]) {
  return workspaceRouteGroups.map(group => ({
    key: group.key,
    label: group.label,
    routes: group.routes.filter(route => canVisitRoute(route, permissions))
  })).filter(group => group.routes.length > 0)
}
