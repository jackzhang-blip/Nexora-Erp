<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NButton, NConfigProvider, dateZhCN, zhCN } from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
// 应用内品牌标记与安装包图标共用第一版 Nexus + Aurora 标志。
import nexoraLogo from '../../../resources/icon.png'
// 从 Remix Icon 的 ri 图标集按需导入，构建时会把 SVG 打包进应用。
import IconArrowRightUpLine from '~icons/ri/arrow-right-up-line'
import IconRadarLine from '~icons/ri/radar-line'
import IconServerLine from '~icons/ri/server-line'
import IconHistoryLine from '~icons/ri/history-line'
import IconAddLine from '~icons/ri/add-line'
import IconCheckboxCircleLine from '~icons/ri/checkbox-circle-line'
import IconErrorWarningLine from '~icons/ri/error-warning-line'
import IconRefreshLine from '~icons/ri/refresh-line'
import IconStackLine from '~icons/ri/stack-line'
import IconArchiveLine from '~icons/ri/archive-line'
import IconFileList3Line from '~icons/ri/file-list-3-line'
import IconTeamLine from '~icons/ri/team-line'
import IconSettings3Line from '~icons/ri/settings-3-line'
import type { Bom, Customer, FinanceAccount, FinancialEntry, Material, MaterialIssue, MaterialReturn, Movement, PaymentRecord, Permission, ProductionCompletion, ProductionCostReport, PurchaseOrder, PurchaseReturn, ReceivablesPayables, Receipt, Role, SalesOrder, SalesReturn, Shipment, Stock, Stocktake, Supplier, Transfer, User, Warehouse, WorkOrder } from '../../shared/erp-api'
import type { ConnectionCandidate, DiscoveryResult, HostStatus, ServerProfile } from '../../shared/desktop-api'

type Screen = 'loading' | 'welcome' | 'manual' | 'scan' | 'results' | 'create' | 'trust' | 'ready' | 'offline' | 'setup' | 'login' | 'app'
type Tab = 'stock' | 'catalog' | 'purchase' | 'receipts' | 'purchaseReturns' | 'transfers' | 'stocktakes' | 'sales' | 'shipments' | 'salesReturns' | 'finance' | 'boms' | 'workOrders' | 'materialIssues' | 'materialReturns' | 'productionCompletions' | 'productionCosts' | 'users' | 'settings'

// 让新增的 Naive UI 控件沿用工作台现有的青绿色主色。
const naiveThemeOverrides: GlobalThemeOverrides = {
  common: { primaryColor: '#237d7a', primaryColorHover: '#1d6c69', primaryColorPressed: '#195d5a' }
}

const screen = ref<Screen>('loading')
const activeTab = ref<Tab>('stock')
const version = ref('')
const notice = ref('')
const error = ref('')
const busy = ref(false)
const user = ref<User | null>(null)
const username = ref('')
const password = ref('')
const materials = ref<Material[]>([])
const suppliers = ref<Supplier[]>([])
const stock = ref<Stock[]>([])
const movements = ref<Movement[]>([])
const receipts = ref<Receipt[]>([])
const purchaseOrders = ref<PurchaseOrder[]>([])
const purchaseReturns = ref<PurchaseReturn[]>([])
const receivablesPayables = ref<ReceivablesPayables | null>(null)
const financeAccounts = ref<FinanceAccount[]>([])
const paymentRecords = ref<PaymentRecord[]>([])
const boms = ref<Bom[]>([])
const workOrders = ref<WorkOrder[]>([])
const materialIssues = ref<MaterialIssue[]>([])
const materialReturns = ref<MaterialReturn[]>([])
const productionCompletions = ref<ProductionCompletion[]>([])
const productionCostReport = ref<ProductionCostReport | null>(null)
const warehouses = ref<Warehouse[]>([])
const transfers = ref<Transfer[]>([])
const stocktakes = ref<Stocktake[]>([])
const customers = ref<Customer[]>([])
const salesOrders = ref<SalesOrder[]>([])
const shipments = ref<Shipment[]>([])
const salesReturns = ref<SalesReturn[]>([])
const selectedWarehouseId = ref(0)
const roles = ref<Role[]>([])
const permissions = ref<Permission[]>([])
const users = ref<User[]>([])
const roleDrafts = ref<Record<number, string[]>>({})
const rolePermissionDrafts = ref<Record<string, string[]>>({})
const roleLabelDrafts = ref<Record<string, string>>({})
const resetPasswords = ref<Record<number, string>>({})
const materialForm = ref({ sku: '', name: '', unit: '件' })
const supplierForm = ref({ name: '' })
const receiptForm = ref({ supplier_id: 0, warehouse_id: 1, purchase_order_id: null as number | null,
  reference: '', lines: [{ material_id: 0, quantity: '1' }] })
const purchaseForm = ref({ supplier_id: 0, reference: '',
  lines: [{ material_id: 0, quantity: '1', unit_price: '0' }] })
const purchaseReturnForm = ref({ receipt_id: 0, reason: '',
  lines: [] as { receipt_line_id: number; quantity: string }[] })
const paymentForm = ref({ kind: 'receivable' as 'receivable' | 'payable', order_id: 0,
  action: 'settlement' as 'settlement' | 'refund', amount: '', reference: '', note: '' })
const reversalReasons = ref<Record<number, string>>({})
const bomForm = ref({ product_material_id: 0, base_quantity: '1', note: '',
  lines: [{ component_material_id: 0, quantity: '1' }] })
const workOrderForm = ref({ bom_id: 0, warehouse_id: 1, target_quantity: '1', reference: '', note: '' })
const materialIssueForm = ref({ work_order_id: 0, warehouse_id: 1, reference: '',
  lines: [] as { work_order_line_id: number; quantity: string }[] })
const materialReturnForm = ref({ material_issue_id: 0, reason: '',
  lines: [] as { material_issue_line_id: number; quantity: string }[] })
const completionForm = ref({ work_order_id: 0, reported_quantity: '1', reference: '' })
const inspectionDrafts = ref<Record<number, { accepted_quantity: string; qc_note: string }>>({})
const completionReversalReasons = ref<Record<number, string>>({})
const materialValuationForm = ref({ material_issue_line_id: 0, unit_cost: '0', reference: '', note: '' })
const productionChargeForm = ref({ work_order_id: 0, kind: 'labor' as 'labor' | 'overhead', amount: '', reference: '', note: '' })
const costReversalReasons = ref<Record<number, string>>({})
const warehouseForm = ref({ code: '', name: '' })
const transferForm = ref({ from_warehouse_id: 1, to_warehouse_id: 0, reference: '', lines: [{ material_id: 0, quantity: '1' }] })
const transferReversalReasons = ref<Record<number, string>>({})
const salesReturnReversalReasons = ref<Record<number, string>>({})
const purchaseReturnReversalReasons = ref<Record<number, string>>({})
const stocktakeForm = ref({ warehouse_id: 1, reference: '', lines: [{ material_id: 0, counted_quantity: '0' }] })
const stocktakeReversalReasons = ref<Record<number, string>>({})
const customerForm = ref({ name: '' })
const salesForm = ref({ customer_id: 0, reference: '',
  lines: [{ material_id: 0, quantity: '1', unit_price: '0' }] })
const shipmentForm = ref({ sales_order_id: 0, warehouse_id: 1, reference: '',
  lines: [{ material_id: 0, quantity: '1' }] })
const salesReturnForm = ref({ shipment_id: 0, warehouse_id: 1, reason: '',
  lines: [] as { shipment_line_id: number; quantity: string }[] })
const newUser = ref({ username: '', password: '', roles: ['viewer'] as string[] })
const newRole = ref({ code: '', label: '', permissions: ['inventory.view'] as string[] })
const passwordChange = ref({ current_password: '', new_password: '' })
const server = ref<ServerProfile | null>(null)
const candidate = ref<ConnectionCandidate | null>(null)
const recentServers = ref<ServerProfile[]>([])
const discoveries = ref<DiscoveryResult[]>([])
const scanSeconds = ref(0)
const scanning = ref(false)
const manualForm = ref({ address: '', port: 8000 })
const hostForm = ref({ name: '我的 Nexora ERP', dataDir: '', port: 8000,
  username: 'admin', password: '', confirm: '' })
const trustChecked = ref(false)
const host = ref<HostStatus>({ configured: false, running: false, systemManaged: false,
  migrationNeeded: false, fingerprint: null })
const connectionLost = ref(false)
let scanTimer: ReturnType<typeof setInterval> | null = null
let healthTimer: ReturnType<typeof setInterval> | null = null
let checkingHealth = false
let unsubscribeDiscovery: (() => void) | null = null

const can = (permission: string): boolean => user.value?.permissions.includes(permission) ?? false
// 导航权限仍按原规则计算；图标与文字绑定，避免图标单独承载含义。
const visibleTabs = computed(() => [
  ...(can('inventory.view') ? [{ key: 'stock' as const, label: '库存总览', icon: IconStackLine }, { key: 'catalog' as const, label: '基础资料', icon: IconArchiveLine }, { key: 'purchase' as const, label: '采购订单', icon: IconFileList3Line }, { key: 'receipts' as const, label: '采购入库', icon: IconFileList3Line }, { key: 'purchaseReturns' as const, label: '采购退货', icon: IconHistoryLine }, { key: 'transfers' as const, label: '仓库调拨', icon: IconStackLine }, { key: 'stocktakes' as const, label: '库存盘点', icon: IconFileList3Line }] : []),
  ...(can('sales.view') ? [{ key: 'sales' as const, label: '销售订单', icon: IconFileList3Line }, { key: 'shipments' as const, label: '销售出库', icon: IconArchiveLine }, { key: 'salesReturns' as const, label: '销售退货', icon: IconHistoryLine }] : []),
  ...(can('finance.view') ? [{ key: 'finance' as const, label: '应收应付', icon: IconFileList3Line }] : []),
  ...(can('production.view') ? [{ key: 'boms' as const, label: '生产 BOM', icon: IconStackLine }, { key: 'workOrders' as const, label: '生产工单', icon: IconFileList3Line }, { key: 'materialIssues' as const, label: '生产领料', icon: IconArchiveLine }, { key: 'materialReturns' as const, label: '生产退料', icon: IconHistoryLine }, { key: 'productionCompletions' as const, label: '完工与质检', icon: IconFileList3Line }] : []),
  ...(can('production_cost.view') ? [{ key: 'productionCosts' as const, label: '生产成本', icon: IconFileList3Line }] : []),
  ...(can('users.manage') ? [{ key: 'users' as const, label: '用户权限', icon: IconTeamLine }] : []),
  { key: 'settings' as const, label: '连接与服务', icon: IconSettings3Line }
])
const selectedSalesReturnShipment = computed(() => shipments.value.find(
  item => item.id === salesReturnForm.value.shipment_id))
const selectedPurchaseReturnReceipt = computed(() => receipts.value.find(
  item => item.id === purchaseReturnForm.value.receipt_id))
const selectedIssueOrder = computed(() => workOrders.value.find(
  item => item.id === materialIssueForm.value.work_order_id))
const selectedReturnIssue = computed(() => materialIssues.value.find(
  item => item.id === materialReturnForm.value.material_issue_id))
const selectedCompletionOrder = computed(() => workOrders.value.find(
  item => item.id === completionForm.value.work_order_id))

function displayError(cause: unknown): string {
  const message = cause instanceof Error ? cause.message : '操作失败'
  return message.replace(/^Error invoking remote method '[^']+': Error: /, '')
}

