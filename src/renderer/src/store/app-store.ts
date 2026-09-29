import {
  computed,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  provide,
  ref,
  watch
} from 'vue'
// 从 Remix Icon 的 ri 图标集按需导入，构建时会把 SVG 打包进应用。
import IconStackLine from '~icons/ri/stack-line'
import IconArchiveLine from '~icons/ri/archive-line'
import IconFileList3Line from '~icons/ri/file-list-3-line'
import IconHistoryLine from '~icons/ri/history-line'
import IconTeamLine from '~icons/ri/team-line'
import IconSettings3Line from '~icons/ri/settings-3-line'
import IconDashboardLine from '~icons/ri/dashboard-line'
import type {
  ConnectionCandidate,
  DiscoveryResult,
  HostStatus,
  ServerProfile
} from '../../../shared/desktop-api'
import {
  canVisitRoute,
  closeRoute,
  nextExpandedGroup,
  openRoute,
  permittedOpenedRoutes,
  resolveWorkspaceRoute,
  routeByKey,
  visibleRouteGroups
} from '../router/workspace-routes'
import type {
  WorkspaceRouteGroupKey,
  WorkspaceRouteKey
} from '../router/workspace-routes'
import { scrollActiveTabIntoView } from '../utils/workspace-tab-strip'

import { createAppState } from './state'
import { createDataLoader } from './data-loader'
import { createConnectionActions } from './connection-actions'
import { createCatalogActions } from './modules/catalog-actions'
import { createPurchaseActions } from './modules/purchase-actions'
import { createWarehouseActions } from './modules/warehouse-actions'
import { createFinanceActions } from './modules/finance-actions'
import { createSalesActions } from './modules/sales-actions'
import { createProductionActions } from './modules/production-actions'
import { createAccessActions } from './modules/access-actions'
import {
  displayError,
  localTime,
  movementSource,
  financialSource,
  paymentActionLabel
} from '../utils/formatters'

import type { Screen } from './types'

