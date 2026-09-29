import { createRouter } from 'vue-router'
import type { Component } from 'vue'
import type { Router, RouterHistory, RouteRecordRaw } from 'vue-router'
import { canVisitRoute, workspaceRoutes } from './workspace-routes.ts'
import type { WorkspaceRouteKey } from './workspace-routes.ts'

// 路由键与页面组件在一处对应，新增业务页面时类型检查会要求补齐组件。
const workspaceRouteComponents = {
  home: () => import('../views/workspace/home/HomeDashboardView.vue'),
  stock: () => import('../views/workspace/warehouse/InventoryOverviewView.vue'),
  transfers: () => import('../views/workspace/warehouse/WarehouseTransfersView.vue'),
  stocktakes: () => import('../views/workspace/warehouse/InventoryStocktakesView.vue'),
  catalog: () => import('../views/workspace/catalog/MaterialsView.vue'),
  suppliers: () => import('../views/workspace/catalog/SuppliersView.vue'),
  warehouses: () => import('../views/workspace/catalog/WarehousesView.vue'),
  purchase: () => import('../views/workspace/purchase/PurchaseOrdersView.vue'),
  receipts: () => import('../views/workspace/purchase/PurchaseReceiptsView.vue'),
  purchaseReturns: () => import('../views/workspace/purchase/PurchaseReturnsView.vue'),
  sales: () => import('../views/workspace/sales/SalesOrdersView.vue'),
  shipments: () => import('../views/workspace/sales/SalesShipmentsView.vue'),
  salesReturns: () => import('../views/workspace/sales/SalesReturnsView.vue'),
  finance: () => import('../views/workspace/finance/ReceivablesPayablesView.vue'),
  boms: () => import('../views/workspace/production/ProductionBomsView.vue'),
  workOrders: () => import('../views/workspace/production/ProductionWorkOrdersView.vue'),
  materialIssues: () => import('../views/workspace/production/MaterialIssuesView.vue'),
  materialReturns: () => import('../views/workspace/production/MaterialReturnsView.vue'),
  productionCompletions: () => import('../views/workspace/production/ProductionCompletionsView.vue'),
  productionCosts: () => import('../views/workspace/production/ProductionCostsView.vue'),
  users: () => import('../views/workspace/system/UserManagementView.vue'),
  roles: () => import('../views/workspace/system/RolePermissionsView.vue'),
  settings: () => import('../views/workspace/system/ConnectionSettingsView.vue')
} satisfies Record<WorkspaceRouteKey, () => Promise<unknown>>

export function createWorkspaceRouter(
  history: RouterHistory,
  componentOverrides: Partial<Record<WorkspaceRouteKey, Component>> = {}
): Router {
  const routes: RouteRecordRaw[] = workspaceRoutes.map((route) => ({
    path: route.path,
    name: route.key,
    component: componentOverrides[route.key] ?? workspaceRouteComponents[route.key]
  }))
  // 旧书签或未知地址统一回首页；权限判断另由守卫处理。
  routes.push({ path: '/:pathMatch(.*)*', redirect: '/workspace/home' })
  return createRouter({ history, routes })
}

export function installWorkspaceAccessGuard(
  router: Router,
  getPermissions: () => readonly string[] | null
): () => void {
  return router.beforeEach((to) => {
    const requested = workspaceRoutes.find((route) => route.path === to.path)
    const permissions = getPermissions()
    // 登录前保留深链接，认证成功并取得权限后再核对；此时工作台尚不渲染。
    if (!requested || permissions === null) return true
    if (!canVisitRoute(requested, permissions))
      return { path: '/workspace/home', replace: true }
    return true
  })
}
