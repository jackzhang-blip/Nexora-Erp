import type { Warehouse } from '../../../../shared/erp-api'
import type { AppState } from '../state'

// 仓库与盘点操作独立维护；写入后由统一入口刷新服务端快照。
export function createWarehouseActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  const {
    warehouseForm,
    transferForm,
    transferReversalReasons,
    stocktakeForm,
    stocktakeReversalReasons
  } = state

  async function createWarehouse(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('createWarehouse', {
        ...warehouseForm.value
      })
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
        lines: transferForm.value.lines.map((line) => ({
          material_id: line.material_id,
          quantity: line.quantity
        }))
      })
      transferForm.value = {
        from_warehouse_id: transferForm.value.from_warehouse_id,
        to_warehouse_id: 0,
        reference: '',
        lines: [{ material_id: 0, quantity: '1' }]
      }
    }, '调拨单草稿已创建。')
  }

  async function postTransfer(transferId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('postTransfer', { transferId }),
      `调拨单 #${transferId} 已确认，双向库存流水已生成。`
    )
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
        lines: stocktakeForm.value.lines.map((line) => ({
          material_id: line.material_id,
          counted_quantity: line.counted_quantity
        }))
      })
      stocktakeForm.value = {
        warehouse_id: stocktakeForm.value.warehouse_id,
        reference: '',
        lines: [{ material_id: 0, counted_quantity: '0' }]
      }
    }, '盘点草稿已创建，请核对账面与实盘数量。')
  }

  async function postStocktake(stocktakeId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('postStocktake', { stocktakeId }),
      `盘点单 #${stocktakeId} 已确认，差异已记入库存流水。`
    )
  }

  async function cancelStocktake(stocktakeId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('cancelStocktake', { stocktakeId }),
      `盘点单 #${stocktakeId} 已取消。`
    )
  }

  async function reverseStocktake(stocktakeId: number): Promise<void> {
    if (!window.nexora) return
    const reason = stocktakeReversalReasons.value[stocktakeId] ?? ''
    await perform(async () => {
      await window.nexora!.callApi('reverseStocktake', { stocktakeId, reason })
      delete stocktakeReversalReasons.value[stocktakeId]
    }, `盘点单 #${stocktakeId} 已冲销，反向差异已记入库存流水。`)
  }

  async function saveWarehouse(data: Omit<Warehouse, 'id'>, id?: number): Promise<boolean> {
    if (!window.nexora) return false
    let saved = false
    await perform(async () => {
      if (id) await window.nexora!.callApi('updateWarehouse', { ...data, id })
      else await window.nexora!.callApi('createWarehouse', { ...data })
      saved = true
    }, '仓库已保存。')
    return saved
  }

  async function deleteWarehouse(id: number): Promise<void> {
    if (!window.nexora) return
    await perform(() => window.nexora!.callApi('deleteWarehouse', { id }), '仓库已删除。')
  }

  return {
    saveWarehouse,
    deleteWarehouse,
    createWarehouse,
    createTransfer,
    postTransfer,
    reverseTransfer,
    createStocktake,
    postStocktake,
    cancelStocktake,
    reverseStocktake
  }
}
