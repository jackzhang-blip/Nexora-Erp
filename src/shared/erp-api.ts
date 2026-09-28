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
  lines: ReceiptLine[]
}
// 已入库数量由服务端按确认单据汇总，前端只展示而不自行累计。
export interface PurchaseOrderLine extends ReceiptLine {
  unit_price: string
  received_quantity: string
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
  source_type: 'receipt' | 'transfer_out' | 'transfer_in' | 'stocktake' | 'shipment' | 'sales_return'
  source_id: number
  source_line_id: number
  receipt_id: number | null
  transfer_id: number | null
  stocktake_id: number | null
  shipment_id: number | null
  sales_return_id: number | null
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
