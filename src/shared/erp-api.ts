// 桌面端与本地服务共用的数据契约；渲染进程不能自行指定请求地址。
export interface User {
  id: number
  username: string
  is_active: boolean
  roles: string[]
  permissions: string[]
}

export interface Permission { code: string; label: string }
export interface Role { code: string; label: string; is_builtin: boolean; permissions: string[] }
export interface Supplier { id: number; name: string }
export interface Customer { id: number; name: string }
export interface Material { id: number; sku: string; name: string; unit: string }
export interface Warehouse { id: number; code: string; name: string }
export interface Stock extends Material { quantity: string }
export interface ReceiptLine {
  id: number
  material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
}
export interface ReceivedLine extends ReceiptLine {
  returned_quantity: string
  returnable_quantity: string
}
export interface Receipt {
  id: number
  supplier_id: number
  supplier_name: string
  purchase_order_id: number | null
  warehouse_id: number
  warehouse_name: string
  reference: string
  status: 'draft' | 'posted'
  created_by: number
  created_by_name: string
  posted_by: number | null
  created_at: string
  posted_at: string | null
  lines: ReceivedLine[]
}
// 已入库数量由服务端按确认单据汇总，前端只展示而不自行累计。
export interface PurchaseOrderLine extends ReceiptLine {
  unit_price: string
  received_quantity: string
  net_received_quantity: string
  returned_quantity: string
  remaining_quantity: string
  line_total: string
}
export interface PurchaseOrder {
  id: number
  supplier_id: number
  supplier_name: string
  reference: string
  status: 'draft' | 'confirmed' | 'partially_received' | 'received' | 'cancelled'
  created_by: number
  created_by_name: string
  confirmed_by: number | null
  cancelled_by: number | null
  created_at: string
  confirmed_at: string | null
  cancelled_at: string | null
  lines: PurchaseOrderLine[]
  total_amount: string
}
// 历史未关联采购订单的入库单没有单价，退货金额明确为未知。
export interface PurchaseReturnLine extends ReceiptLine {
  receipt_line_id: number
  unit_price: string | null
  line_total: string | null
}
export interface PurchaseReturn {
  id: number
  receipt_id: number
  supplier_id: number
  supplier_name: string
  warehouse_id: number
  warehouse_name: string
  reason: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: PurchaseReturnLine[]
  total_amount: string | null
}
// 应收应付按已确认业务来源逐行推导，空金额表示原入库缺少合同单价。
export interface FinancialEntry {
  key: string
  kind: 'receivable' | 'payable'
  party_id: number
  party_name: string
  source_type: 'shipment' | 'sales_return' | 'receipt' | 'purchase_return'
  source_id: number
  source_line_id: number
  order_id: number | null
  material_id: number
  sku: string
  quantity: string
  unit_price: string | null
  amount: string | null
  currency: 'CNY'
  posted_by: number | null
  posted_by_name: string | null
  posted_at: string
}
export interface ReceivablesPayables {
  currency: 'CNY'
  receivable_amount: string
  payable_amount: string
  unpriced_count: number
  entries: FinancialEntry[]
}
export interface FinanceAccount {
  kind: 'receivable' | 'payable'
  order_id: number
  party_id: number
  party_name: string
  currency: 'CNY'
  business_amount: string
  settled_amount: string
  outstanding_amount: string
  source_keys: string[]
}
// 原收付款和冲销均为独立、不可编辑的记录，负金额表示退款或反向冲销。
export interface PaymentRecord {
  id: number
  kind: 'receivable' | 'payable'
  order_id: number
  action: 'settlement' | 'refund' | 'reversal'
  amount: string
  reference: string
  note: string
  reverses_id: number | null
  created_by: number
  created_by_name: string
  created_at: string
  party_id: number
  party_name: string
  currency: 'CNY'
}
export interface FinanceOverview {
  report: ReceivablesPayables
  accounts: FinanceAccount[]
  payments: PaymentRecord[]
}
export interface BomLine {
  id: number
  component_material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
}
// 生产工单将固定引用一个 BOM 版本，停用后历史内容仍可查询。
export interface Bom {
  id: number
  product_material_id: number
  product_sku: string
  product_name: string
  product_unit: string
  version: number
  base_quantity: string
  note: string
  status: 'draft' | 'active' | 'retired' | 'cancelled'
  created_by: number
  created_by_name: string
  activated_by: number | null
  retired_by: number | null
  cancelled_by: number | null
  created_at: string
  activated_at: string | null
  retired_at: string | null
  cancelled_at: string | null
  lines: BomLine[]
}
export interface WorkOrderLine {
  id: number
  component_material_id: number
  sku: string
  material_name: string
  unit: string
  required_quantity: string
  issued_quantity: string
  remaining_quantity: string
}
// 工单组件需求在建单时固定，旧 BOM 停用也不会改变已下达工单。
export interface WorkOrder {
  id: number
  bom_id: number
  bom_version: number
  product_material_id: number
  product_sku: string
  product_name: string
  product_unit: string
  warehouse_id: number
  warehouse_name: string
  target_quantity: string
  reference: string
  note: string
  status: 'draft' | 'released' | 'in_progress' | 'completed' | 'cancelled'
  created_by: number
  created_by_name: string
  released_by: number | null
  cancelled_by: number | null
  created_at: string
  released_at: string | null
  cancelled_at: string | null
  lines: WorkOrderLine[]
}
export interface MaterialIssueLine {
  id: number
  work_order_line_id: number
  component_material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
  returned_quantity: string
  returnable_quantity: string
}
// 确认后的领料单生成独立负向库存流水；原单据保留供追溯。
export interface MaterialIssue {
  id: number
  work_order_id: number
  warehouse_id: number
  warehouse_name: string
  reference: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: MaterialIssueLine[]
}
export interface MaterialReturnLine {
  id: number
  material_issue_line_id: number
  work_order_line_id: number
  component_material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
}
// 退料引用原领料明细并回到原仓库，确认后生成独立正向流水。
export interface MaterialReturn {
  id: number
  material_issue_id: number
  work_order_id: number
  warehouse_id: number
  warehouse_name: string
  reason: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: MaterialReturnLine[]
}
// 销售订单剩余量由已确认的出库单计算，草稿不会预先扣减。
export interface SalesOrderLine extends ReceiptLine {
  unit_price: string
  shipped_quantity: string
  returned_quantity: string
  net_delivered_quantity: string
  remaining_quantity: string
  line_total: string
}
export interface SalesOrder {
  id: number
  customer_id: number
  customer_name: string
  reference: string
  status: 'draft' | 'confirmed' | 'partially_shipped' | 'shipped' | 'cancelled'
  created_by: number
  created_by_name: string
  confirmed_by: number | null
  cancelled_by: number | null
  created_at: string
  confirmed_at: string | null
  cancelled_at: string | null
  lines: SalesOrderLine[]
  total_amount: string
}
export interface Shipment {
  id: number
  sales_order_id: number
  warehouse_id: number
  warehouse_name: string
  customer_name: string
  reference: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: ShipmentLine[]
}
export interface ShipmentLine extends ReceiptLine {
  returned_quantity: string
  returnable_quantity: string
}
// 退货明细固定关联原出库行，金额沿用原销售单价，由服务端计算。
export interface SalesReturnLine extends ReceiptLine {
  shipment_line_id: number
  unit_price: string
  line_total: string
}
export interface SalesReturn {
  id: number
  shipment_id: number
  sales_order_id: number
  warehouse_id: number
  warehouse_name: string
  customer_name: string
  reason: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: SalesReturnLine[]
  total_amount: string
}
// 调拨单沿用单据的状态与明细结构，同时明确记录两个仓库。
export interface Transfer extends Omit<Receipt, 'supplier_id' | 'supplier_name' | 'warehouse_id' | 'warehouse_name'> {
  from_warehouse_id: number
  from_warehouse_name: string
  to_warehouse_id: number
  to_warehouse_name: string
}
// 盘点差异由服务端根据建单快照计算，桌面端不能自行修改账面数量。
export interface StocktakeLine {
  id: number
  material_id: number
  sku: string
  material_name: string
  unit: string
  book_quantity: string
  counted_quantity: string
  difference: string
}
export interface Stocktake {
  id: number
  warehouse_id: number
  warehouse_name: string
  reference: string
  status: 'draft' | 'posted' | 'cancelled'
  created_by: number
  created_by_name: string
  posted_by: number | null
  cancelled_by: number | null
  created_at: string
  posted_at: string | null
  cancelled_at: string | null
  lines: StocktakeLine[]
}
export interface Movement {
  id: number
  warehouse_id: number
  warehouse_name: string
  material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
  source_type: 'receipt' | 'transfer_out' | 'transfer_in' | 'stocktake' | 'shipment' | 'sales_return' | 'purchase_return' | 'material_issue' | 'material_return'
  source_id: number
  source_line_id: number
  receipt_id: number | null
  transfer_id: number | null
  stocktake_id: number | null
  shipment_id: number | null
  sales_return_id: number | null
  purchase_return_id: number | null
  material_issue_id: number | null
  material_return_id: number | null
  created_by: number | null
  created_at: string
}

