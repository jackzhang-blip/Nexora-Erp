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
export interface Material { id: number; sku: string; name: string; unit: string }
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
  reference: string
  status: 'draft' | 'posted'
  created_by: number
  created_by_name: string
  posted_by: number | null
  created_at: string
  posted_at: string | null
  lines: ReceiptLine[]
}
export interface Movement {
  id: number
  material_id: number
  sku: string
  material_name: string
  unit: string
  quantity: string
  receipt_id: number
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
  materials: { input: undefined; output: Material[] }
  createMaterial: { input: { sku: string; name: string; unit: string }; output: Material }
  receipts: { input: undefined; output: Receipt[] }
  createReceipt: {
    input: { supplier_id: number; reference: string; lines: { material_id: number; quantity: string }[] }
    output: Receipt
  }
  postReceipt: { input: { receiptId: number }; output: Receipt }
  stock: { input: undefined; output: Stock[] }
  movements: { input: undefined; output: Movement[] }
}
