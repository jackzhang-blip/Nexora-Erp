<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '../store/app-store'
import type { Component } from 'vue'
import WorkspaceSidebar from '../components/WorkspaceSidebar.vue'
import ThemeToggle from '../components/ThemeToggle.vue'
import WorkspaceTabs from '../components/WorkspaceTabs.vue'
import AppStatusFooter from '../components/AppStatusFooter.vue'
import AuthView from './AuthView.vue'
import { nexoraLogo } from '../assets/brand'
import type { WorkspaceRouteKey } from '../router/workspace-routes'
import { accountRoleText } from '../utils/account-role'
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
import HomeDashboardView from './workspace/home/HomeDashboardView.vue'

// 路由键与视图一一对应，避免页面再次回到 App.vue 的条件分支。
const workspaceViews: Record<WorkspaceRouteKey, Component> = {
  home: HomeDashboardView,
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
  notice,
  error,
  busy,
  user,
  username,
  password,
  roles,
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

// 登录、初始化和工作台共用内容区域与底栏。
const isAuthScreen = computed(() => screen.value === 'setup' || screen.value === 'login')
// 窄窗口与侧栏账号卡片共用角色名称规则，避免同一用户显示两种称呼。
const accountRole = computed(() => accountRoleText(user.value?.roles ?? [], roles.value))
</script>

<template>
  <div class="app-shell" :class="{ 'has-sidebar': screen === 'app' }">
    <!-- 只在进入工作台后挂载侧栏，进出时与内容列共用同一段过渡。 -->
    <Transition name="sidebar-slide">
      <WorkspaceSidebar v-if="screen === 'app'" />
    </Transition>

    <main class="content">
      <div class="content-body" :class="{ 'auth-screen': isAuthScreen }">
        <WorkspaceTabs v-if="screen === 'app'" />

        <header class="topbar">
          <!-- 登录标题沿用侧栏的品牌图形，保持未登录和工作台的视觉识别一致。 -->
          <span v-if="isAuthScreen" class="auth-header-mark" aria-hidden="true">
            <img :src="nexoraLogo" alt="" />
          </span>
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
            <!-- 侧栏在窄窗口收起时，顶部保留账号和退出操作。 -->
            <span class="account-identity"
              >{{ user.username
              }}<small>{{ accountRole }}</small></span
            ><ThemeToggle /><button class="text-button" type="button" @click="logout">
              退出登录
            </button>
          </div>
        </header>

        <div v-if="error" class="message error" role="alert">{{ error }}</div>
        <div v-if="notice" class="message success" role="status">
          {{ notice }}
        </div>

        <AuthView v-if="isAuthScreen" />
        <template v-else-if="screen === 'app' && activeRouteAllowed">
          <!-- 页面映射由路由键决定，新增页面须同时登记路由与视图。 -->
          <component :is="workspaceViews[activeTab]" />
        </template>
      </div>
      <AppStatusFooter />
    </main>
  </div>
</template>