export interface ErpOperations {
  setupStatus: { input: undefined; output: { needs_setup: boolean } }
  bootstrap: { input: { username: string; password: string }; output: User }
  login: { input: { username: string; password: string }; output: User }
  logout: { input: undefined; output: void }
  me: { input: undefined; output: User }
  changePassword: { input: { current_password: string; new_password: string }; output: void }
  permissions: { input: undefined; output: Permission[] }
  roles: { input: undefined; output: Role[] }
  createRole: { input: { code: string; label: string; permissions: string[] }; output: Role }
  updateRole: { input: { code: string; label: string; permissions: string[] }; output: Role }
  users: { input: undefined; output: User[] }
  createUser: { input: { username: string; password: string; roles: string[] }; output: User }
  setUserRoles: { input: { userId: number; roles: string[] }; output: User }
  setUserStatus: { input: { userId: number; is_active: boolean }; output: User }
  resetUserPassword: { input: { userId: number; password: string }; output: void }
  suppliers: { input: undefined; output: Supplier[] }
  createSupplier: { input: { name: string }; output: Supplier }
  customers: { input: undefined; output: Customer[] }
  createCustomer: { input: { name: string }; output: Customer }
  materials: { input: undefined; output: Material[] }
  createMaterial: { input: { sku: string; name: string; unit: string }; output: Material }
  warehouses: { input: undefined; output: Warehouse[] }
  createWarehouse: { input: { code: string; name: string }; output: Warehouse }
  receipts: { input: undefined; output: Receipt[] }
  createReceipt: {
    input: { supplier_id: number; warehouse_id: number; purchase_order_id: number | null; reference: string; lines: { material_id: number; quantity: string }[] }
    output: Receipt
  }
  postReceipt: { input: { receiptId: number }; output: Receipt }
  purchaseReturns: { input: undefined; output: PurchaseReturn[] }
  receivablesPayables: { input: undefined; output: ReceivablesPayables }
  financeOverview: { input: undefined; output: FinanceOverview }
  financeAccounts: { input: undefined; output: FinanceAccount[] }
  paymentRecords: { input: undefined; output: PaymentRecord[] }
  createPaymentRecord: { input: { kind: 'receivable' | 'payable'; order_id: number; action: 'settlement' | 'refund'; amount: string; reference: string; note: string }; output: PaymentRecord }
  reversePaymentRecord: { input: { paymentId: number; reason: string }; output: PaymentRecord }
  boms: { input: undefined; output: Bom[] }
  createBom: { input: { product_material_id: number; base_quantity: string; note: string; lines: { component_material_id: number; quantity: string }[] }; output: Bom }
  activateBom: { input: { bomId: number }; output: Bom }
  retireBom: { input: { bomId: number }; output: Bom }
  cancelBom: { input: { bomId: number }; output: Bom }
  workOrders: { input: undefined; output: WorkOrder[] }
  createWorkOrder: { input: { bom_id: number; warehouse_id: number; target_quantity: string; reference: string; note: string }; output: WorkOrder }
  releaseWorkOrder: { input: { orderId: number }; output: WorkOrder }
  cancelWorkOrder: { input: { orderId: number }; output: WorkOrder }
  materialIssues: { input: undefined; output: MaterialIssue[] }
  createMaterialIssue: { input: { work_order_id: number; warehouse_id: number; reference: string; lines: { work_order_line_id: number; quantity: string }[] }; output: MaterialIssue }
  postMaterialIssue: { input: { issueId: number }; output: MaterialIssue }
  cancelMaterialIssue: { input: { issueId: number }; output: MaterialIssue }
  materialReturns: { input: undefined; output: MaterialReturn[] }
  createMaterialReturn: { input: { material_issue_id: number; reason: string; lines: { material_issue_line_id: number; quantity: string }[] }; output: MaterialReturn }
  postMaterialReturn: { input: { returnId: number }; output: MaterialReturn }
  cancelMaterialReturn: { input: { returnId: number }; output: MaterialReturn }
  createPurchaseReturn: { input: { receipt_id: number; reason: string; lines: { receipt_line_id: number; quantity: string }[] }; output: PurchaseReturn }
  postPurchaseReturn: { input: { returnId: number }; output: PurchaseReturn }
  cancelPurchaseReturn: { input: { returnId: number }; output: PurchaseReturn }
  purchaseOrders: { input: undefined; output: PurchaseOrder[] }
  createPurchaseOrder: { input: { supplier_id: number; reference: string; lines: { material_id: number; quantity: string; unit_price: string }[] }; output: PurchaseOrder }
  confirmPurchaseOrder: { input: { orderId: number }; output: PurchaseOrder }
  cancelPurchaseOrder: { input: { orderId: number }; output: PurchaseOrder }
  salesOrders: { input: undefined; output: SalesOrder[] }
  createSalesOrder: { input: { customer_id: number; reference: string; lines: { material_id: number; quantity: string; unit_price: string }[] }; output: SalesOrder }
  confirmSalesOrder: { input: { orderId: number }; output: SalesOrder }
  cancelSalesOrder: { input: { orderId: number }; output: SalesOrder }
  shipments: { input: undefined; output: Shipment[] }
  createShipment: { input: { sales_order_id: number; warehouse_id: number; reference: string; lines: { material_id: number; quantity: string }[] }; output: Shipment }
  postShipment: { input: { shipmentId: number }; output: Shipment }
  cancelShipment: { input: { shipmentId: number }; output: Shipment }
  salesReturns: { input: undefined; output: SalesReturn[] }
  createSalesReturn: { input: { shipment_id: number; warehouse_id: number; reason: string; lines: { shipment_line_id: number; quantity: string }[] }; output: SalesReturn }
  postSalesReturn: { input: { returnId: number }; output: SalesReturn }
  cancelSalesReturn: { input: { returnId: number }; output: SalesReturn }
  transfers: { input: undefined; output: Transfer[] }
  createTransfer: { input: { from_warehouse_id: number; to_warehouse_id: number; reference: string; lines: { material_id: number; quantity: string }[] }; output: Transfer }
  postTransfer: { input: { transferId: number }; output: Transfer }
  stocktakes: { input: undefined; output: Stocktake[] }
  createStocktake: { input: { warehouse_id: number; reference: string; lines: { material_id: number; counted_quantity: string }[] }; output: Stocktake }
  postStocktake: { input: { stocktakeId: number }; output: Stocktake }
  cancelStocktake: { input: { stocktakeId: number }; output: Stocktake }
  stock: { input: { warehouseId?: number } | undefined; output: Stock[] }
  movements: { input: undefined; output: Movement[] }
}