function localTime(value: string): string {
  // SQLite 的 CURRENT_TIMESTAMP 是 UTC，展示时换算成用户设备的本地时区。
  const date = new Date(value.replace(' ', 'T') + 'Z')
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function movementSource(item: Movement): string {
  // 所有库存变动都显示原始业务单据，便于从数量追溯到责任操作。
  if (item.receipt_id !== null) return `入库单 #${item.receipt_id}`
  if (item.transfer_id !== null) return `调拨单 #${item.transfer_id}`
  if (item.transfer_reversal_id !== null) return `调拨冲销单 #${item.transfer_reversal_id}`
  if (item.stocktake_id !== null) return `盘点单 #${item.stocktake_id}`
  if (item.stocktake_reversal_id !== null) return `盘点冲销单 #${item.stocktake_reversal_id}`
  if (item.shipment_id !== null) return `出库单 #${item.shipment_id}`
  if (item.sales_return_id !== null) return `销售退货单 #${item.sales_return_id}`
  if (item.sales_return_reversal_id !== null) return `销售退货冲销单 #${item.sales_return_reversal_id}`
  if (item.purchase_return_id !== null) return `采购退货单 #${item.purchase_return_id}`
  if (item.purchase_return_reversal_id !== null) return `采购退货冲销单 #${item.purchase_return_reversal_id}`
  if (item.material_issue_id !== null) return `生产领料单 #${item.material_issue_id}`
  if (item.material_return_id !== null) return `生产退料单 #${item.material_return_id}`
  if (item.production_completion_id !== null) return `生产完工单 #${item.production_completion_id}`
  if (item.production_completion_reversal_id !== null) return `生产完工冲销单 #${item.production_completion_reversal_id}`
  return `流水 #${item.id}`
}

function financialSource(item: FinancialEntry): string {
  const names = { shipment: '销售出库', sales_return: '销售退货', sales_return_reversal: '销售退货冲销', receipt: '采购入库', purchase_return: '采购退货', purchase_return_reversal: '采购退货冲销' }
  return `${names[item.source_type]} #${item.source_id}`
}

async function checkConnection(): Promise<void> {
  if (!window.nexora) {
    screen.value = 'offline'
    error.value = '请在 Electron 桌面应用中打开此页面。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const state = await window.nexora.startup()
    connectionLost.value = false
    if (state.status === 'connected') {
      server.value = state.server
      screen.value = 'login'
    } else if (state.status === 'needs_setup') {
      server.value = state.server
      screen.value = 'setup'
    } else if (state.status === 'offline') {
      server.value = state.server ?? null
      screen.value = 'offline'
      error.value = state.message
    } else {
      screen.value = 'welcome'
    }
    recentServers.value = await window.nexora.recentServers()
    host.value = await window.nexora.hostStatus()
  } catch (cause) {
    screen.value = 'offline'
    error.value = displayError(cause)
  } finally {
    busy.value = false
  }
}

function clearMessage(): void { error.value = ''; notice.value = '' }

async function go(screenName: Screen): Promise<void> {
  clearMessage()
  if (screen.value === 'scan') await stopScan()
  screen.value = screenName
}

async function switchServer(): Promise<void> {
  if (!window.nexora) return
  if (user.value) {
    try { await window.nexora.callApi('logout', undefined) } catch { /* 网络中断时仍清理本地连接。 */ }
  }
  user.value = null
  connectionLost.value = false
  server.value = null
  // 仓库编号只在当前服务端有效，切换实例时重置筛选，避免请求另一实例不存在的仓库。
  selectedWarehouseId.value = 0
  await window.nexora.disconnect()
  recentServers.value = await window.nexora.recentServers()
  await go('welcome')
}

async function connectManual(): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  clearMessage()
  try {
    candidate.value = await window.nexora.prepareConnection(manualForm.value.address, Number(manualForm.value.port))
    trustChecked.value = false
    if (candidate.value.trusted) {
      server.value = await window.nexora.approveConnection(candidate.value.id, candidate.value.fingerprint)
      await go('ready')
    } else await go('trust')
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function connectSaved(profile: ServerProfile): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  clearMessage()
  try {
    server.value = await window.nexora.activateSaved(profile.id)
    await go('ready')
  } catch (cause) {
    error.value = displayError(cause)
    manualForm.value = { address: profile.host, port: profile.port }
    screen.value = 'manual'
  } finally { busy.value = false }
}

async function approveTrust(): Promise<void> {
  if (!window.nexora || !candidate.value || !trustChecked.value) return
  busy.value = true
  try {
    server.value = await window.nexora.approveConnection(candidate.value.id, candidate.value.fingerprint)
    recentServers.value = await window.nexora.recentServers()
    await go('ready')
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function startScan(): Promise<void> {
  if (!window.nexora) return
  await go('scan')
  scanSeconds.value = 0
  discoveries.value = []
  scanning.value = true
  unsubscribeDiscovery?.()
  unsubscribeDiscovery = window.nexora.onDiscovery((results) => { discoveries.value = results })
  try {
    await window.nexora.startDiscovery()
    scanTimer = setInterval(() => { scanSeconds.value += 1 }, 1000)
  } catch (cause) {
    scanning.value = false
    error.value = displayError(cause)
  }
}

async function stopScan(): Promise<void> {
  if (scanTimer) clearInterval(scanTimer)
  scanTimer = null
  if (scanning.value) await window.nexora?.stopDiscovery()
  scanning.value = false
  unsubscribeDiscovery?.()
  unsubscribeDiscovery = null
}

async function showResults(): Promise<void> {
  await stopScan()
  screen.value = 'results'
}

async function pickDiscovered(item: DiscoveryResult): Promise<void> {
  manualForm.value = { address: item.host, port: item.port }
  await connectManual()
}

async function chooseDataDir(): Promise<void> {
  if (!window.nexora) return
  const path = await window.nexora.chooseDataDir()
  if (path) hostForm.value.dataDir = path
}

async function createLocalHost(): Promise<void> {
  if (!window.nexora || busy.value) return
  if (hostForm.value.password !== hostForm.value.confirm) {
    error.value = '两次输入的管理员密码不一致'
    return
  }
  busy.value = true
  clearMessage()
  try {
    server.value = await window.nexora.createHost({
      name: hostForm.value.name, dataDir: hostForm.value.dataDir, port: Number(hostForm.value.port),
      username: hostForm.value.username, password: hostForm.value.password
    })
    hostForm.value.password = ''
    hostForm.value.confirm = ''
    recentServers.value = await window.nexora.recentServers()
    host.value = await window.nexora.hostStatus()
    await go('ready')
  } catch (cause) {
    const failure = displayError(cause)
    await checkConnection()
    error.value = failure
  }
  finally { busy.value = false }
}

async function stopLocalHost(): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  clearMessage()
  try {
    await window.nexora.stopHost()
    host.value = await window.nexora.hostStatus()
    notice.value = '本机服务已停止。'
    if (server.value?.isLocal) {
      // 服务已退出，主进程也已清除令牌，此时无需再向停掉的服务发送登出请求。
      user.value = null
      await switchServer()
      notice.value = '本机服务已停止。'
    }
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function restartLocalHost(): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  clearMessage()
  try {
    server.value = await window.nexora.restartHost()
    host.value = await window.nexora.hostStatus()
    if (screen.value === 'offline' || screen.value === 'create') await go('ready')
    notice.value = '本机服务已启动。'
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function upgradeLocalHost(): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  clearMessage()
  try {
    // 升级命令会在停止服务后创建成组备份，并保留原实例的数据目录与证书。
    server.value = await window.nexora.upgradeHost()
    host.value = await window.nexora.hostStatus()
    notice.value = '系统服务已升级，升级前备份保存在主机系统数据目录。'
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function authenticate(): Promise<void> {
  if (!window.nexora || busy.value) return
  busy.value = true
  error.value = ''
  try {
    if (screen.value === 'setup') {
      await window.nexora.finishHostSetup(username.value, password.value)
      screen.value = 'login'
      notice.value = '管理员已创建，请登录。'
      password.value = ''
      return
    }
    user.value = await window.nexora.callApi('login', { username: username.value, password: password.value })
    password.value = ''
    screen.value = 'app'
    await refreshData()
    activeTab.value = visibleTabs.value[0]?.key ?? 'stock'
  } catch (cause) {
    error.value = displayError(cause)
  } finally {
    busy.value = false
  }
}

async function refreshData(): Promise<void> {
  if (!window.nexora || !user.value) return
  // 每次写操作后重新读取服务端权限；角色变化立即反映到当前页面。
  user.value = await window.nexora.callApi('me', undefined)
  if (!visibleTabs.value.some((item) => item.key === activeTab.value)) activeTab.value = visibleTabs.value[0]?.key ?? 'settings'
  // 页面只显示当前角色可访问的入口；数据访问仍以服务端授权为准。
  if (can('inventory.view')) {
    [materials.value, suppliers.value, stock.value, receipts.value, movements.value, warehouses.value, transfers.value, purchaseOrders.value, stocktakes.value, purchaseReturns.value] = await Promise.all([
      window.nexora.callApi('materials', undefined),
      window.nexora.callApi('suppliers', undefined),
      window.nexora.callApi('stock', selectedWarehouseId.value ? { warehouseId: selectedWarehouseId.value } : undefined),
      window.nexora.callApi('receipts', undefined),
      window.nexora.callApi('movements', undefined),
      window.nexora.callApi('warehouses', undefined),
      window.nexora.callApi('transfers', undefined),
      window.nexora.callApi('purchaseOrders', undefined),
      window.nexora.callApi('stocktakes', undefined),
      window.nexora.callApi('purchaseReturns', undefined)
    ])
  }
  if (can('sales.view')) {
    [customers.value, salesOrders.value, shipments.value, salesReturns.value] = await Promise.all([
      window.nexora.callApi('customers', undefined),
      window.nexora.callApi('salesOrders', undefined),
      window.nexora.callApi('shipments', undefined),
      window.nexora.callApi('salesReturns', undefined)
    ])
  }
  if (can('finance.view')) {
    // 单次服务端快照避免并发收付款时来源、余额和记录短暂不一致。
    const overview = await window.nexora.callApi('financeOverview', undefined)
    receivablesPayables.value = overview.report
    financeAccounts.value = overview.accounts
    paymentRecords.value = overview.payments
  } else {
    receivablesPayables.value = null
    financeAccounts.value = []
    paymentRecords.value = []
  }
  if (can('production.view')) {
    [boms.value, workOrders.value, materialIssues.value, materialReturns.value, productionCompletions.value] = await Promise.all([
      window.nexora.callApi('boms', undefined), window.nexora.callApi('workOrders', undefined),
      window.nexora.callApi('materialIssues', undefined), window.nexora.callApi('materialReturns', undefined),
      window.nexora.callApi('productionCompletions', undefined)
    ])
    // 刷新列表时保留尚未提交的质检输入，避免其他业务操作意外清空填写内容。
    const previousInspections = inspectionDrafts.value
    inspectionDrafts.value = Object.fromEntries(productionCompletions.value.filter(item => item.status === 'draft')
      .map(item => [item.id, previousInspections[item.id] ?? { accepted_quantity: item.reported_quantity, qc_note: '' }]))
  } else {
    boms.value = []
    workOrders.value = []
    materialIssues.value = []
    materialReturns.value = []
    productionCompletions.value = []
    inspectionDrafts.value = {}
  }
  productionCostReport.value = can('production_cost.view')
    ? await window.nexora.callApi('productionCosts', undefined) : null
  if (can('users.manage')) {
    [permissions.value, roles.value, users.value] = await Promise.all([
      window.nexora.callApi('permissions', undefined), window.nexora.callApi('roles', undefined),
      window.nexora.callApi('users', undefined)
    ])
    roleDrafts.value = Object.fromEntries(users.value.map((entry) => [entry.id, [...entry.roles]]))
    rolePermissionDrafts.value = Object.fromEntries(roles.value.map((entry) => [entry.code, [...entry.permissions]]))
    roleLabelDrafts.value = Object.fromEntries(roles.value.map((entry) => [entry.code, entry.label]))
  } else {
    permissions.value = []
    roles.value = []
    users.value = []
  }
}

async function perform(action: () => Promise<unknown>, success: string): Promise<void> {
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

function addLine(): void {
  receiptForm.value.lines.push({ material_id: 0, quantity: '1' })
}

function removeLine(index: number): void {
  if (receiptForm.value.lines.length > 1) receiptForm.value.lines.splice(index, 1)
}

async function createMaterial(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    // Vue 的响应式代理不能通过 Electron IPC，发送前只取普通字段。
    await window.nexora!.callApi('createMaterial', { ...materialForm.value })
    materialForm.value = { sku: '', name: '', unit: '件' }
  }, '物料已保存。')
}

async function createSupplier(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createSupplier', { name: supplierForm.value.name })
    supplierForm.value = { name: '' }
  }, '供应商已保存。')
}

async function createReceipt(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createReceipt', {
      supplier_id: receiptForm.value.supplier_id,
      warehouse_id: receiptForm.value.warehouse_id,
      purchase_order_id: receiptForm.value.purchase_order_id,
      reference: receiptForm.value.reference,
      lines: receiptForm.value.lines.map((line) => ({ material_id: line.material_id, quantity: line.quantity }))
    })
    receiptForm.value = { supplier_id: 0, warehouse_id: receiptForm.value.warehouse_id,
      purchase_order_id: null, reference: '', lines: [{ material_id: 0, quantity: '1' }] }
  }, '入库单草稿已创建，等待仓库员确认。')
}

function chooseReceiptOrder(): void {
  // 关联采购订单后使用订单供应商和待入库明细，数量仍允许操作员按本批次调整。
  const order = purchaseOrders.value.find(item => item.id === receiptForm.value.purchase_order_id)
  if (!order) {
    receiptForm.value.supplier_id = 0
    receiptForm.value.lines = [{ material_id: 0, quantity: '1' }]
    return
  }
  receiptForm.value.supplier_id = order.supplier_id
  receiptForm.value.lines = order.lines.filter(line => Number(line.remaining_quantity) > 0)
    .map(line => ({ material_id: line.material_id, quantity: line.remaining_quantity }))
}

async function createPurchaseOrder(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createPurchaseOrder', {
      supplier_id: purchaseForm.value.supplier_id, reference: purchaseForm.value.reference,
      lines: purchaseForm.value.lines.map(line => ({ material_id: line.material_id,
        quantity: line.quantity, unit_price: line.unit_price }))
    })
    purchaseForm.value = { supplier_id: 0, reference: '',
      lines: [{ material_id: 0, quantity: '1', unit_price: '0' }] }
  }, '采购订单草稿已创建。')
}

async function confirmPurchaseOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('confirmPurchaseOrder', { orderId }), `采购订单 #${orderId} 已确认。`)
}

async function cancelPurchaseOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelPurchaseOrder', { orderId }), `采购订单 #${orderId} 已取消。`)
}

async function postReceipt(receiptId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postReceipt', { receiptId }), `入库单 #${receiptId} 已确认，库存流水已生成。`)
}

function choosePurchaseReturnReceipt(): void {
  const receipt = selectedPurchaseReturnReceipt.value
  // 原入库行决定退货上限和出库仓库，页面只预填当前尚可退的数量。
  purchaseReturnForm.value.lines = receipt?.lines.filter(line => Number(line.returnable_quantity) > 0)
    .map(line => ({ receipt_line_id: line.id, quantity: line.returnable_quantity })) ?? []
}

async function createPurchaseReturn(): Promise<void> {
  if (!window.nexora || !purchaseReturnForm.value.lines.length) return
  await perform(async () => {
    await window.nexora!.callApi('createPurchaseReturn', {
      receipt_id: purchaseReturnForm.value.receipt_id,
      reason: purchaseReturnForm.value.reason,
      lines: purchaseReturnForm.value.lines.map(line => ({ ...line }))
    })
    purchaseReturnForm.value = { receipt_id: 0, reason: '', lines: [] }
  }, '采购退货草稿已创建。')
}

async function postPurchaseReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postPurchaseReturn', { returnId }),
    `采购退货单 #${returnId} 已确认，原入库仓库库存已扣减。`)
}

async function cancelPurchaseReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelPurchaseReturn', { returnId }),
    `采购退货单 #${returnId} 已取消。`)
}

async function reversePurchaseReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  const reason = purchaseReturnReversalReasons.value[returnId]?.trim() ?? ''
  // 正向补回库存和应付更正均由服务端写事务完成，页面只提交纠错原因。
  await perform(async () => {
    await window.nexora!.callApi('reversePurchaseReturn', { returnId, reason })
    delete purchaseReturnReversalReasons.value[returnId]
  }, `采购退货单 #${returnId} 已冲销，原仓库存与应付已追加更正记录。`)
}

async function createWarehouse(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createWarehouse', { ...warehouseForm.value })
    warehouseForm.value = { code: '', name: '' }
  }, '仓库已创建。')
}

async function createTransfer(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    // 只发送表单字段，避免把 Vue 响应式对象传入进程通信。
    await window.nexora!.callApi('createTransfer', {
      from_warehouse_id: transferForm.value.from_warehouse_id,
      to_warehouse_id: transferForm.value.to_warehouse_id,
      reference: transferForm.value.reference,
      lines: transferForm.value.lines.map(line => ({ material_id: line.material_id, quantity: line.quantity }))
    })
    transferForm.value = { from_warehouse_id: transferForm.value.from_warehouse_id, to_warehouse_id: 0,
      reference: '', lines: [{ material_id: 0, quantity: '1' }] }
  }, '调拨单草稿已创建。')
}

async function postTransfer(transferId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postTransfer', { transferId }), `调拨单 #${transferId} 已确认，双向库存流水已生成。`)
}

