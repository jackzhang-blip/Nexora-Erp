// 官网独立演示模型；业务操作不依赖滚动，也不调用 ERP 接口。
export const catalog = {
  suppliers: ['SUP-A', 'SUP-B'], warehouses: ['WH-A', 'WH-B'],
  materials: ['MAT-A', 'MAT-B', 'MAT-C', 'MAT-D']
}
export class DemoError extends Error {
  constructor(code, field = '') { super(code); this.code = code; this.field = field }
}
const fail = (code, field) => { throw new DemoError(code, field) }
const safe = (n, field = '') => {
  if (n > BigInt(Number.MAX_SAFE_INTEGER) || n < 0n) fail('tooLarge', field)
  return Number(n)
}
export function decimal(value, places, field = '', allowZero = false) {
  const input = String(value).trim()
  if (!new RegExp(`^\\d+(?:\\.\\d{1,${places}})?$`).test(input) || input.length > 24) fail('number', field)
  const [whole, fraction = ''] = input.split('.')
  const result = safe(BigInt(whole) * 10n ** BigInt(places) + BigInt(fraction.padEnd(places, '0')), field)
  if (!allowZero && result === 0) fail('positive', field)
  return result
}
export function lineTotal(line, index = 0) {
  const quantity = decimal(line.quantity, 3, `quantity-${index}`)
  const price = decimal(line.price, 2, `price-${index}`, true)
  return safe((BigInt(quantity) * BigInt(price) + 500n) / 1000n, `price-${index}`)
}
export const total = receipt => safe(receipt.lines.reduce((sum, line, index) => sum + BigInt(lineTotal(line, index)), 0n))
export const paid = (state, id) => safe(state.payments.filter(p => p.receiptId === id).reduce((sum, p) => sum + BigInt(p.amount), 0n))
export function sources(state) {
  return state.receipts.filter(r => r.status === 'posted').map(r => {
    const amount = total(r), settled = paid(state, r.id)
    return { ...r, amount, paid: settled, remaining: amount - settled, paymentStatus: settled >= amount ? 'paid' : settled ? 'partial' : 'unpaid' }
  })
}
export function movements(state) {
  const balances = new Map()
  return state.receipts.filter(r => r.status === 'posted').flatMap(r => r.lines.map((line, index) => {
    const key = `${r.warehouse}/${line.material}`
    const quantity = decimal(line.quantity, 3)
    const balance = safe(BigInt(balances.get(key) || 0) + BigInt(quantity))
    balances.set(key, balance)
    return { id: `${r.id}/${index}`, receiptId: r.id, warehouse: r.warehouse, material: line.material, date: r.date, quantity, balance }
  }))
}
export function balances(state) {
  const result = new Map()
  for (const row of movements(state)) result.set(`${row.warehouse}/${row.material}`, { warehouse: row.warehouse, material: row.material, quantity: row.balance })
  return [...result.values()]
}
export function initialState() {
  return { version: 1, nextId: 2, selectedId: 'DEMO-001', receipts: [{ id: 'DEMO-001', status: 'posted', supplier: 'SUP-A', warehouse: 'WH-A', date: '2026-09-30', lines: [{ material: 'MAT-A', quantity: '12', price: '10.00' }] }], payments: [] }
}
function validateReceipt(r) {
  if (!catalog.suppliers.includes(r.supplier)) fail('supplier', 'supplier')
  if (!catalog.warehouses.includes(r.warehouse)) fail('warehouse', 'warehouse')
  if (!/^\d{4}-\d{2}-\d{2}$/.test(r.date) || !Number.isFinite(Date.parse(r.date)) || new Date(r.date).toISOString().slice(0, 10) !== r.date) fail('date', 'date')
  if (!r.lines.length) fail('lines', 'lines')
  r.lines.forEach((line, index) => {
    if (!catalog.materials.includes(line.material)) fail('material', `material-${index}`)
    lineTotal(line, index)
  })
  total(r)
}
export function transition(state, action) {
  const next = structuredClone(state)
  const r = next.receipts.find(row => row.id === (action.id || next.selectedId))
  if (action.type === 'reset') return initialState()
  if (action.type === 'new' || action.type === 'copy') {
    if (action.type === 'copy' && !r) fail('missing')
    const id = `DEMO-${String(next.nextId++).padStart(3, '0')}`
    next.receipts.push(action.type === 'copy' ? { ...structuredClone(r), id, status: 'draft' } : { id, status: 'draft', supplier: 'SUP-A', warehouse: 'WH-A', date: '2026-09-30', lines: [{ material: 'MAT-A', quantity: '1', price: '10.00' }] })
    next.selectedId = id
    return next
  }
  if (!r) fail('missing')
  if (action.type === 'select') { next.selectedId = r.id; return next }
  if (action.type === 'pay') {
    if (r.status !== 'posted') fail('draftPayment')
    const amount = decimal(action.amount, 2, 'payment')
    if (amount > total(r) - paid(next, r.id)) fail('overpayment', 'payment')
    next.payments.push({ id: `PAY-${next.payments.length + 1}`, receiptId: r.id, amount })
    return next
  }
  if (r.status !== 'draft') fail('locked')
  if (action.type === 'edit') {
    if (['supplier', 'warehouse', 'date'].includes(action.field)) r[action.field] = String(action.value)
    else if (['material', 'quantity', 'price'].includes(action.field) && r.lines[action.index]) r.lines[action.index][action.field] = String(action.value)
    else fail('field')
  } else if (action.type === 'addLine') r.lines.push({ material: 'MAT-B', quantity: '1', price: '10.00' })
  else if (action.type === 'removeLine') {
    if (r.lines.length <= 1) fail('lines', 'lines')
    if (!Number.isInteger(action.index) || !r.lines[action.index]) fail('field')
    r.lines.splice(action.index, 1)
  } else if (action.type === 'post') {
    validateReceipt(r)
    r.status = 'posted'
    movements(next) // 确认前检查累计数量，失败不替换旧状态。
  } else fail('action')
  return next
}
// 语言切换只接收当前演示模型；损坏或不兼容数据回退到初始示例。
export function restoreState(value) {
  try {
    if (value?.version !== 1 || !Array.isArray(value.receipts) || !value.receipts.length || !Array.isArray(value.payments)) return initialState()
    if (!Number.isSafeInteger(value.nextId) || value.nextId < 2) return initialState()
    const ids = new Set()
    for (const r of value.receipts) {
      if (!/^DEMO-\d{3,}$/.test(r.id) || ids.has(r.id) || Number(r.id.slice(5)) >= value.nextId || !['draft', 'posted'].includes(r.status)) return initialState()
      ids.add(r.id)
      if (!Array.isArray(r.lines) || r.lines.some(l => typeof l.quantity !== 'string' || typeof l.price !== 'string' || !catalog.materials.includes(l.material))) return initialState()
      if (!catalog.suppliers.includes(r.supplier) || !catalog.warehouses.includes(r.warehouse) || typeof r.date !== 'string') return initialState()
      if (r.status === 'posted') validateReceipt(r)
    }
    if (!ids.has(value.selectedId)) return initialState()
    const paymentIds = new Set()
    for (const p of value.payments) {
      if (!Number.isSafeInteger(p.amount) || p.amount <= 0 || !/^PAY-\d+$/.test(p.id) || paymentIds.has(p.id) || !value.receipts.some(r => r.id === p.receiptId && r.status === 'posted')) return initialState()
      paymentIds.add(p.id)
    }
    if (sources(value).some(s => s.remaining < 0)) return initialState()
    movements(value)
    return structuredClone(value)
  } catch { return initialState() }
}