// 每个窗口创建独立 store，业务页面通过注入共享同一份会话状态。
function createAppStore() {
  const state = createAppState()
  const {
    screen,
    activeTab,
    openedRouteKeys,
    expandedGroupKey,
    version,
    notice,
    error,
    busy,
    user,
    permissions,
    hostForm,
    connectionLost
  } = state
  let healthTimer: ReturnType<typeof setInterval> | null = null

  const can = (permission: string): boolean =>
    user.value?.permissions.includes(permission) ?? false
  const routeIcons = {
    dashboard: IconDashboardLine,
    stack: IconStackLine,
    archive: IconArchiveLine,
    file: IconFileList3Line,
    history: IconHistoryLine,
    team: IconTeamLine,
    settings: IconSettings3Line
  }
  // 分类和权限来自同一张路由表，避免侧栏与地址访问使用两套规则。
  const visibleGroups = computed(() =>
    visibleRouteGroups(user.value?.permissions ?? []).map((group) => ({
      ...group,
      routes: group.routes.map((route) => ({
        ...route,
        icon: routeIcons[route.icon]
      }))
    }))
  )
  const visibleTabs = computed(() =>
    visibleGroups.value.flatMap((group) => group.routes)
  )
  const openedTabs = computed(() => openedRouteKeys.value.map(routeByKey))
  function revealCurrentTab(): void {
    // 路由先更新页面和标签，再在 Vue 完成 DOM 更新后调整横向滚动位置。
    void nextTick(() => {
      const strip = document.querySelector<HTMLElement>('.workspace-tabs')
      if (strip) scrollActiveTabIntoView(strip)
    })
  }
  watch(screen, (current) => {
    // 再次登录时从全部收起开始，不保留上个账号的侧栏状态。
    if (current !== 'app') {
      expandedGroupKey.value = null
      // 页面栏只属于当前登录会话，退出后不向下一个账号展示访问记录。
      openedRouteKeys.value = []
    }
  })
  watch(visibleGroups, (groups) => {
    // 当前账号失去某分类的查看权限后，清除其展开状态。
    if (
      expandedGroupKey.value &&
      !groups.some((group) => group.key === expandedGroupKey.value)
    )
      expandedGroupKey.value = null
  })
  // 用户切换或权限被撤销时，页面内容必须和入口使用同一条权限规则。
  const activeRouteAllowed = computed(
    () =>
      user.value !== null &&
      canVisitRoute(routeByKey(activeTab.value), user.value.permissions)
  )

  function toggleRouteGroup(key: WorkspaceRouteGroupKey): void {
    expandedGroupKey.value = nextExpandedGroup(expandedGroupKey.value, key)
  }

  function syncWorkspaceRoute(): void {
    if (screen.value !== 'app' || !user.value) return
    const route = resolveWorkspaceRoute(
      window.location.hash,
      user.value.permissions
    )
    openedRouteKeys.value = openRoute(
      permittedOpenedRoutes(openedRouteKeys.value, user.value.permissions),
      route.key
    )
    activeTab.value = route.key
    revealCurrentTab()
    if (window.location.hash !== `#${route.path}`) {
      // 未授权或未知地址不留在历史记录中，也不渲染原页面。
      window.history.replaceState(null, '', `#${route.path}`)
    }
  }

  function navigateToRoute(key: WorkspaceRouteKey): void {
    if (!user.value) return
    const route = routeByKey(key)
    if (!canVisitRoute(route, user.value.permissions)) return
    openedRouteKeys.value = openRoute(openedRouteKeys.value, key)
    activeTab.value = key
    revealCurrentTab()
    window.location.hash = route.path
  }

  function closeOpenedRoute(key: WorkspaceRouteKey): void {
    const result = closeRoute(openedRouteKeys.value, key, activeTab.value)
    openedRouteKeys.value = result.opened
    if (result.active !== activeTab.value) navigateToRoute(result.active)
  }
  const refreshData = createDataLoader(state, can, syncWorkspaceRoute)
  const connectionActions = createConnectionActions(state, refreshData)
  const { checkConnection, stopScan, monitorConnection } = connectionActions

  async function perform(
    action: () => Promise<unknown>,
    success: string
  ): Promise<void> {
    if (busy.value) return
    if (connectionLost.value) {
      error.value = '服务端连接已中断，恢复连接后才能保存更改。'
      return
    }
    busy.value = true
    error.value = ''
    notice.value = ''
    try {
      await action()
      await refreshData()
      notice.value = success
    } catch (cause) {
      error.value = displayError(cause)
    } finally {
      busy.value = false
    }
  }

  const catalogActions = createCatalogActions(state, perform)
  const purchaseActions = createPurchaseActions(state, perform)
  const warehouseActions = createWarehouseActions(state, perform)
  const financeActions = createFinanceActions(state, perform)

  const salesActions = createSalesActions(state, perform)

  const productionActions = createProductionActions(
    state,
    perform,
    navigateToRoute
  )

  const accessActions = createAccessActions(state, perform)

  onMounted(async () => {
    window.addEventListener('hashchange', syncWorkspaceRoute)
    window.addEventListener('resize', revealCurrentTab)
    if (window.nexora)
      version.value = await window.nexora.getVersion().catch(() => '')
    if (window.nexora)
      hostForm.value.dataDir = await window.nexora
        .defaultDataDir()
        .catch(() => '')
    await checkConnection()
    healthTimer = setInterval(() => {
      void monitorConnection()
    }, 5000)
  })

  onUnmounted(() => {
    void stopScan()
    if (healthTimer) clearInterval(healthTimer)
    window.removeEventListener('hashchange', syncWorkspaceRoute)
    window.removeEventListener('resize', revealCurrentTab)
  })
  return {
    ...state,
    ...connectionActions,
    ...catalogActions,
    ...purchaseActions,
    ...warehouseActions,
    ...financeActions,
    ...salesActions,
    ...productionActions,
    ...accessActions,
    can,
    visibleGroups,
    visibleTabs,
    openedTabs,
    revealCurrentTab,
    activeRouteAllowed,
    toggleRouteGroup,
    syncWorkspaceRoute,
    navigateToRoute,
    closeOpenedRoute,
    displayError,
    localTime,
    movementSource,
    financialSource,
    refreshData,
    perform,
    paymentActionLabel
  }
}

export type AppStore = ReturnType<typeof createAppStore>
const appStoreKey = Symbol('nexora-app-store')

export function provideAppStore(): AppStore {
  const store = createAppStore()
  provide(appStoreKey, store)
  return store
}

export function useAppStore(): AppStore {
  const store = inject<AppStore>(appStoreKey)
  if (!store) throw new Error('缺少应用状态提供者')
  return store
}