async function reverseTransfer(transferId: number): Promise<void> {
  if (!window.nexora) return
  const reason = transferReversalReasons.value[transferId] ?? ''
  await perform(async () => {
    await window.nexora!.callApi('reverseTransfer', { transferId, reason })
    delete transferReversalReasons.value[transferId]
  }, `调拨单 #${transferId} 已冲销，库存已按原路径退回。`)
}

async function createStocktake(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    // 仅传实盘量；账面快照由服务端在事务内生成，防止客户端伪造差异。
    await window.nexora!.callApi('createStocktake', {
      warehouse_id: stocktakeForm.value.warehouse_id,
      reference: stocktakeForm.value.reference,
      lines: stocktakeForm.value.lines.map(line => ({
        material_id: line.material_id, counted_quantity: line.counted_quantity
      }))
    })
    stocktakeForm.value = { warehouse_id: stocktakeForm.value.warehouse_id,
      reference: '', lines: [{ material_id: 0, counted_quantity: '0' }] }
  }, '盘点草稿已创建，请核对账面与实盘数量。')
}

async function postStocktake(stocktakeId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postStocktake', { stocktakeId }),
    `盘点单 #${stocktakeId} 已确认，差异已记入库存流水。`)
}

async function cancelStocktake(stocktakeId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelStocktake', { stocktakeId }),
    `盘点单 #${stocktakeId} 已取消。`)
}

async function reverseStocktake(stocktakeId: number): Promise<void> {
  if (!window.nexora) return
  const reason = stocktakeReversalReasons.value[stocktakeId] ?? ''
  await perform(async () => {
    await window.nexora!.callApi('reverseStocktake', { stocktakeId, reason })
    delete stocktakeReversalReasons.value[stocktakeId]
  }, `盘点单 #${stocktakeId} 已冲销，反向差异已记入库存流水。`)
}

async function createCustomer(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createCustomer', { name: customerForm.value.name })
    customerForm.value = { name: '' }
  }, '客户已创建。')
}

async function createSalesOrder(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    // 销售单价和数量只从表单读取，服务端独立计算订单金额与出库进度。
    await window.nexora!.callApi('createSalesOrder', {
      customer_id: salesForm.value.customer_id,
      reference: salesForm.value.reference,
      lines: salesForm.value.lines.map(line => ({ material_id: line.material_id,
        quantity: line.quantity, unit_price: line.unit_price }))
    })
    salesForm.value = { customer_id: 0, reference: '',
      lines: [{ material_id: 0, quantity: '1', unit_price: '0' }] }
  }, '销售订单草稿已创建。')
}

async function confirmSalesOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('confirmSalesOrder', { orderId }),
    `销售订单 #${orderId} 已确认，可创建出库单。`)
}

async function cancelSalesOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelSalesOrder', { orderId }),
    `销售订单 #${orderId} 已取消。`)
}

function chooseShipmentOrder(): void {
  const order = salesOrders.value.find(item => item.id === shipmentForm.value.sales_order_id)
  // 订单选择后仅填入未出库明细，最终数量仍由操作人填写并由服务端复核。
  shipmentForm.value.lines = order?.lines.filter(line => Number(line.remaining_quantity) > 0)
    .map(line => ({ material_id: line.material_id, quantity: line.remaining_quantity }))
    ?? [{ material_id: 0, quantity: '1' }]
}

async function createShipment(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createShipment', {
      sales_order_id: shipmentForm.value.sales_order_id,
      warehouse_id: shipmentForm.value.warehouse_id,
      reference: shipmentForm.value.reference,
      lines: shipmentForm.value.lines.map(line => ({ material_id: line.material_id, quantity: line.quantity }))
    })
    shipmentForm.value = { sales_order_id: 0, warehouse_id: shipmentForm.value.warehouse_id,
      reference: '', lines: [{ material_id: 0, quantity: '1' }] }
  }, '出库单草稿已创建。')
}

async function postShipment(shipmentId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postShipment', { shipmentId }),
    `出库单 #${shipmentId} 已确认，仓库库存与订单进度已更新。`)
}

async function cancelShipment(shipmentId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelShipment', { shipmentId }),
    `出库单 #${shipmentId} 已取消。`)
}

function chooseSalesReturnShipment(): void {
  const shipment = shipments.value.find(item => item.id === salesReturnForm.value.shipment_id)
  // 只预填原出库中仍可退的明细；创建和确认时服务端会分别复核累计数量。
  salesReturnForm.value.lines = shipment?.lines.filter(line => Number(line.returnable_quantity) > 0)
    .map(line => ({ shipment_line_id: line.id, quantity: line.returnable_quantity })) ?? []
  if (shipment) salesReturnForm.value.warehouse_id = shipment.warehouse_id
}

async function createSalesReturn(): Promise<void> {
  if (!window.nexora || !salesReturnForm.value.lines.length) return
  await perform(async () => {
    await window.nexora!.callApi('createSalesReturn', {
      shipment_id: salesReturnForm.value.shipment_id,
      warehouse_id: salesReturnForm.value.warehouse_id,
      reason: salesReturnForm.value.reason,
      lines: salesReturnForm.value.lines.map(line => ({ ...line }))
    })
    salesReturnForm.value = { shipment_id: 0, warehouse_id: salesReturnForm.value.warehouse_id,
      reason: '', lines: [] }
  }, '销售退货草稿已创建。')
}

async function postSalesReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postSalesReturn', { returnId }),
    `销售退货单 #${returnId} 已确认，退回库存已入仓。`)
}

async function cancelSalesReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelSalesReturn', { returnId }),
    `销售退货单 #${returnId} 已取消。`)
}

async function reverseSalesReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  const reason = salesReturnReversalReasons.value[returnId]?.trim() ?? ''
  // 页面只收集原因；库存不足和重复冲销由服务端在写事务内拦截。
  await perform(async () => {
    await window.nexora!.callApi('reverseSalesReturn', { returnId, reason })
    delete salesReturnReversalReasons.value[returnId]
  }, `销售退货单 #${returnId} 已冲销，库存与应收已追加更正记录。`)
}

async function createPaymentRecord(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createPaymentRecord', { ...paymentForm.value })
    // 保存后清空金额和流水号，避免重复点击复用同一银行凭据。
    paymentForm.value.amount = ''
    paymentForm.value.reference = ''
    paymentForm.value.note = ''
  }, '收付款记录已保存，订单余额已更新。')
}

async function reversePaymentRecord(paymentId: number): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('reversePaymentRecord', {
      paymentId, reason: reversalReasons.value[paymentId] ?? ''
    })
    delete reversalReasons.value[paymentId]
  }, `收付款记录 #${paymentId} 已冲销，原记录已保留。`)
}

function paymentActionLabel(item: PaymentRecord): string {
  if (item.action === 'reversal') return '冲销'
  if (item.kind === 'receivable') return item.action === 'settlement' ? '客户收款' : '客户退款'
  return item.action === 'settlement' ? '供应商付款' : '供应商退款'
}

async function createBom(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createBom', {
      product_material_id: bomForm.value.product_material_id,
      base_quantity: bomForm.value.base_quantity,
      note: bomForm.value.note,
      lines: bomForm.value.lines.map(line => ({ ...line }))
    })
    bomForm.value = { product_material_id: 0, base_quantity: '1', note: '',
      lines: [{ component_material_id: 0, quantity: '1' }] }
  }, 'BOM 草稿已创建。')
}

async function activateBom(bomId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('activateBom', { bomId }), `BOM #${bomId} 已启用。`)
}

async function retireBom(bomId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('retireBom', { bomId }), `BOM #${bomId} 已停用。`)
}

async function cancelBom(bomId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelBom', { bomId }), `BOM #${bomId} 草稿已取消。`)
}

async function createWorkOrder(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createWorkOrder', { ...workOrderForm.value })
    // 成功后重置选择，避免误把下一张工单挂在旧版 BOM 上。
    workOrderForm.value = { bom_id: 0, warehouse_id: 1, target_quantity: '1', reference: '', note: '' }
  }, '生产工单草稿已创建，组件需求已固定。')
}

async function releaseWorkOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('releaseWorkOrder', { orderId }), `生产工单 #${orderId} 已下达。`)
}

async function cancelWorkOrder(orderId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelWorkOrder', { orderId }), `生产工单 #${orderId} 已取消。`)
}

function selectIssueOrder(orderId: number): void {
  const order = workOrders.value.find(item => item.id === orderId)
  materialIssueForm.value = { work_order_id: orderId, warehouse_id: 1, reference: '',
    // 只预填仍需领用的组件，计划员可再调整本次分批数量。
    lines: order?.lines.filter(line => Number(line.remaining_quantity) > 0).map(line => ({
      work_order_line_id: line.id, quantity: line.remaining_quantity
    })) ?? [] }
  activeTab.value = 'materialIssues'
}

async function createMaterialIssue(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createMaterialIssue', {
      ...materialIssueForm.value, lines: materialIssueForm.value.lines.map(line => ({ ...line }))
    })
    materialIssueForm.value = { work_order_id: 0, warehouse_id: 1, reference: '', lines: [] }
  }, '生产领料草稿已创建，确认前不会扣减库存。')
}

async function postMaterialIssue(issueId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postMaterialIssue', { issueId }),
    `生产领料单 #${issueId} 已确认，源仓库存已扣减。`)
}

async function cancelMaterialIssue(issueId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelMaterialIssue', { issueId }),
    `生产领料单 #${issueId} 草稿已取消。`)
}

function selectReturnIssue(issueId: number): void {
  const issue = materialIssues.value.find(item => item.id === issueId)
  materialReturnForm.value = { material_issue_id: issueId, reason: '',
    // 仅预填仍可退的领料明细；用户可按实际退回数量修改或移除。
    lines: issue?.lines.filter(line => Number(line.returnable_quantity) > 0).map(line => ({
      material_issue_line_id: line.id, quantity: line.returnable_quantity
    })) ?? [] }
  activeTab.value = 'materialReturns'
}

async function createMaterialReturn(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createMaterialReturn', {
      ...materialReturnForm.value, lines: materialReturnForm.value.lines.map(line => ({ ...line }))
    })
    materialReturnForm.value = { material_issue_id: 0, reason: '', lines: [] }
  }, '生产退料草稿已创建，确认前不会增加库存。')
}

async function postMaterialReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postMaterialReturn', { returnId }),
    `生产退料单 #${returnId} 已确认，组件已回到原领料仓库。`)
}

async function cancelMaterialReturn(returnId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelMaterialReturn', { returnId }),
    `生产退料单 #${returnId} 草稿已取消。`)
}

function selectCompletionOrder(orderId: number): void {
  const order = workOrders.value.find(item => item.id === orderId)
  completionForm.value = { work_order_id: orderId,
    reported_quantity: order?.remaining_output_quantity ?? '1', reference: '' }
  activeTab.value = 'productionCompletions'
}

async function createProductionCompletion(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createProductionCompletion', { ...completionForm.value })
    completionForm.value = { work_order_id: 0, reported_quantity: '1', reference: '' }
  }, '完工报工草稿已创建，质检并确认前不会增加成品库存。')
}

async function inspectProductionCompletion(completionId: number): Promise<void> {
  if (!window.nexora) return
  const draft = inspectionDrafts.value[completionId]
  if (!draft) return
  await perform(() => window.nexora!.callApi('inspectProductionCompletion', {
    completionId, accepted_quantity: draft.accepted_quantity, qc_note: draft.qc_note
  }), `完工单 #${completionId} 的质检结果已记录。`)
}

async function postProductionCompletion(completionId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('postProductionCompletion', { completionId }),
    `完工单 #${completionId} 已确认，合格成品已入目标仓库。`)
}

async function cancelProductionCompletion(completionId: number): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('cancelProductionCompletion', { completionId }),
    `完工单 #${completionId} 已取消。`)
}

async function reverseProductionCompletion(completionId: number): Promise<void> {
  const reason = completionReversalReasons.value[completionId]?.trim()
  if (!reason) return
  await perform(() => window.nexora!.callApi('reverseProductionCompletion', { completionId, reason }),
    `完工单 #${completionId} 已冲销，原记录和冲销凭据均已保留。`)
  delete completionReversalReasons.value[completionId]
}

async function recordMaterialValuation(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('recordMaterialValuation', { ...materialValuationForm.value })
    materialValuationForm.value = { material_issue_line_id: 0, unit_cost: '0', reference: '', note: '' }
  }, '领料明细核定单价已记录。')
}

async function recordProductionCharge(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('recordProductionCharge', { ...productionChargeForm.value })
    productionChargeForm.value = { work_order_id: 0, kind: 'labor', amount: '', reference: '', note: '' }
  }, '生产费用已归集到工单。')
}

async function reverseProductionCost(entryId: number): Promise<void> {
  if (!window.nexora) return
  const reason = costReversalReasons.value[entryId]?.trim()
  if (!reason) return
  await perform(async () => {
    await window.nexora!.callApi('reverseProductionCost', { entryId, reason })
    delete costReversalReasons.value[entryId]
  }, `成本记录 #${entryId} 已冲销，原记录仍可查询。`)
}

async function createUser(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createUser', {
      username: newUser.value.username, password: newUser.value.password, roles: [...newUser.value.roles]
    })
    newUser.value = { username: '', password: '', roles: ['viewer'] }
  }, '用户已创建。')
}

async function saveRoles(userId: number): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('setUserRoles', { userId, roles: [...(roleDrafts.value[userId] ?? [])] })
    if (user.value?.id === userId) user.value = await window.nexora!.callApi('me', undefined)
  }, '角色已更新。')
}

async function createRole(): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('createRole', { code: newRole.value.code, label: newRole.value.label,
      permissions: [...newRole.value.permissions] })
    newRole.value = { code: '', label: '', permissions: ['inventory.view'] }
  }, '自定义角色已创建。')
}

async function saveRole(code: string): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('updateRole', { code, label: roleLabelDrafts.value[code],
    permissions: [...(rolePermissionDrafts.value[code] ?? [])] }), '角色权限已更新。')
}

async function setUserStatus(entry: User): Promise<void> {
  if (!window.nexora) return
  await perform(() => window.nexora!.callApi('setUserStatus', { userId: entry.id,
    is_active: !entry.is_active }), entry.is_active ? '账号已停用，原有登录已失效。' : '账号已启用。')
}

async function resetUserPassword(userId: number): Promise<void> {
  if (!window.nexora) return
  await perform(async () => {
    await window.nexora!.callApi('resetUserPassword', { userId, password: resetPasswords.value[userId] })
    resetPasswords.value[userId] = ''
  }, '密码已重置，用户需要重新登录。')
}

