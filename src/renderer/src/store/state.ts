import { computed, ref } from 'vue'
import type {
  Bom,
  Customer,
  FinanceAccount,
  FinancialEntry,
  Material,
  MaterialIssue,
  MaterialReturn,
  Movement,
  PaymentRecord,
  Permission,
  ProductionCompletion,
  ProductionCostReport,
  PurchaseOrder,
  PurchaseReturn,
  ReceivablesPayables,
  Receipt,
  Role,
  SalesOrder,
  SalesReturn,
  Shipment,
  Stock,
  Stocktake,
  Supplier,
  Transfer,
  User,
  Warehouse,
  WorkOrder
} from '../../../shared/erp-api'
import type {
  ConnectionCandidate,
  DiscoveryResult,
  HostStatus,
  ServerProfile
} from '../../../shared/desktop-api'
import type {
  WorkspaceRouteGroupKey,
  WorkspaceRouteKey
} from '../router/workspace-routes'
import type { Screen } from './types'

// 表单草稿与服务端快照按应用实例创建，切换页面时保留输入。
export function createAppState() {
  const screen = ref<Screen>('loading')
  const openedRouteKeys = ref<WorkspaceRouteKey[]>([])
  // 日常默认全部收起，点击分类时最多展开一个。
  const expandedGroupKey = ref<WorkspaceRouteGroupKey | null>(null)
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
  const permissionLabelDrafts = ref<Record<string, string>>({})
  const users = ref<User[]>([])
  const roleDrafts = ref<Record<number, string[]>>({})
  const rolePermissionDrafts = ref<Record<string, string[]>>({})
  const roleLabelDrafts = ref<Record<string, string>>({})
  const resetPasswords = ref<Record<number, string>>({})
  const materialForm = ref({ sku: '', name: '', unit: '件' })
  const supplierForm = ref({ name: '' })
  const receiptForm = ref({
    supplier_id: 0,
    warehouse_id: 1,
    purchase_order_id: null as number | null,
    reference: '',
    lines: [{ material_id: 0, quantity: '1' }]
  })
  const purchaseForm = ref({
    supplier_id: 0,
    reference: '',
    lines: [{ material_id: 0, quantity: '1', unit_price: '0' }]
  })
  const purchaseReturnForm = ref({
    receipt_id: 0,
    reason: '',
    lines: [] as { receipt_line_id: number; quantity: string }[]
  })
  const paymentForm = ref({
    kind: 'receivable' as 'receivable' | 'payable',
    order_id: 0,
    action: 'settlement' as 'settlement' | 'refund',
    amount: '',
    reference: '',
    note: ''
  })
  const reversalReasons = ref<Record<number, string>>({})
  const bomForm = ref({
    product_material_id: 0,
    base_quantity: '1',
    note: '',
    lines: [{ component_material_id: 0, quantity: '1' }]
  })
  const workOrderForm = ref({
    bom_id: 0,
    warehouse_id: 1,
    target_quantity: '1',
    reference: '',
    note: ''
  })
  const materialIssueForm = ref({
    work_order_id: 0,
    warehouse_id: 1,
    reference: '',
    lines: [] as { work_order_line_id: number; quantity: string }[]
  })
  const materialReturnForm = ref({
    material_issue_id: 0,
    reason: '',
    lines: [] as { material_issue_line_id: number; quantity: string }[]
  })
  const completionForm = ref({
    work_order_id: 0,
    reported_quantity: '1',
    reference: ''
  })
  const inspectionDrafts = ref<
    Record<number, { accepted_quantity: string; qc_note: string }>
  >({})
  const completionReversalReasons = ref<Record<number, string>>({})
  const materialValuationForm = ref({
    material_issue_line_id: 0,
    unit_cost: '0',
    reference: '',
    note: ''
  })
  const productionChargeForm = ref({
    work_order_id: 0,
    kind: 'labor' as 'labor' | 'overhead',
    amount: '',
    reference: '',
    note: ''
  })
  const costReversalReasons = ref<Record<number, string>>({})
  const warehouseForm = ref({ code: '', name: '' })
  const transferForm = ref({
    from_warehouse_id: 1,
    to_warehouse_id: 0,
    reference: '',
    lines: [{ material_id: 0, quantity: '1' }]
  })
  const transferReversalReasons = ref<Record<number, string>>({})
  const salesReturnReversalReasons = ref<Record<number, string>>({})
  const purchaseReturnReversalReasons = ref<Record<number, string>>({})
  const receiptReversalReasons = ref<Record<number, string>>({})
  const shipmentReversalReasons = ref<Record<number, string>>({})
  const stocktakeForm = ref({
    warehouse_id: 1,
    reference: '',
    lines: [{ material_id: 0, counted_quantity: '0' }]
  })
  const stocktakeReversalReasons = ref<Record<number, string>>({})
  const customerForm = ref({ name: '' })
  const salesForm = ref({
    customer_id: 0,
    reference: '',
    lines: [{ material_id: 0, quantity: '1', unit_price: '0' }]
  })
  const shipmentForm = ref({
    sales_order_id: 0,
    warehouse_id: 1,
    reference: '',
    lines: [{ material_id: 0, quantity: '1' }]
  })
  const salesReturnForm = ref({
    shipment_id: 0,
    warehouse_id: 1,
    reason: '',
    lines: [] as { shipment_line_id: number; quantity: string }[]
  })
  const newUser = ref({
    username: '',
    password: '',
    roles: ['viewer'] as string[]
  })
  // 新角色默认不授予任何权限，必须由管理员明确勾选授权范围。
  const newRole = ref({ label: '', permissions: [] as string[] })
  const passwordChange = ref({ current_password: '', new_password: '' })
  const server = ref<ServerProfile | null>(null)
  const candidate = ref<ConnectionCandidate | null>(null)
  const recentServers = ref<ServerProfile[]>([])
  const discoveries = ref<DiscoveryResult[]>([])
  const scanSeconds = ref(0)
  const scanning = ref(false)
  const manualForm = ref({ address: '', port: 8000 })
  const hostForm = ref({
    name: '我的 Nexora ERP',
    dataDir: '',
    port: 8000,
    username: 'admin',
    password: '',
    confirm: ''
  })
  const trustChecked = ref(false)
  const host = ref<HostStatus>({
    configured: false,
    running: false,
    systemManaged: false,
    migrationNeeded: false,
    fingerprint: null
  })
  const connectionLost = ref(false)
  // 连接恢复反馈独立于业务操作提示，供所有页面共用的底栏展示。
  const connectionNotice = ref('')

  const selectedSalesReturnShipment = computed(() =>
    shipments.value.find(
      (item) => item.id === salesReturnForm.value.shipment_id
    )
  )
  const selectedPurchaseReturnReceipt = computed(() =>
    receipts.value.find(
      (item) => item.id === purchaseReturnForm.value.receipt_id
    )
  )
  const selectedIssueOrder = computed(() =>
    workOrders.value.find(
      (item) => item.id === materialIssueForm.value.work_order_id
    )
  )
  const selectedReturnIssue = computed(() =>
    materialIssues.value.find(
      (item) => item.id === materialReturnForm.value.material_issue_id
    )
  )
  const selectedCompletionOrder = computed(() =>
    workOrders.value.find(
      (item) => item.id === completionForm.value.work_order_id
    )
  )

  return {
    screen,
    openedRouteKeys,
    expandedGroupKey,
    version,
    notice,
    error,
    busy,
    user,
    username,
    password,
    materials,
    suppliers,
    stock,
    movements,
    receipts,
    purchaseOrders,
    purchaseReturns,
    receivablesPayables,
    financeAccounts,
    paymentRecords,
    boms,
    workOrders,
    materialIssues,
    materialReturns,
    productionCompletions,
    productionCostReport,
    warehouses,
    transfers,
    stocktakes,
    customers,
    salesOrders,
    shipments,
    salesReturns,
    selectedWarehouseId,
    roles,
    permissions,
    permissionLabelDrafts,
    users,
    roleDrafts,
    rolePermissionDrafts,
    roleLabelDrafts,
    resetPasswords,
    materialForm,
    supplierForm,
    receiptForm,
    purchaseForm,
    purchaseReturnForm,
    paymentForm,
    reversalReasons,
    bomForm,
    workOrderForm,
    materialIssueForm,
    materialReturnForm,
    completionForm,
    inspectionDrafts,
    completionReversalReasons,
    materialValuationForm,
    productionChargeForm,
    costReversalReasons,
    warehouseForm,
    transferForm,
    transferReversalReasons,
    salesReturnReversalReasons,
    purchaseReturnReversalReasons,
    receiptReversalReasons,
    shipmentReversalReasons,
    stocktakeForm,
    stocktakeReversalReasons,
    customerForm,
    salesForm,
    shipmentForm,
    salesReturnForm,
    newUser,
    newRole,
    passwordChange,
    server,
    candidate,
    recentServers,
    discoveries,
    scanSeconds,
    scanning,
    manualForm,
    hostForm,
    trustChecked,
    host,
    connectionLost,
    connectionNotice,
    selectedSalesReturnShipment,
    selectedPurchaseReturnReceipt,
    selectedIssueOrder,
    selectedReturnIssue,
    selectedCompletionOrder
  }
}

export type AppState = ReturnType<typeof createAppState>
