<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../store/app-store'
import type { Component } from 'vue'
import WorkspaceSidebar from '../components/WorkspaceSidebar.vue'
import WorkspaceTabs from '../components/WorkspaceTabs.vue'
import AuthView from './AuthView.vue'
import type { WorkspaceRouteKey } from '../router/workspace-routes'
import InventoryOverviewView from './workspace/warehouse/InventoryOverviewView.vue'
import WarehouseTransfersView from './workspace/warehouse/WarehouseTransfersView.vue'
import InventoryStocktakesView from './workspace/warehouse/InventoryStocktakesView.vue'
import MaterialsSuppliersView from './workspace/catalog/MaterialsSuppliersView.vue'
import PurchaseOrdersView from './workspace/purchase/PurchaseOrdersView.vue'
import PurchaseReceiptsView from './workspace/purchase/PurchaseReceiptsView.vue'
import PurchaseReturnsView from './workspace/purchase/PurchaseReturnsView.vue'
import SalesOrdersView from './workspace/sales/SalesOrdersView.vue'
import SalesShipmentsView from './workspace/sales/SalesShipmentsView.vue'
import SalesReturnsView from './workspace/sales/SalesReturnsView.vue'
import ReceivablesPayablesView from './workspace/finance/ReceivablesPayablesView.vue'
import ProductionBomsView from './workspace/production/ProductionBomsView.vue'
import ProductionWorkOrdersView from './workspace/production/ProductionWorkOrdersView.vue'
import MaterialIssuesView from './workspace/production/MaterialIssuesView.vue'
import MaterialReturnsView from './workspace/production/MaterialReturnsView.vue'
import ProductionCompletionsView from './workspace/production/ProductionCompletionsView.vue'
import ProductionCostsView from './workspace/production/ProductionCostsView.vue'
import UserManagementView from './workspace/system/UserManagementView.vue'
import RolePermissionsView from './workspace/system/RolePermissionsView.vue'
import ConnectionSettingsView from './workspace/system/ConnectionSettingsView.vue'

// 路由键与视图一一对应，避免页面再次回到 App.vue 的条件分支。
const workspaceViews: Record<WorkspaceRouteKey, Component> = {
  stock: InventoryOverviewView,
  transfers: WarehouseTransfersView,
  stocktakes: InventoryStocktakesView,
  catalog: MaterialsSuppliersView,
  purchase: PurchaseOrdersView,
  receipts: PurchaseReceiptsView,
  purchaseReturns: PurchaseReturnsView,
  sales: SalesOrdersView,
  shipments: SalesShipmentsView,
  salesReturns: SalesReturnsView,
  finance: ReceivablesPayablesView,
  boms: ProductionBomsView,
  workOrders: ProductionWorkOrdersView,
  materialIssues: MaterialIssuesView,
  materialReturns: MaterialReturnsView,
  productionCompletions: ProductionCompletionsView,
  productionCosts: ProductionCostsView,
  users: UserManagementView,
  roles: RolePermissionsView,
  settings: ConnectionSettingsView
}

const {
  screen,
  activeTab,
  expandedGroupKey,
  version,
  notice,
  error,
  busy,
  user,
  username,
  password,
  roles,
  server,
  connectionLost,
  visibleGroups,
  visibleTabs,
  openedTabs,
  activeRouteAllowed,
  toggleRouteGroup,
  navigateToRoute,
  closeOpenedRoute,
  switchServer,
  authenticate,
  logout
} = useAppStore()

// 登录与管理员初始化共用底部状态栏，切换到工作台后恢复原有页面提示。
const isAuthScreen = computed(() => screen.value === 'setup' || screen.value === 'login')
</script>

<template>
  <div class="app-shell" :class="{ 'auth-shell': isAuthScreen }">
    <WorkspaceSidebar />

    <main class="content" :class="{ 'auth-content': isAuthScreen }">
      <div class="content-body">
        <WorkspaceTabs v-if="screen === 'app'" />

        <header class="topbar">
          <div>
            <p class="eyebrow">NEXORA WORKSPACE</p>
            <h1>
              {{
                screen === 'app'
                  ? visibleTabs.find((item) => item.key === activeTab)?.label
                  : '开始使用联光 ERP'
              }}
            </h1>
          </div>
          <div v-if="user" class="account">
            <span
              >{{ user.username
              }}<small>{{ user.roles.join(' · ') }}</small></span
            ><button class="text-button" type="button" @click="logout">
              退出登录
            </button>
          </div>
        </header>

        <div v-if="error" class="message error" role="alert">{{ error }}</div>
        <div v-if="connectionLost" class="message error" role="alert">
          服务端连接已中断，正在重试。恢复连接前无法保存更改。
        </div>
        <div v-if="notice && !isAuthScreen" class="message success" role="status">
          {{ notice }}
        </div>

        <AuthView v-if="isAuthScreen" />
        <template v-else-if="screen === 'app' && activeRouteAllowed">
          <!-- 页面映射由路由键决定，新增页面须同时登记路由与视图。 -->
          <component :is="workspaceViews[activeTab]" />
        </template>
      </div>
      <footer v-if="isAuthScreen" class="onboard-footer auth-footer">
        <span class="onboard-footer-copy">联光 ERP · 团队工作台</span>
        <!-- 登录页的成功反馈放进固定底栏，表单区只保留需要立即处理的错误。 -->
        <span v-if="notice" class="onboard-footer-status" role="status">{{ notice }}</span>
        <span class="onboard-footer-copy"
          >{{ server?.name || '当前服务端' }}<span v-if="version"> · v{{ version }}</span></span
        >
      </footer>
    </main>
  </div>
</template>