async function changeOwnPassword(): Promise<void> {
  if (!window.nexora || busy.value) return
  if (connectionLost.value) { error.value = '服务端连接已中断，恢复后再修改密码。'; return }
  busy.value = true
  error.value = ''
  try {
    await window.nexora.callApi('changePassword', { ...passwordChange.value })
    passwordChange.value = { current_password: '', new_password: '' }
    user.value = null
    screen.value = 'login'
    notice.value = '密码已修改，请使用新密码重新登录。'
  } catch (cause) { error.value = displayError(cause) }
  finally { busy.value = false }
}

async function logout(): Promise<void> {
  if (!window.nexora) return
  try { await window.nexora.callApi('logout', undefined) } catch { /* 本地界面仍退出，重连后需要再次登录。 */ }
  user.value = null
  screen.value = 'login'
  notice.value = ''
  error.value = ''
}

async function monitorConnection(): Promise<void> {
  if (!window.nexora || checkingHealth || !['app', 'login', 'setup', 'ready'].includes(screen.value)) return
  checkingHealth = true
  try {
    const health = await window.nexora.getBackendHealth()
    if (!health.connected) {
      connectionLost.value = true
      return
    }
    if (!connectionLost.value) return
    // TLS 请求仍使用固定证书；恢复后从服务端重读，避免展示断线期间的旧库存。
    connectionLost.value = false
    if (screen.value === 'app') {
      try { await refreshData() }
      catch {
        user.value = null
        screen.value = 'login'
        notice.value = '连接已恢复，请重新登录后查看最新数据。'
        return
      }
    }
    notice.value = '服务端连接已恢复，数据已更新。'
  } catch { connectionLost.value = true }
  finally { checkingHealth = false }
}

onMounted(async () => {
  if (window.nexora) version.value = await window.nexora.getVersion().catch(() => '')
  if (window.nexora) hostForm.value.dataDir = await window.nexora.defaultDataDir().catch(() => '')
  await checkConnection()
  healthTimer = setInterval(() => { void monitorConnection() }, 5000)
})

onUnmounted(() => { void stopScan(); if (healthTimer) clearInterval(healthTimer) })
</script>

<template>
  <!-- 统一设置 Naive UI 中文环境；现有页面可逐步使用组件。 -->
  <NConfigProvider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="naiveThemeOverrides">
  <div v-if="screen !== 'app' && screen !== 'login' && screen !== 'setup'" class="onboarding">
    <header class="onboard-top"><div class="onboard-logo"><span class="onboard-mark"><img :src="nexoraLogo" alt="" /></span><strong>NEXORA <small>ERP</small></strong></div><span class="onboard-top-note">企业运营工作台 <span v-if="version">· v{{ version }}</span></span></header>
    <main class="onboard-main">
      <div class="onboard-hero">
        <p class="onboard-kicker">NEXORA · CONNECT</p>
        <h1>{{ screen === 'welcome' ? '选择你的工作方式' : screen === 'manual' ? '连接现有服务端' : screen === 'scan' ? '正在查找局域网服务端' : screen === 'results' ? '选择服务端' : screen === 'create' ? '创建本机服务端' : screen === 'trust' ? '核对服务端身份' : screen === 'ready' ? '服务端已就绪' : screen === 'offline' ? '连接暂时中断' : '正在准备工作台' }}</h1>
        <p>{{ screen === 'welcome' ? '连接团队已有的服务端，或者在这台电脑上创建一个。' : screen === 'manual' ? '输入局域网地址，连接团队的 Nexora ERP。' : screen === 'scan' ? '正在发现同一局域网中可用的 Nexora 服务端。' : screen === 'results' ? '以下服务端由当前网络实际发现；选择后仍需核对身份。' : screen === 'create' ? '数据保存在所选目录；安装版由系统服务持续运行。' : screen === 'trust' ? '请与服务端电脑上的指纹逐字核对，再使用账号密码登录。' : screen === 'ready' ? '连接和服务状态已确认，可以进入工作台。' : screen === 'offline' ? '检查网络或本机服务，再试一次。' : '请稍候。' }}</p>
      </div>
      <div v-if="error" class="onboard-alert" role="alert">{{ error }}</div>
      <div v-if="notice" class="onboard-alert success" role="status">{{ notice }}</div>

      <section v-if="screen === 'loading'" class="onboard-panel loading-panel"><div class="scan-orbit"></div><h2>正在检查上次连接…</h2></section>

      <section v-else-if="screen === 'welcome'" class="choice-grid" aria-label="启动方式">
        <!-- 启动方式保留文字说明，Remix Icon 只作为辅助视觉标记。 -->
        <button class="choice-card" type="button" @click="go('manual')"><span class="choice-index">01 / CONNECT</span><span class="choice-symbol"><IconArrowRightUpLine aria-hidden="true" /></span><strong>连接服务端</strong><span>知道地址时直接填写，也可以选择最近使用过的服务端。</span><em>填写连接信息 <span aria-hidden="true">→</span></em></button>
        <button class="choice-card featured" type="button" @click="startScan"><span class="choice-index">02 / DISCOVER</span><span class="choice-symbol radar-symbol"><IconRadarLine aria-hidden="true" /></span><strong>扫描局域网</strong><span>自动发现同一网络中的服务端，再核对身份并连接。</span><em>开始扫描 <span aria-hidden="true">→</span></em></button>
        <button class="choice-card" type="button" @click="go('create')"><span class="choice-index">03 / HOST</span><span class="choice-symbol"><IconServerLine aria-hidden="true" /></span><strong>新建服务端</strong><span>在这台电脑上创建服务端，供团队在局域网中使用。</span><em>开始创建 <span aria-hidden="true">→</span></em></button>
      </section>

      <section v-else-if="screen === 'manual'" class="onboard-columns">
        <form class="onboard-panel onboard-form" @submit.prevent="connectManual"><div class="panel-heading"><span class="panel-icon"><IconArrowRightUpLine aria-hidden="true" /></span><div><h2>服务端地址</h2><p>只支持本机和局域网地址，连接将使用 HTTPS。</p></div></div><label>IP 地址或主机名<input v-model.trim="manualForm.address" required placeholder="例如 192.168.1.100" autocomplete="off" /></label><label>端口<input v-model.number="manualForm.port" type="number" min="1" max="65535" required /></label><div class="onboard-actions"><button class="secondary" type="button" @click="go('welcome')">返回首页</button><button class="primary" type="submit" :disabled="busy">{{ busy ? '正在检查…' : '检查并连接' }}</button></div></form>
        <div class="onboard-panel"><div class="panel-heading"><span class="panel-icon"><IconHistoryLine aria-hidden="true" /></span><div><h2>最近连接</h2><p>仅保存地址和已核对的证书，不保存密码。</p></div></div><div v-if="!recentServers.length" class="onboard-empty">还没有连接记录。可以填写地址，或扫描局域网。</div><button v-for="entry in recentServers" :key="entry.id" class="server-row" type="button" :disabled="busy" @click="connectSaved(entry)"><span><strong>{{ entry.name }}</strong><small>{{ entry.host }}:{{ entry.port }}</small></span><span class="server-row-action">连接 →</span></button></div>
      </section>

      <section v-else-if="screen === 'scan'" class="onboard-panel scan-panel"><div class="scan-visual"><div class="scan-orbit"><span class="scan-core">N</span></div></div><div class="scan-copy"><p class="onboard-kicker">LIVE DISCOVERY</p><h2>已扫描 {{ scanSeconds }} 秒</h2><p>发现 {{ discoveries.length }} 个可用服务端。结果会随着网络变化更新。</p><div class="scan-live"><span class="status-dot"></span>{{ scanning ? '正在发现' : '已暂停' }}</div></div><div class="onboard-actions scan-actions"><button class="secondary" type="button" @click="go('welcome')">返回首页</button><button class="secondary" type="button" @click="showResults">暂停并查看结果</button><button class="primary" type="button" @click="startScan">重新扫描</button></div></section>

      <section v-else-if="screen === 'results'" class="onboard-panel"><div class="panel-heading"><span class="panel-icon"><IconRadarLine aria-hidden="true" /></span><div><h2>发现 {{ discoveries.length }} 个服务端</h2><p>选择在线服务端，下一步核对证书指纹。</p></div></div><div v-if="!discoveries.length" class="onboard-empty">当前没有发现可用服务端。请确认两台电脑在同一局域网，或手动填写地址。</div><button v-for="entry in discoveries" :key="entry.id" class="server-row" type="button" :disabled="!entry.online || busy" @click="pickDiscovered(entry)"><span><strong>{{ entry.name }}</strong><small>{{ entry.host }}:{{ entry.port }} · v{{ entry.version }}</small></span><span :class="entry.online ? 'online' : 'offline'">{{ entry.online ? '在线 · 连接 →' : '离线' }}</span></button><div class="onboard-actions"><button class="secondary" type="button" @click="go('manual')">手动填写</button><button class="primary" type="button" @click="startScan">重新扫描</button></div></section>

      <section v-else-if="screen === 'create'" class="onboard-columns create-columns"><div v-if="host.configured" class="onboard-panel"><div class="panel-heading"><span class="panel-icon"><IconServerLine aria-hidden="true" /></span><div><h2>此电脑已有服务端</h2><p>一个电脑只创建一个本机实例。你可以继续使用已有服务端。</p></div></div><div class="onboard-actions"><button class="secondary" type="button" @click="go('welcome')">返回首页</button><button class="primary" type="button" :disabled="busy" @click="restartLocalHost">{{ host.running ? '连接本机服务' : '启动本机服务' }}</button></div></div><form v-else class="onboard-panel onboard-form" @submit.prevent="createLocalHost"><div class="panel-heading"><span class="panel-icon"><IconAddLine aria-hidden="true" /></span><div><h2>本机服务配置</h2><p>第一版使用 SQLite，每台电脑只创建一个本机实例。</p></div></div><div class="form-grid"><label>实例名称<input v-model.trim="hostForm.name" required maxlength="80" placeholder="例如 总公司 ERP" /></label><label>服务端口<input v-model.number="hostForm.port" type="number" min="1" max="65535" required /></label></div><label>数据目录<div class="path-picker"><input v-model.trim="hostForm.dataDir" required placeholder="选择 SQLite 数据保存位置" /><button class="secondary" type="button" @click="chooseDataDir">选择</button></div></label><div class="form-grid"><label>首位管理员账号<input v-model.trim="hostForm.username" required minlength="3" maxlength="40" autocomplete="username" /></label><span class="form-hint">已有数据库会原样保留；已有管理员请使用原账号登录。</span></div><div class="form-grid"><label>管理员密码<input v-model="hostForm.password" type="password" required minlength="12" maxlength="128" autocomplete="new-password" placeholder="至少 12 位" /></label><label>确认密码<input v-model="hostForm.confirm" type="password" required minlength="12" autocomplete="new-password" /></label></div><div class="onboard-actions"><button class="secondary" type="button" @click="go('welcome')">返回首页</button><button class="primary" type="submit" :disabled="busy">{{ busy ? '正在创建服务端…' : '创建并启动' }}</button></div></form><aside class="onboard-panel setup-summary"><p class="onboard-kicker">DEPLOYMENT SUMMARY</p><h2>这台电脑将成为服务端</h2><dl><div><dt>业务数据库</dt><dd>SQLite</dd></div><div><dt>访问方式</dt><dd>局域网 HTTPS</dd></div><div><dt>后台运行</dt><dd>安装版由系统服务管理</dd></div><div><dt>外部客户端</dt><dd>需核对证书指纹并登录</dd></div></dl><p class="summary-note">服务端数据集中保存在此电脑。客户端断网后不能继续编辑或自动同步。</p></aside></section>

      <section v-else-if="screen === 'trust' && candidate" class="onboard-panel trust-panel"><span class="trust-icon">◇</span><h2>{{ candidate.changed ? '服务端证书已变化' : '首次连接，需要确认身份' }}</h2><p>请到服务端电脑的“服务端已就绪”页面，核对以下完整 SHA-256 指纹。不要只凭本页面显示的名称判断身份。</p><div class="fingerprint">{{ candidate.fingerprint }}</div><p class="muted">{{ candidate.name }} · {{ candidate.host }}:{{ candidate.port }}</p><label class="check trust-check"><input v-model="trustChecked" type="checkbox" />我已通过服务端电脑或可信渠道核对完整指纹</label><div class="onboard-actions"><button class="secondary" type="button" @click="go('manual')">取消</button><button class="primary" type="button" :disabled="!trustChecked || busy" @click="approveTrust">确认身份并连接</button></div></section>

      <section v-else-if="screen === 'ready' && server" class="onboard-columns ready-columns"><div class="onboard-panel ready-primary"><div class="ready-symbol"><IconCheckboxCircleLine aria-hidden="true" /></div><p class="onboard-kicker">CONNECTION READY</p><h2>{{ server.isLocal ? '本机服务已启动' : '连接已建立' }}</h2><p>使用服务端账号登录后，就可以进入 ERP 工作台。</p><div class="onboard-actions"><button class="primary" type="button" @click="go('login')">进入登录 →</button><button class="secondary" type="button" @click="switchServer">切换服务端</button></div></div><div class="onboard-panel"><div class="panel-heading"><span class="panel-icon"><IconServerLine aria-hidden="true" /></span><div><h2>当前服务端</h2><p>连接信息与身份核验</p></div></div><dl class="server-details"><div><dt>名称</dt><dd>{{ server.name }}</dd></div><div><dt>地址</dt><dd>{{ server.host }}:{{ server.port }}</dd></div><div><dt>版本</dt><dd>v{{ server.version }}</dd></div><div><dt>状态</dt><dd class="online">运行中</dd></div></dl><template v-if="server.isLocal"><p class="fingerprint-label">请将此指纹提供给需要连接的团队成员核对：</p><div class="fingerprint compact">{{ server.fingerprint }}</div></template></div></section>

      <section v-else-if="screen === 'offline'" class="onboard-panel offline-panel"><span class="offline-symbol"><IconErrorWarningLine aria-hidden="true" /></span><h2>{{ server?.name || '服务端' }} · 暂时无法连接</h2><p>服务端可能未启动、网络不可达或证书发生变化。重新连接前请确认服务端身份。</p><div class="onboard-actions"><button class="primary" type="button" :disabled="busy" @click="checkConnection">重试连接</button><button v-if="host.configured && !host.running" class="secondary" type="button" :disabled="busy" @click="restartLocalHost">启动本机服务</button><button class="secondary" type="button" @click="switchServer">切换服务端</button></div></section>
    </main>
    <footer class="onboard-footer"><span>联光 ERP · 让业务流转有据可查</span><span>局域网内连接 · 账号权限由服务端管理</span></footer>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark"><img :src="nexoraLogo" alt="" /></span><div><strong>NEXORA</strong><small>联光 ERP · {{ server?.isLocal ? '本机服务' : '团队工作台' }}</small></div></div>
      <div v-if="screen === 'app'" class="side-group">
        <p class="side-label">工作台</p>
        <!-- 导航图标随可见标签一起生成，不改变现有权限判断。 -->
        <button v-for="item in visibleTabs" :key="item.key" class="nav-item" :class="{ active: activeTab === item.key }" type="button" @click="activeTab = item.key"><component :is="item.icon" class="nav-icon" aria-hidden="true" />{{ item.label }}</button>
      </div>
      <div class="sidebar-bottom"><span class="status-dot"></span> {{ server?.name || 'Nexora ERP' }} <small v-if="version">v{{ version }}</small></div>
    </aside>

    <main class="content">
      <header class="topbar">
        <div><p class="eyebrow">NEXORA WORKSPACE</p><h1>{{ screen === 'app' ? visibleTabs.find(item => item.key === activeTab)?.label : '开始使用联光 ERP' }}</h1></div>
        <div v-if="user" class="account"><span>{{ user.username }}<small>{{ user.roles.join(' · ') }}</small></span><button class="text-button" type="button" @click="logout">退出登录</button></div>
      </header>

      <div v-if="error" class="message error" role="alert">{{ error }}</div>
      <div v-if="connectionLost" class="message error" role="alert">服务端连接已中断，正在重试。恢复连接前无法保存更改。</div>
      <div v-if="notice" class="message success" role="status">{{ notice }}</div>

      <section v-if="screen === 'setup' || screen === 'login'" class="card auth-card">
        <p class="eyebrow">{{ screen === 'setup' ? '首次使用' : '欢迎回来' }}</p>
        <h2>{{ screen === 'setup' ? '创建首位管理员' : '登录工作台' }}</h2>
        <p class="muted">{{ screen === 'setup' ? '管理员可以创建用户并分配角色。请设置至少 12 位的密码。' : `使用 ${server?.name || '当前服务端'} 的账号访问采购、库存与用户权限。` }}</p>
        <form @submit.prevent="authenticate">
          <label>用户名<input v-model.trim="username" autocomplete="username" minlength="3" maxlength="40" required placeholder="例如 admin" /></label>
          <label>密码<input v-model="password" type="password" :autocomplete="screen === 'setup' ? 'new-password' : 'current-password'" :minlength="screen === 'setup' ? 12 : undefined" required placeholder="输入密码" /></label>
          <button class="primary" type="submit" :disabled="busy || connectionLost">{{ busy ? '请稍候…' : screen === 'setup' ? '创建管理员' : '登录' }}</button>
        </form>
        <button class="text-button auth-switch" type="button" @click="switchServer">切换服务端</button>
      </section>

      <template v-else-if="screen === 'app'">
        <section v-if="activeTab === 'stock'" class="stack">
          <div class="summary-grid"><div class="metric"><span>物料种类</span><strong>{{ materials.length }}</strong></div><div class="metric"><span>已确认入库单</span><strong>{{ receipts.filter(item => item.status === 'posted').length }}</strong></div><div class="metric"><span>库存流水</span><strong>{{ movements.length }}</strong></div></div>
          <div class="card">
            <div class="section-heading">
              <div><p class="eyebrow">INVENTORY</p><h2>当前库存</h2></div>
              <label>仓库<select v-model.number="selectedWarehouseId" :disabled="busy" @change="perform(refreshData, '库存已切换。')"><option :value="0">全部仓库</option><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
              <!-- 用 Naive UI 按钮接入现有刷新操作，并以 Tailwind 工具类避免窄屏挤压。 -->
              <NButton text type="primary" class="shrink-0" :disabled="busy" @click="perform(refreshData, '数据已刷新。')"><template #icon><IconRefreshLine aria-hidden="true" /></template>刷新</NButton>
            </div>
            <div class="table-wrap"><table><thead><tr><th>物料编码</th><th>物料名称</th><th>数量</th></tr></thead><tbody><tr v-for="item in stock" :key="item.id"><td class="mono">{{ item.sku }}</td><td>{{ item.name }}</td><td><strong>{{ item.quantity }}</strong> {{ item.unit }}</td></tr><tr v-if="!stock.length"><td colspan="3" class="muted">暂无物料，先到基础资料中添加。</td></tr></tbody></table></div>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">AUDIT TRAIL</p><h2>库存流水</h2></div></div><div class="table-wrap"><table><thead><tr><th>时间</th><th>仓库</th><th>物料</th><th>数量变动</th><th>来源</th></tr></thead><tbody><tr v-for="item in movements" :key="item.id"><td>{{ localTime(item.created_at) }}</td><td>{{ item.warehouse_name }}</td><td>{{ item.material_name }} <small class="mono">{{ item.sku }}</small></td><td>{{ item.quantity.startsWith('-') ? '' : '+' }}{{ item.quantity }} {{ item.unit }}</td><td>{{ movementSource(item) }}</td></tr><tr v-if="!movements.length"><td colspan="5" class="muted">确认入库、调拨、盘点、出库或退货后，这里会显示库存流水。</td></tr></tbody></table></div></div>
        </section>

        <section v-if="activeTab === 'finance' && receivablesPayables" class="stack">
          <div class="summary-grid"><div class="metric"><span>业务应收净额</span><strong>¥{{ receivablesPayables.receivable_amount }}</strong></div><div class="metric"><span>业务应付净额</span><strong>¥{{ receivablesPayables.payable_amount }}</strong></div><div class="metric"><span>待定价明细</span><strong>{{ receivablesPayables.unpriced_count }}</strong></div></div>
          <div v-if="can('finance.record')" class="card"><div class="section-heading"><div><p class="eyebrow">PAYMENT RECORD</p><h2>登记收付款</h2></div></div>
            <p class="muted">选择订单后登记真实发生的收付款。退款只在退货产生贷方余额时允许；录错请在下方冲销并重新登记。</p>
            <form @submit.prevent="createPaymentRecord"><div class="form-grid">
              <label>往来类别<select v-model="paymentForm.kind" @change="paymentForm.order_id = 0"><option value="receivable">客户应收</option><option value="payable">供应商应付</option></select></label>
              <label>关联订单<select v-model.number="paymentForm.order_id" required><option :value="0" disabled>选择已发生业务的订单</option><option v-for="item in financeAccounts.filter(entry => entry.kind === paymentForm.kind)" :key="`${item.kind}-${item.order_id}`" :value="item.order_id">#{{ item.order_id }} · {{ item.party_name }} · 未结 ¥{{ item.outstanding_amount }}</option></select></label>
              <label>业务动作<select v-model="paymentForm.action"><option value="settlement">{{ paymentForm.kind === 'receivable' ? '收到客户款' : '支付供应商' }}</option><option value="refund">{{ paymentForm.kind === 'receivable' ? '退还客户' : '收到供应商退款' }}</option></select></label>
              <label>金额（元）<input v-model.trim="paymentForm.amount" type="number" min="0.01" max="1000000000000" step="0.01" required /></label>
              <label>银行或收据参考号<input v-model.trim="paymentForm.reference" required maxlength="100" /></label>
              <label>备注（可选）<input v-model.trim="paymentForm.note" maxlength="200" /></label>
            </div><button class="primary" type="submit" :disabled="busy || !financeAccounts.length">登记收付款</button></form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">OPEN BALANCES</p><h2>订单核对</h2></div></div>
            <p class="muted">未结金额 = 已确认业务净额 − 收付款净额。负数表示应退客户或应收供应商退款。</p>
            <div class="table-wrap"><table><thead><tr><th>类别</th><th>往来单位</th><th>订单</th><th>业务净额</th><th>收付款净额</th><th>未结金额</th><th>来源明细</th></tr></thead><tbody>
              <tr v-for="item in financeAccounts" :key="`${item.kind}-${item.order_id}`"><td>{{ item.kind === 'receivable' ? '应收' : '应付' }}</td><td>{{ item.party_name }}</td><td>#{{ item.order_id }}</td><td>¥{{ item.business_amount }}</td><td>¥{{ item.settled_amount }}</td><td><strong>¥{{ item.outstanding_amount }}</strong></td><td>{{ item.source_keys.length }} 笔</td></tr>
              <tr v-if="!financeAccounts.length"><td colspan="7" class="muted">暂无可核对的订单金额。</td></tr>
            </tbody></table></div>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">PAYMENT AUDIT</p><h2>收付款与冲销记录</h2></div></div><div v-if="!paymentRecords.length" class="muted">暂无收付款记录。</div>
            <article v-for="item in paymentRecords" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ paymentActionLabel(item) }} · {{ item.party_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · {{ item.kind === 'receivable' ? '销售订单' : '采购订单' }} #{{ item.order_id }} · ¥{{ item.amount }} · 参考号 {{ item.reference }} · 操作人 {{ item.created_by_name }} <span v-if="item.reverses_id">· 冲销记录 #{{ item.reverses_id }}</span> <span v-if="item.note">· {{ item.note }}</span></p></div></div>
              <form v-if="item.action !== 'reversal' && !paymentRecords.some(entry => entry.reverses_id === item.id) && can('finance.reverse')" class="inline-form" @submit.prevent="reversePaymentRecord(item.id)"><label>冲销原因<input v-model.trim="reversalReasons[item.id]" required maxlength="200" /></label><button class="secondary small" type="submit" :disabled="busy">冲销此记录</button></form>
            </article>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">DOCUMENT RECONCILIATION</p><h2>应收应付来源</h2></div></div>
            <p class="muted">金额按已确认的出库、入库与退货明细计算，单位为人民币；无采购单价的历史入库显示“待核价”。</p>
            <div class="table-wrap"><table><thead><tr><th>确认时间</th><th>类别</th><th>往来单位</th><th>来源单据</th><th>物料</th><th>金额变动</th><th>操作人</th></tr></thead><tbody>
              <tr v-for="item in receivablesPayables.entries" :key="item.key"><td>{{ localTime(item.posted_at) }}</td><td>{{ item.kind === 'receivable' ? '应收' : '应付' }}</td><td>{{ item.party_name }}</td><td>{{ financialSource(item) }}<small v-if="item.order_id"> · 订单 #{{ item.order_id }}</small></td><td>{{ item.sku }} × {{ item.quantity }}</td><td>{{ item.amount === null ? '待核价' : `¥${item.amount}` }}</td><td>{{ item.posted_by_name ?? (item.posted_by === null ? '未知' : `#${item.posted_by}`) }}</td></tr>
              <tr v-if="!receivablesPayables.entries.length"><td colspan="7" class="muted">暂无已确认的金额来源单据。</td></tr>
            </tbody></table></div>
          </div>
        </section>

        <section v-if="activeTab === 'boms'" class="stack">
          <div v-if="can('bom.create')" class="card"><div class="section-heading"><div><p class="eyebrow">BILL OF MATERIALS</p><h2>新建 BOM 版本</h2></div><span class="pill">草稿</span></div>
            <p class="muted">BOM 记录生产指定数量成品所需的组件。旧版本会保留供追溯；同一成品一次只能启用一个版本。</p>
            <form @submit.prevent="createBom"><div class="form-grid"><label>成品物料<select v-model.number="bomForm.product_material_id" required><option :value="0" disabled>选择成品</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>基准产出数量<input v-model.trim="bomForm.base_quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><label>版本说明（可选）<input v-model.trim="bomForm.note" maxlength="200" /></label></div>
              <h3>组件用量</h3><div v-for="(line, index) in bomForm.lines" :key="index" class="line-row"><label>组件物料<select v-model.number="line.component_material_id" required><option :value="0" disabled>选择组件</option><option v-for="item in materials.filter(entry => entry.id !== bomForm.product_material_id)" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>基准用量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><button class="text-button" type="button" :disabled="bomForm.lines.length === 1" @click="bomForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="secondary" type="button" @click="bomForm.lines.push({ component_material_id: 0, quantity: '1' })">添加组件</button><button class="primary" type="submit" :disabled="busy || materials.length < 2">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">BOM HISTORY</p><h2>成品配方版本</h2></div></div><div v-if="!boms.length" class="muted">暂无 BOM。</div>
            <article v-for="item in boms" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.product_name }}（{{ item.product_sku }}）· V{{ item.version }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} · 基准产出 {{ item.base_quantity }} {{ item.product_unit }} <span v-if="item.note">· {{ item.note }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', active: '已启用', retired: '已停用', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('bom.activate')" class="primary small" type="button" :disabled="busy || boms.some(other => other.product_material_id === item.product_material_id && other.status === 'active')" @click="activateBom(item.id)">启用</button><button v-if="item.status === 'active' && can('bom.retire')" class="secondary small" type="button" :disabled="busy" @click="retireBom(item.id)">停用</button><button v-if="item.status === 'draft' && can('bom.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelBom(item.id)">取消草稿</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'workOrders'" class="stack">
          <div v-if="can('work_order.create')" class="card"><div class="section-heading"><div><p class="eyebrow">PRODUCTION ORDERS</p><h2>新建生产工单</h2></div><span class="pill">草稿</span></div>
            <p class="muted">选择已启用的 BOM 和目标产量。建单时会固定本次组件需求；仓库用于后续完工入库，目前不会改变库存。</p>
            <form @submit.prevent="createWorkOrder"><div class="form-grid"><label>启用的 BOM<select v-model.number="workOrderForm.bom_id" required><option :value="0" disabled>选择成品与版本</option><option v-for="item in boms.filter(entry => entry.status === 'active')" :key="item.id" :value="item.id">{{ item.product_name }}（{{ item.product_sku }}）· V{{ item.version }}</option></select></label><label>完工目标仓库<select v-model.number="workOrderForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>目标产量<input v-model.trim="workOrderForm.target_quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><label>参考号（可选）<input v-model.trim="workOrderForm.reference" maxlength="100" /></label><label>备注（可选）<input v-model.trim="workOrderForm.note" maxlength="200" /></label></div><button class="primary" type="submit" :disabled="busy || !boms.some(item => item.status === 'active') || !warehouses.length">保存工单草稿</button></form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">WORK ORDER HISTORY</p><h2>生产工单</h2></div></div><div v-if="!workOrders.length" class="muted">暂无生产工单。</div>
            <article v-for="item in workOrders" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.product_name }}（{{ item.product_sku }}）· BOM V{{ item.bom_version }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} · 目标 {{ item.target_quantity }} {{ item.product_unit }} · {{ item.warehouse_name }} <span v-if="item.reference">· {{ item.reference }}</span><span v-if="item.note"> · {{ item.note }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', released: '已下达', in_progress: '生产中', completed: '已完工', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('work_order.release')" class="primary small" type="button" :disabled="busy" @click="releaseWorkOrder(item.id)">下达</button><button v-if="(item.status === 'released' || item.status === 'in_progress') && item.lines.some(line => Number(line.remaining_quantity) > 0) && can('material_issue.create')" class="secondary small" type="button" :disabled="busy" @click="selectIssueOrder(item.id)">创建领料单</button><button v-if="item.status === 'in_progress' && Number(item.remaining_output_quantity) > 0 && can('production_completion.create')" class="secondary small" type="button" :disabled="busy" @click="selectCompletionOrder(item.id)">创建完工单</button><button v-if="(item.status === 'draft' || item.status === 'released') && can('work_order.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelWorkOrder(item.id)">取消</button></div></div><div class="receipt-lines"><span>已报工 {{ item.reported_quantity }} · 合格 {{ item.accepted_quantity }} · 不合格 {{ item.rejected_quantity }} · 待报工 {{ item.remaining_output_quantity }} {{ item.product_unit }}</span><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} · 需求 {{ line.required_quantity }} · 已领 {{ line.issued_quantity }} · 剩余 {{ line.remaining_quantity }} {{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'materialIssues'" class="stack">
          <div v-if="can('material_issue.create')" class="card"><div class="section-heading"><div><p class="eyebrow">MATERIAL ISSUE</p><h2>新建领料单</h2></div><span class="pill">草稿</span></div>
            <p class="muted">按工单剩余需料分批建单。草稿不预留库存；确认时服务端再次检查源仓库存与剩余需料。</p>
            <form @submit.prevent="createMaterialIssue"><div class="form-grid"><label>生产工单<select v-model.number="materialIssueForm.work_order_id" required @change="selectIssueOrder(materialIssueForm.work_order_id)"><option :value="0" disabled>选择已下达工单</option><option v-for="item in workOrders.filter(entry => (entry.status === 'released' || entry.status === 'in_progress') && entry.lines.some(line => Number(line.remaining_quantity) > 0))" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.product_name }} · {{ item.target_quantity }} {{ item.product_unit }}</option></select></label><label>领料源仓库<select v-model.number="materialIssueForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>参考号（可选）<input v-model.trim="materialIssueForm.reference" maxlength="100" /></label></div>
              <h3>本次领料数量</h3><div v-for="line in materialIssueForm.lines" :key="line.work_order_line_id" class="line-row"><label>{{ selectedIssueOrder?.lines.find(item => item.id === line.work_order_line_id)?.material_name }} · 剩余 {{ selectedIssueOrder?.lines.find(item => item.id === line.work_order_line_id)?.remaining_quantity }}<input v-model.trim="line.quantity" type="number" min="0.001" :max="selectedIssueOrder?.lines.find(item => item.id === line.work_order_line_id)?.remaining_quantity" step="0.001" required /></label><button class="text-button" type="button" :disabled="busy" @click="materialIssueForm.lines = materialIssueForm.lines.filter(item => item.work_order_line_id !== line.work_order_line_id)">本次不领</button></div>
              <button class="primary" type="submit" :disabled="busy || !materialIssueForm.lines.length || !warehouses.length">保存领料草稿</button>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">ISSUE HISTORY</p><h2>领料记录</h2></div></div><div v-if="!materialIssues.length" class="muted">暂无领料单。</div>
            <article v-for="item in materialIssues" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · 工单 #{{ item.work_order_id }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', posted: '已确认', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('material_issue.post')" class="primary small" type="button" :disabled="busy" @click="postMaterialIssue(item.id)">确认领料</button><button v-if="item.status === 'draft' && can('material_issue.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelMaterialIssue(item.id)">取消</button><button v-if="item.status === 'posted' && item.lines.some(line => Number(line.returnable_quantity) > 0) && can('material_return.create')" class="secondary small" type="button" :disabled="busy" @click="selectReturnIssue(item.id)">创建退料单</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} · 已领 {{ line.quantity }} · 已退 {{ line.returned_quantity }} · 可退 {{ line.returnable_quantity }} {{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'materialReturns'" class="stack">
          <div v-if="can('material_return.create')" class="card"><div class="section-heading"><div><p class="eyebrow">MATERIAL RETURN</p><h2>新建生产退料单</h2></div><span class="pill">草稿</span></div>
            <p class="muted">只退回已确认领料的组件，确认后入原领料仓库，并恢复工单可领数量。请按实际退回数量填写。</p>
            <form @submit.prevent="createMaterialReturn"><div class="form-grid"><label>原领料单<select v-model.number="materialReturnForm.material_issue_id" required @change="selectReturnIssue(materialReturnForm.material_issue_id)"><option :value="0" disabled>选择可退领料单</option><option v-for="item in materialIssues.filter(entry => entry.status === 'posted' && workOrders.some(order => order.id === entry.work_order_id && order.status === 'in_progress') && entry.lines.some(line => Number(line.returnable_quantity) > 0))" :key="item.id" :value="item.id">#{{ item.id }} · 工单 #{{ item.work_order_id }} · {{ item.warehouse_name }}</option></select></label><label>退料原因<input v-model.trim="materialReturnForm.reason" required maxlength="200" /></label></div>
              <h3>本次退料数量</h3><div v-for="line in materialReturnForm.lines" :key="line.material_issue_line_id" class="line-row"><label>{{ selectedReturnIssue?.lines.find(item => item.id === line.material_issue_line_id)?.material_name }} · 可退 {{ selectedReturnIssue?.lines.find(item => item.id === line.material_issue_line_id)?.returnable_quantity }}<input v-model.trim="line.quantity" type="number" min="0.001" :max="selectedReturnIssue?.lines.find(item => item.id === line.material_issue_line_id)?.returnable_quantity" step="0.001" required /></label><button class="text-button" type="button" :disabled="busy" @click="materialReturnForm.lines = materialReturnForm.lines.filter(item => item.material_issue_line_id !== line.material_issue_line_id)">本次不退</button></div>
              <button class="primary" type="submit" :disabled="busy || !materialReturnForm.lines.length">保存退料草稿</button>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">RETURN HISTORY</p><h2>生产退料记录</h2></div></div><div v-if="!materialReturns.length" class="muted">暂无退料单。</div>
            <article v-for="item in materialReturns" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · 原领料 #{{ item.material_issue_id }} · 工单 #{{ item.work_order_id }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} · {{ item.reason }}</p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', posted: '已确认', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('material_return.post')" class="primary small" type="button" :disabled="busy" @click="postMaterialReturn(item.id)">确认退料</button><button v-if="item.status === 'draft' && can('material_return.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelMaterialReturn(item.id)">取消</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'productionCompletions'" class="stack">
          <div v-if="can('production_completion.create')" class="card"><div class="section-heading"><div><p class="eyebrow">PRODUCTION COMPLETION</p><h2>新建完工报工单</h2></div><span class="pill">草稿</span></div>
            <p class="muted">按工单目标产量分批报工。报工数包含待质检的合格与不合格产品；质检并确认后，只有合格数进入工单目标仓库。</p>
            <form @submit.prevent="createProductionCompletion"><div class="form-grid"><label>生产工单<select v-model.number="completionForm.work_order_id" required @change="selectCompletionOrder(completionForm.work_order_id)"><option :value="0" disabled>选择生产中工单</option><option v-for="item in workOrders.filter(entry => entry.status === 'in_progress' && Number(entry.remaining_output_quantity) > 0)" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.product_name }} · 待报工 {{ item.remaining_output_quantity }} {{ item.product_unit }}</option></select></label><label>本次报工数量<input v-model.trim="completionForm.reported_quantity" type="number" min="0.001" :max="selectedCompletionOrder?.remaining_output_quantity" step="0.001" required /></label><label>参考号（可选）<input v-model.trim="completionForm.reference" maxlength="100" /></label></div><button class="primary" type="submit" :disabled="busy || !completionForm.work_order_id">保存报工草稿</button></form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">COMPLETION HISTORY</p><h2>完工与质检记录</h2></div></div><div v-if="!productionCompletions.length" class="muted">暂无完工单。</div>
            <article v-for="item in productionCompletions" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · 工单 #{{ item.work_order_id }} · {{ item.product_name }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 报工人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '待质检', inspected: '已质检', posted: '已入库', reversed: '已冲销', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'inspected' && can('production_completion.post')" class="primary small" type="button" :disabled="busy" @click="postProductionCompletion(item.id)">确认合格品入库</button><button v-if="(item.status === 'draft' || item.status === 'inspected') && can('production_completion.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelProductionCompletion(item.id)">取消</button></div></div><div class="receipt-lines"><span>报工 {{ item.reported_quantity }} · 合格 {{ item.accepted_quantity ?? '待质检' }} · 不合格 {{ item.rejected_quantity ?? '待质检' }} {{ item.product_unit }}</span><span v-if="item.qc_note">质检说明：{{ item.qc_note }} · 质检人 {{ item.inspected_by_name }}</span><span v-if="item.reversal_id">冲销 #{{ item.reversal_id }} · {{ item.reversal_reason }} · {{ item.reversed_by_name }} · {{ localTime(item.reversed_at!) }}</span></div>
              <form v-if="item.status === 'draft' && can('production_completion.inspect') && inspectionDrafts[item.id]" class="inline-form" @submit.prevent="inspectProductionCompletion(item.id)"><label>合格数量<input v-model.trim="inspectionDrafts[item.id]!.accepted_quantity" type="number" min="0" :max="item.reported_quantity" step="0.001" required /></label><label>质检说明<input v-model.trim="inspectionDrafts[item.id]!.qc_note" required maxlength="200" /></label><button class="primary small" type="submit" :disabled="busy">记录质检结果</button></form>
              <form v-if="item.status === 'posted' && can('production_completion.reverse')" class="inline-form" @submit.prevent="reverseProductionCompletion(item.id)"><label>冲销原因<input v-model.trim="completionReversalReasons[item.id]" required maxlength="200" placeholder="说明报工或质检记录错误" /></label><button class="secondary small" type="submit" :disabled="busy">冲销已确认完工</button></form>
            </article>
          </div>
        </section>

        <section v-if="activeTab === 'productionCosts'" class="stack">
          <div class="card">
            <div class="section-heading"><div><p class="eyebrow">PRODUCTION COST</p><h2>工单成本归集</h2></div></div>
            <p class="muted">材料单价由财务按凭据人工核定，金额按已领减已退数量计算。存在待核价领料时，总成本显示待核价；这不是库存计价或总账凭证。</p>
            <div v-if="!productionCostReport?.orders.length" class="muted">暂无生产工单。</div>
            <article v-for="item in productionCostReport?.orders ?? []" :key="item.work_order_id" class="receipt">
              <div class="receipt-head"><strong>工单 #{{ item.work_order_id }} · {{ item.product_name }}</strong><span class="pill">{{ item.work_order_status === 'draft' ? '未下达' : item.total_amount === null ? '待核价' : '当前已知' }}</span></div>
              <div class="receipt-lines"><span>材料已知金额 ¥{{ item.known_material_amount }}</span><span>人工 ¥{{ item.labor_amount }}</span><span>制造费用 ¥{{ item.overhead_amount }}</span><span>总成本 {{ item.total_amount === null ? '待核价' : `¥${item.total_amount}` }}</span><span v-if="item.unpriced_issue_count">待核价领料 {{ item.unpriced_issue_count }} 条</span></div>
            </article>
          </div>
          <div v-if="can('production_cost.record')" class="two-columns">
            <div class="card"><div class="section-heading"><h2>核定领料单价</h2></div>
              <form @submit.prevent="recordMaterialValuation"><div class="form-grid"><label>待核价领料<select v-model.number="materialValuationForm.material_issue_line_id" required><option :value="0" disabled>选择领料明细</option><option v-for="line in productionCostReport?.unpriced_lines ?? []" :key="line.material_issue_line_id" :value="line.material_issue_line_id">工单 #{{ line.work_order_id }} · 领料 #{{ line.material_issue_id }} · {{ line.material_name }} · 净领 {{ line.net_quantity }} {{ line.unit }}</option></select></label><label>核定单价（元）<input v-model.trim="materialValuationForm.unit_cost" type="number" min="0" max="1000000000" step="0.0001" required /></label><label>依据编号<input v-model.trim="materialValuationForm.reference" maxlength="100" required placeholder="发票或内部核价单编号" /></label><label>说明（可选）<input v-model.trim="materialValuationForm.note" maxlength="200" /></label></div><button class="primary" type="submit" :disabled="busy || !materialValuationForm.material_issue_line_id">保存核价</button></form>
            </div>
            <div class="card"><div class="section-heading"><h2>登记人工或制造费用</h2></div>
              <form @submit.prevent="recordProductionCharge"><div class="form-grid"><label>生产工单<select v-model.number="productionChargeForm.work_order_id" required><option :value="0" disabled>选择已下达工单</option><option v-for="item in (productionCostReport?.orders ?? []).filter(entry => entry.work_order_status !== 'draft' && entry.work_order_status !== 'cancelled')" :key="item.work_order_id" :value="item.work_order_id">#{{ item.work_order_id }} · {{ item.product_name }}</option></select></label><label>费用类别<select v-model="productionChargeForm.kind"><option value="labor">人工</option><option value="overhead">制造费用</option></select></label><label>金额（元）<input v-model.trim="productionChargeForm.amount" type="number" min="0.01" max="1000000000000" step="0.01" required /></label><label>依据编号<input v-model.trim="productionChargeForm.reference" maxlength="100" required /></label><label>说明（可选）<input v-model.trim="productionChargeForm.note" maxlength="200" /></label></div><button class="primary" type="submit" :disabled="busy || !productionChargeForm.work_order_id">登记费用</button></form>
            </div>
          </div>
          <div class="card"><div class="section-heading"><h2>成本记录与冲销</h2></div><div v-if="!productionCostReport?.entries.length" class="muted">暂无成本记录。</div>
            <article v-for="item in productionCostReport?.entries ?? []" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · 工单 #{{ item.work_order_id }} · {{ { material: '材料核价', labor: '人工', overhead: '制造费用' }[item.kind] }}</strong><p class="muted">{{ localTime(item.created_at) }} · {{ item.created_by_name }} · 依据 {{ item.reference }}</p></div><span class="pill">{{ item.status === 'active' ? '有效' : '已冲销' }}</span></div><div class="receipt-lines"><span v-if="item.kind === 'material'">{{ item.material_name }}（{{ item.material_sku }}）· 净领 {{ item.net_quantity }} · 单价 ¥{{ item.unit_cost }}</span><span>当前计入 {{ item.current_amount === null ? '已冲销' : `¥${item.current_amount}` }}</span><span v-if="item.note">{{ item.note }}</span><span v-if="item.reversal_id">冲销原因：{{ item.reversal_reason }} · {{ item.reversed_by_name }} · {{ localTime(item.reversed_at!) }}</span></div><form v-if="item.status === 'active' && can('production_cost.reverse')" class="inline-form" @submit.prevent="reverseProductionCost(item.id)"><label>冲销原因<input v-model.trim="costReversalReasons[item.id]" required maxlength="200" /></label><button class="secondary small" type="submit" :disabled="busy">冲销记录</button></form></article>
          </div>
        </section>

        <section v-if="activeTab === 'catalog'" class="stack">
          <div class="two-columns"><div class="card"><div class="section-heading"><div><p class="eyebrow">MATERIALS</p><h2>物料</h2></div></div><form v-if="can('catalog.manage')" class="inline-form" @submit.prevent="createMaterial"><label>物料编码<input v-model.trim="materialForm.sku" required maxlength="40" placeholder="SKU-001" /></label><label>名称<input v-model.trim="materialForm.name" required maxlength="120" placeholder="物料名称" /></label><label>单位<input v-model.trim="materialForm.unit" required maxlength="20" placeholder="件" /></label><button class="primary" type="submit" :disabled="busy">添加物料</button></form><div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th><th>单位</th></tr></thead><tbody><tr v-for="item in materials" :key="item.id"><td class="mono">{{ item.sku }}</td><td>{{ item.name }}</td><td>{{ item.unit }}</td></tr><tr v-if="!materials.length"><td colspan="3" class="muted">暂无物料。</td></tr></tbody></table></div></div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">SUPPLIERS</p><h2>供应商</h2></div></div><form v-if="can('catalog.manage')" class="inline-form" @submit.prevent="createSupplier"><label>供应商名称<input v-model.trim="supplierForm.name" required maxlength="120" placeholder="输入供应商名称" /></label><button class="primary" type="submit" :disabled="busy">添加供应商</button></form><div class="table-wrap"><table><thead><tr><th>名称</th></tr></thead><tbody><tr v-for="item in suppliers" :key="item.id"><td>{{ item.name }}</td></tr><tr v-if="!suppliers.length"><td class="muted">暂无供应商。</td></tr></tbody></table></div></div></div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">WAREHOUSES</p><h2>仓库</h2></div></div><form v-if="can('warehouse.manage')" class="inline-form" @submit.prevent="createWarehouse"><label>仓库编码<input v-model.trim="warehouseForm.code" required maxlength="40" pattern="[A-Za-z0-9_-]+" placeholder="例如 EAST" /></label><label>仓库名称<input v-model.trim="warehouseForm.name" required maxlength="80" placeholder="例如东区仓库" /></label><button class="primary" type="submit" :disabled="busy">添加仓库</button></form><div class="table-wrap"><table><thead><tr><th>编码</th><th>名称</th></tr></thead><tbody><tr v-for="item in warehouses" :key="item.id"><td class="mono">{{ item.code }}</td><td>{{ item.name }}</td></tr></tbody></table></div></div>
        </section>

        <section v-if="activeTab === 'purchase'" class="stack">
          <div v-if="can('purchase_order.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">PURCHASE ORDER</p><h2>新建采购订单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createPurchaseOrder">
              <div class="form-grid"><label>供应商<select v-model.number="purchaseForm.supplier_id" required><option :value="0" disabled>选择供应商</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>参考单号（可选）<input v-model.trim="purchaseForm.reference" maxlength="100" /></label></div>
              <h3>采购明细</h3>
              <div v-for="(line, index) in purchaseForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><label>单价（元）<input v-model.trim="line.unit_price" type="number" min="0" max="1000000000" step="0.0001" required /></label><button class="text-button" type="button" :disabled="purchaseForm.lines.length === 1" @click="purchaseForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="secondary" type="button" @click="purchaseForm.lines.push({ material_id: 0, quantity: '1', unit_price: '0' })">添加明细</button><button class="primary" type="submit" :disabled="busy || !suppliers.length || !materials.length">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">ORDER LOG</p><h2>采购订单</h2></div></div><div v-if="!purchaseOrders.length" class="muted">暂无采购订单。</div>
            <article v-for="item in purchaseOrders" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.supplier_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span> · 总额 ¥{{ item.total_amount }}</p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', confirmed: '待入库', partially_received: '部分入库', received: '全部入库', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('purchase_order.confirm')" class="primary small" type="button" :disabled="busy" @click="confirmPurchaseOrder(item.id)">确认订单</button><button v-if="['draft', 'confirmed'].includes(item.status) && can('purchase_order.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelPurchaseOrder(item.id)">取消订单</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} 已入 {{ line.received_quantity }}/{{ line.quantity }} {{ line.unit }} · 已退 {{ line.returned_quantity }} · 净入 {{ line.net_received_quantity }} · ¥{{ line.unit_price }}/{{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'receipts'" class="stack">
          <div v-if="can('receipt.create')" class="card"><div class="section-heading"><div><p class="eyebrow">PURCHASE RECEIPT</p><h2>新建入库单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createReceipt"><div class="form-grid"><label>关联采购订单（可选）<select v-model.number="receiptForm.purchase_order_id" @change="chooseReceiptOrder"><option :value="null">不关联订单</option><option v-for="item in purchaseOrders.filter(entry => ['confirmed', 'partially_received'].includes(entry.status))" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.supplier_name }}</option></select></label><label>供应商<select v-model.number="receiptForm.supplier_id" :disabled="receiptForm.purchase_order_id !== null" required><option :value="0" disabled>选择供应商</option><option v-for="item in suppliers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>入库仓库<select v-model.number="receiptForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>外部单号（可选）<input v-model.trim="receiptForm.reference" maxlength="100" placeholder="采购单或送货单号" /></label></div><h3>入库明细</h3><div v-for="(line, index) in receiptForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><button class="text-button" type="button" :disabled="receiptForm.lines.length === 1" @click="removeLine(index)">移除</button></div><div class="form-actions"><button class="secondary" type="button" @click="addLine">添加明细</button><button class="primary" type="submit" :disabled="busy || !materials.length || !suppliers.length">保存草稿</button></div></form></div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">RECEIPT LOG</p><h2>入库单</h2></div></div><div v-if="!receipts.length" class="muted">暂无入库单。</div><article v-for="item in receipts" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.supplier_name }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.purchase_order_id">· 采购订单 #{{ item.purchase_order_id }}</span> <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.status === 'posted' ? '已入库' : '待确认' }}</span><button v-if="item.status === 'draft' && can('receipt.post')" class="primary small" type="button" :disabled="busy" @click="postReceipt(item.id)">确认入库</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} · 已退 {{ line.returned_quantity }}</span></div></article></div>
        </section>

        <section v-if="activeTab === 'purchaseReturns'" class="stack">
          <div v-if="can('purchase_return.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">PURCHASE RETURN</p><h2>新建采购退货</h2></div><span class="pill">草稿</span></div>
            <p class="muted">退货从原入库仓库扣减。若货物已调走，请先调回；未关联采购订单的历史入库单不显示退货金额。</p>
            <form @submit.prevent="createPurchaseReturn">
              <div class="form-grid"><label>原入库单<select v-model.number="purchaseReturnForm.receipt_id" required @change="choosePurchaseReturnReceipt"><option :value="0" disabled>选择可退货的入库单</option><option v-for="item in receipts.filter(entry => entry.status === 'posted' && entry.lines.some(line => Number(line.returnable_quantity) > 0))" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.supplier_name }} · {{ item.warehouse_name }}</option></select></label><label>退货原因<input v-model.trim="purchaseReturnForm.reason" required maxlength="200" /></label></div>
              <h3>退货明细</h3>
              <div v-for="(line, index) in purchaseReturnForm.lines" :key="line.receipt_line_id" class="line-row"><label>原入库物料<input :value="selectedPurchaseReturnReceipt?.lines.find(item => item.id === line.receipt_line_id)?.material_name" disabled /></label><label>退货数量（最多 {{ selectedPurchaseReturnReceipt?.lines.find(item => item.id === line.receipt_line_id)?.returnable_quantity }}）<input v-model.trim="line.quantity" type="number" min="0.001" :max="selectedPurchaseReturnReceipt?.lines.find(item => item.id === line.receipt_line_id)?.returnable_quantity" step="0.001" required /></label><button class="text-button" type="button" @click="purchaseReturnForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="primary" type="submit" :disabled="busy || !purchaseReturnForm.lines.length">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">RETURN LOG</p><h2>采购退货记录</h2></div></div><div v-if="!purchaseReturns.length" class="muted">暂无采购退货单。</div>
            <article v-for="item in purchaseReturns" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.supplier_name }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 原入库单 #{{ item.receipt_id }} · {{ item.reason }} · 创建人 {{ item.created_by_name }} · 原价金额 {{ item.total_amount === null ? '待核对' : `¥${item.total_amount}` }}<span v-if="item.reversal_id"> · 冲销 #{{ item.reversal_id }}（{{ item.reversal_reason }} · {{ item.reversed_by_name }}）</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.reversal_id ? '已冲销' : item.status === 'posted' ? '已退供应商' : item.status === 'cancelled' ? '已取消' : '待确认' }}</span><button v-if="item.status === 'draft' && can('purchase_return.post')" class="primary small" type="button" :disabled="busy" @click="postPurchaseReturn(item.id)">确认退货</button><button v-if="item.status === 'draft' && can('purchase_return.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelPurchaseReturn(item.id)">取消</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} · {{ line.line_total === null ? '金额待核对' : `¥${line.line_total}` }}</span></div><form v-if="item.status === 'posted' && !item.reversal_id && can('purchase_return.reverse')" class="inline-form" @submit.prevent="reversePurchaseReturn(item.id)"><label>冲销原因<input v-model.trim="purchaseReturnReversalReasons[item.id]" required maxlength="200" placeholder="说明原退货为何需要冲销" /></label><button class="secondary small" type="submit" :disabled="busy">冲销已确认退货</button></form></article>
          </div>
        </section>

        <section v-if="activeTab === 'transfers'" class="stack">
          <div v-if="can('transfer.create')" class="card"><div class="section-heading"><div><p class="eyebrow">WAREHOUSE TRANSFER</p><h2>新建调拨单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createTransfer"><div class="form-grid"><label>来源仓库<select v-model.number="transferForm.from_warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>目标仓库<select v-model.number="transferForm.to_warehouse_id" required><option :value="0" disabled>选择目标仓库</option><option v-for="item in warehouses.filter(entry => entry.id !== transferForm.from_warehouse_id)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>参考单号（可选）<input v-model.trim="transferForm.reference" maxlength="100" /></label></div>
              <h3>调拨明细</h3><div v-for="(line, index) in transferForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><button class="text-button" type="button" :disabled="transferForm.lines.length === 1" @click="transferForm.lines.splice(index, 1)">移除</button></div><div class="form-actions"><button class="secondary" type="button" @click="transferForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button><button class="primary" type="submit" :disabled="busy || warehouses.length < 2 || !materials.length">保存草稿</button></div></form></div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">TRANSFER LOG</p><h2>调拨单</h2></div></div><div v-if="!transfers.length" class="muted">暂无调拨单。</div><article v-for="item in transfers" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.from_warehouse_name }} → {{ item.to_warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.reversal_id ? '已冲销' : item.status === 'posted' ? '已调拨' : '待确认' }}</span><button v-if="item.status === 'draft' && can('transfer.post')" class="primary small" type="button" :disabled="busy" @click="postTransfer(item.id)">确认调拨</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }}</span><span v-if="item.reversal_id">冲销 #{{ item.reversal_id }} · {{ item.reversal_reason }} · {{ item.reversed_by_name }} · {{ localTime(item.reversed_at!) }}</span></div><form v-if="item.status === 'posted' && !item.reversal_id && can('transfer.reverse')" class="inline-form" @submit.prevent="reverseTransfer(item.id)"><label>冲销原因<input v-model.trim="transferReversalReasons[item.id]" required maxlength="200" placeholder="说明原调拨为何需要冲销" /></label><button class="secondary small" type="submit" :disabled="busy">冲销已确认调拨</button></form></article></div>
        </section>

        <section v-if="activeTab === 'sales'" class="stack">
          <div v-if="can('customer.manage')" class="card">
            <div class="section-heading"><div><p class="eyebrow">CUSTOMERS</p><h2>客户资料</h2></div></div>
            <form class="inline-form" @submit.prevent="createCustomer"><label>客户名称<input v-model.trim="customerForm.name" required maxlength="120" placeholder="输入客户名称" /></label><button class="primary" type="submit" :disabled="busy">添加客户</button></form>
            <div class="receipt-lines"><span v-for="item in customers" :key="item.id">{{ item.name }}</span></div>
          </div>
          <div v-if="can('sales_order.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">SALES ORDER</p><h2>新建销售订单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createSalesOrder">
              <div class="form-grid"><label>客户<select v-model.number="salesForm.customer_id" required><option :value="0" disabled>选择客户</option><option v-for="item in customers" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>参考单号（可选）<input v-model.trim="salesForm.reference" maxlength="100" /></label></div>
              <h3>销售明细</h3>
              <div v-for="(line, index) in salesForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><label>单价（元）<input v-model.trim="line.unit_price" type="number" min="0" max="1000000000" step="0.0001" required /></label><button class="text-button" type="button" :disabled="salesForm.lines.length === 1" @click="salesForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="secondary" type="button" @click="salesForm.lines.push({ material_id: 0, quantity: '1', unit_price: '0' })">添加明细</button><button class="primary" type="submit" :disabled="busy || !customers.length || !materials.length">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">SALES LOG</p><h2>销售订单</h2></div></div><div v-if="!salesOrders.length" class="muted">暂无销售订单。</div>
            <article v-for="item in salesOrders" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.customer_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span> · 总额 ¥{{ item.total_amount }}</p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ { draft: '草稿', confirmed: '待出库', partially_shipped: '部分出库', shipped: '全部出库', cancelled: '已取消' }[item.status] }}</span><button v-if="item.status === 'draft' && can('sales_order.confirm')" class="primary small" type="button" :disabled="busy" @click="confirmSalesOrder(item.id)">确认订单</button><button v-if="['draft', 'confirmed'].includes(item.status) && can('sales_order.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelSalesOrder(item.id)">取消订单</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} · 已出库 {{ line.shipped_quantity }}/{{ line.quantity }} · 已退 {{ line.returned_quantity }} · 净交付 {{ line.net_delivered_quantity }} {{ line.unit }} · ¥{{ line.unit_price }}/{{ line.unit }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'shipments'" class="stack">
          <div v-if="can('shipment.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">SALES SHIPMENT</p><h2>新建出库单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createShipment">
              <div class="form-grid"><label>销售订单<select v-model.number="shipmentForm.sales_order_id" required @change="chooseShipmentOrder"><option :value="0" disabled>选择待出库订单</option><option v-for="item in salesOrders.filter(entry => ['confirmed', 'partially_shipped'].includes(entry.status))" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.customer_name }}</option></select></label><label>出库仓库<select v-model.number="shipmentForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>参考单号（可选）<input v-model.trim="shipmentForm.reference" maxlength="100" /></label></div>
              <p class="muted">确认出库时将从所选仓库扣减库存，并再次核对销售订单剩余数量。</p>
              <div v-for="(line, index) in shipmentForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>出库数量<input v-model.trim="line.quantity" type="number" min="0.001" max="1000000" step="0.001" required /></label><button class="text-button" type="button" :disabled="shipmentForm.lines.length === 1" @click="shipmentForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="secondary" type="button" @click="shipmentForm.lines.push({ material_id: 0, quantity: '1' })">添加明细</button><button class="primary" type="submit" :disabled="busy || !materials.length || !salesOrders.some(entry => ['confirmed', 'partially_shipped'].includes(entry.status))">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">SHIPMENT LOG</p><h2>出库单</h2></div></div><div v-if="!shipments.length" class="muted">暂无出库单。</div>
            <article v-for="item in shipments" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.customer_name }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 销售订单 #{{ item.sales_order_id }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.status === 'posted' ? '已出库' : item.status === 'cancelled' ? '已取消' : '待确认' }}</span><button v-if="item.status === 'draft' && can('shipment.post')" class="primary small" type="button" :disabled="busy" @click="postShipment(item.id)">确认出库</button><button v-if="item.status === 'draft' && can('shipment.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelShipment(item.id)">取消</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} · 已退 {{ line.returned_quantity }} · 可退 {{ line.returnable_quantity }}</span></div></article>
          </div>
        </section>

        <section v-if="activeTab === 'salesReturns'" class="stack">
          <div v-if="can('sales_return.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">SALES RETURN</p><h2>新建销售退货单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createSalesReturn">
              <div class="form-grid"><label>原出库单<select v-model.number="salesReturnForm.shipment_id" required @change="chooseSalesReturnShipment"><option :value="0" disabled>选择可退货的出库单</option><option v-for="item in shipments.filter(entry => entry.status === 'posted' && entry.lines.some(line => Number(line.returnable_quantity) > 0))" :key="item.id" :value="item.id">#{{ item.id }} · {{ item.customer_name }} · {{ item.warehouse_name }}</option></select></label><label>退回仓库<select v-model.number="salesReturnForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>退货原因<input v-model.trim="salesReturnForm.reason" required maxlength="200" /></label></div>
              <p class="muted">退货关联原出库明细；确认后新增入库流水，不修改原出库记录。金额按原销售单价计算，应收调整将在财务模块处理。</p>
              <div v-for="(line, index) in salesReturnForm.lines" :key="line.shipment_line_id" class="line-row"><label>原出库物料<input :value="selectedSalesReturnShipment?.lines.find(item => item.id === line.shipment_line_id)?.material_name" disabled /></label><label>退货数量（最多 {{ selectedSalesReturnShipment?.lines.find(item => item.id === line.shipment_line_id)?.returnable_quantity }}）<input v-model.trim="line.quantity" type="number" min="0.001" :max="selectedSalesReturnShipment?.lines.find(item => item.id === line.shipment_line_id)?.returnable_quantity" step="0.001" required /></label><button class="text-button" type="button" @click="salesReturnForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="primary" type="submit" :disabled="busy || !salesReturnForm.lines.length || !warehouses.length">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">RETURN LOG</p><h2>退货记录</h2></div></div><div v-if="!salesReturns.length" class="muted">暂无销售退货单。</div>
            <article v-for="item in salesReturns" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.customer_name }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 原出库单 #{{ item.shipment_id }} · {{ item.reason }} · 创建人 {{ item.created_by_name }} · 原价金额 ¥{{ item.total_amount }}<span v-if="item.reversal_id"> · 冲销 #{{ item.reversal_id }}（{{ item.reversal_reason }} · {{ item.reversed_by_name }}）</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.reversal_id ? '已冲销' : item.status === 'posted' ? '已退货入库' : item.status === 'cancelled' ? '已取消' : '待确认' }}</span><button v-if="item.status === 'draft' && can('sales_return.post')" class="primary small" type="button" :disabled="busy" @click="postSalesReturn(item.id)">确认退货</button><button v-if="item.status === 'draft' && can('sales_return.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelSalesReturn(item.id)">取消</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} × {{ line.quantity }} {{ line.unit }} · ¥{{ line.line_total }}</span></div><form v-if="item.status === 'posted' && !item.reversal_id && can('sales_return.reverse')" class="inline-form" @submit.prevent="reverseSalesReturn(item.id)"><label>冲销原因<input v-model.trim="salesReturnReversalReasons[item.id]" required maxlength="200" placeholder="说明原退货为何需要冲销" /></label><button class="secondary small" type="submit" :disabled="busy">冲销已确认退货</button></form></article>
          </div>
        </section>

        <section v-if="activeTab === 'stocktakes'" class="stack">
          <div v-if="can('stocktake.create')" class="card">
            <div class="section-heading"><div><p class="eyebrow">STOCKTAKE</p><h2>新建盘点单</h2></div><span class="pill">草稿</span></div>
            <form @submit.prevent="createStocktake">
              <div class="form-grid"><label>盘点仓库<select v-model.number="stocktakeForm.warehouse_id" required><option v-for="item in warehouses" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>盘点批次或备注（可选）<input v-model.trim="stocktakeForm.reference" maxlength="100" /></label></div>
              <p class="muted">只填写实际清点数量。保存时记录账面数量；若确认前库存发生变化，系统会要求重新盘点。</p>
              <div v-for="(line, index) in stocktakeForm.lines" :key="index" class="line-row"><label>物料<select v-model.number="line.material_id" required><option :value="0" disabled>选择物料</option><option v-for="item in materials" :key="item.id" :value="item.id">{{ item.sku }} · {{ item.name }}</option></select></label><label>实盘数量<input v-model.trim="line.counted_quantity" type="number" min="0" max="1000000" step="0.001" required /></label><button class="text-button" type="button" :disabled="stocktakeForm.lines.length === 1" @click="stocktakeForm.lines.splice(index, 1)">移除</button></div>
              <div class="form-actions"><button class="secondary" type="button" @click="stocktakeForm.lines.push({ material_id: 0, counted_quantity: '0' })">添加明细</button><button class="primary" type="submit" :disabled="busy || !materials.length">保存草稿</button></div>
            </form>
          </div>
          <div class="card"><div class="section-heading"><div><p class="eyebrow">COUNT RECORDS</p><h2>盘点记录</h2></div></div><div v-if="!stocktakes.length" class="muted">暂无盘点单。</div>
            <article v-for="item in stocktakes" :key="item.id" class="receipt"><div class="receipt-head"><div><strong>#{{ item.id }} · {{ item.warehouse_name }}</strong><p class="muted">{{ localTime(item.created_at) }} · 创建人 {{ item.created_by_name }} <span v-if="item.reference">· {{ item.reference }}</span></p></div><div class="receipt-actions"><span class="pill" :class="item.status">{{ item.reversal_id ? '已冲销' : item.status === 'posted' ? '已确认' : item.status === 'cancelled' ? '已取消' : '待确认' }}</span><button v-if="item.status === 'draft' && can('stocktake.post')" class="primary small" type="button" :disabled="busy" @click="postStocktake(item.id)">确认差异</button><button v-if="item.status === 'draft' && can('stocktake.cancel')" class="secondary small" type="button" :disabled="busy" @click="cancelStocktake(item.id)">取消</button></div></div><div class="receipt-lines"><span v-for="line in item.lines" :key="line.id">{{ line.material_name }} · 账面 {{ line.book_quantity }} → 实盘 {{ line.counted_quantity }} {{ line.unit }} · 差异 {{ line.difference }}</span><span v-if="item.reversal_id">冲销 #{{ item.reversal_id }} · {{ item.reversal_reason }} · {{ item.reversed_by_name }} · {{ localTime(item.reversed_at!) }}</span></div><form v-if="item.status === 'posted' && !item.reversal_id && can('stocktake.reverse')" class="inline-form" @submit.prevent="reverseStocktake(item.id)"><label>冲销原因<input v-model.trim="stocktakeReversalReasons[item.id]" required maxlength="200" placeholder="说明原盘点差异为何需要冲销" /></label><button class="secondary small" type="submit" :disabled="busy">冲销已确认盘点</button></form></article>
          </div>
        </section>

        <section v-if="activeTab === 'users' && can('users.manage')" class="stack">
          <div class="card"><div class="section-heading"><div><p class="eyebrow">ACCESS</p><h2>创建用户</h2></div></div><form class="inline-form" @submit.prevent="createUser"><label>用户名<input v-model.trim="newUser.username" required minlength="3" maxlength="40" placeholder="英文、数字或下划线" /></label><label>初始密码<input v-model="newUser.password" type="password" required minlength="12" maxlength="128" autocomplete="new-password" placeholder="至少 12 位" /></label><fieldset><legend>角色</legend><label v-for="role in roles" :key="role.code" class="check"><input v-model="newUser.roles" type="checkbox" :value="role.code" />{{ role.label }}</label></fieldset><button class="primary" type="submit" :disabled="busy || !newUser.roles.length">创建用户</button></form></div>
          <div class="card">
            <div class="section-heading"><div><p class="eyebrow">TEAM</p><h2>用户与角色</h2></div></div>
            <div v-for="entry in users" :key="entry.id" class="user-row">
              <div><strong>{{ entry.username }}</strong><small>#{{ entry.id }} · {{ entry.is_active ? '已启用' : '已停用' }}</small></div>
              <div class="user-access">
                <div class="role-picker"><label v-for="role in roles" :key="role.code" class="check"><input v-model="roleDrafts[entry.id]" type="checkbox" :value="role.code" />{{ role.label }}</label></div>
                <label class="reset-field">新密码<input v-model="resetPasswords[entry.id]" type="password" minlength="12" maxlength="128" autocomplete="new-password" placeholder="重置密码至少 12 位" /></label>
              </div>
              <div class="user-actions">
                <button class="secondary small" type="button" :disabled="busy || !roleDrafts[entry.id]?.length" @click="saveRoles(entry.id)">保存角色</button>
                <button class="secondary small" type="button" :disabled="busy || entry.id === user?.id || !resetPasswords[entry.id] || resetPasswords[entry.id].length < 12" @click="resetUserPassword(entry.id)">重置密码</button>
                <button class="secondary small" type="button" :disabled="busy || entry.id === user?.id" @click="setUserStatus(entry)">{{ entry.is_active ? '停用账号' : '启用账号' }}</button>
              </div>
            </div>
          </div>
          <div class="card">
            <div class="section-heading"><div><p class="eyebrow">ROLE SETTINGS</p><h2>角色与权限</h2></div></div>
            <form class="inline-form" @submit.prevent="createRole">
              <div class="form-grid"><label>角色代码<input v-model.trim="newRole.code" required minlength="3" maxlength="40" pattern="[a-z][a-z0-9_]*" placeholder="例如 stock_clerk" /></label><label>角色名称<input v-model.trim="newRole.label" required maxlength="40" placeholder="例如 库存专员" /></label></div>
              <fieldset><legend>授权范围</legend><label v-for="permission in permissions" :key="permission.code" class="check"><input v-model="newRole.permissions" type="checkbox" :value="permission.code" />{{ permission.label }}</label></fieldset>
              <button class="primary" type="submit" :disabled="busy">创建自定义角色</button>
            </form>
            <div v-for="role in roles" :key="role.code" class="role-row">
              <div><strong>{{ role.label }}</strong><small>{{ role.code }} · {{ role.is_builtin ? '内置角色' : '自定义角色' }}</small></div>
              <div v-if="role.is_builtin" class="muted">{{ role.permissions.map(code => permissions.find(item => item.code === code)?.label ?? code).join(' · ') }}</div>
              <div v-else class="role-editor"><label>名称<input v-model.trim="roleLabelDrafts[role.code]" maxlength="40" /></label><fieldset><legend>权限</legend><label v-for="permission in permissions" :key="permission.code" class="check"><input v-model="rolePermissionDrafts[role.code]" type="checkbox" :value="permission.code" />{{ permission.label }}</label></fieldset><button class="secondary small" type="button" :disabled="busy || !roleLabelDrafts[role.code]" @click="saveRole(role.code)">保存权限</button></div>
            </div>
          </div>
        </section>
        <section v-if="activeTab === 'settings'" class="stack"><div class="card"><div class="section-heading"><div><p class="eyebrow">CONNECTION</p><h2>当前连接</h2></div></div><dl class="server-details"><div><dt>服务端</dt><dd>{{ server?.name }}</dd></div><div><dt>地址</dt><dd>{{ server?.host }}:{{ server?.port }}</dd></div><div><dt>证书指纹</dt><dd class="mono">{{ server?.fingerprint }}</dd></div></dl><button class="secondary" type="button" @click="switchServer">切换服务端</button></div><div class="card"><div class="section-heading"><div><p class="eyebrow">ACCOUNT</p><h2>修改我的密码</h2></div></div><form class="inline-form" @submit.prevent="changeOwnPassword"><div class="form-grid"><label>当前密码<input v-model="passwordChange.current_password" type="password" required autocomplete="current-password" /></label><label>新密码<input v-model="passwordChange.new_password" type="password" required minlength="12" maxlength="128" autocomplete="new-password" placeholder="至少 12 位" /></label></div><p class="muted">修改后所有设备都需要重新登录。</p><button class="primary" type="submit" :disabled="busy">修改密码</button></form></div><div v-if="host.configured" class="card"><div class="section-heading"><div><p class="eyebrow">LOCAL HOST</p><h2>本机服务</h2></div><span class="pill" :class="{ posted: host.running }">{{ host.running ? '运行中' : '已停止' }}</span></div><p class="muted">{{ host.systemManaged ? '系统服务在关闭窗口、退出应用或无人登录时继续运行。' : host.migrationNeeded ? '旧版主机需点击启动，以迁移到系统服务。' : '开发模式下由桌面进程持有，退出应用后停止。' }}</p><div class="onboard-actions"><button v-if="host.running" class="secondary" type="button" :disabled="busy" @click="stopLocalHost">停止本机服务</button><button v-else class="primary" type="button" :disabled="busy" @click="restartLocalHost">{{ host.migrationNeeded ? '迁移并启动系统服务' : '启动本机服务' }}</button><button v-if="host.systemManaged" class="secondary" type="button" :disabled="busy" @click="upgradeLocalHost">用当前安装包升级服务</button></div></div></section>
      </template>
    </main>
  </div>
  </NConfigProvider>
</template>
