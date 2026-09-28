import type { AppState } from '../state'

// 采购单据操作独立维护；写入后由统一入口刷新服务端快照。
export function createPurchaseActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  const {
    purchaseOrders,
    receiptForm,
    purchaseForm,
    purchaseReturnForm,
    purchaseReturnReversalReasons,
    receiptReversalReasons,
    selectedPurchaseReturnReceipt
  } = state

  function addLine(): void {
    receiptForm.value.lines.push({ material_id: 0, quantity: '1' })
  }

  function removeLine(index: number): void {
    if (receiptForm.value.lines.length > 1)
      receiptForm.value.lines.splice(index, 1)
  }

  async function createReceipt(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('createReceipt', {
        supplier_id: receiptForm.value.supplier_id,
        warehouse_id: receiptForm.value.warehouse_id,
        purchase_order_id: receiptForm.value.purchase_order_id,
        reference: receiptForm.value.reference,
        lines: receiptForm.value.lines.map((line) => ({
          material_id: line.material_id,
          quantity: line.quantity
        }))
      })
      receiptForm.value = {
        supplier_id: 0,
        warehouse_id: receiptForm.value.warehouse_id,
        purchase_order_id: null,
        reference: '',
        lines: [{ material_id: 0, quantity: '1' }]
      }
    }, '入库单草稿已创建，等待仓库员确认。')
  }

  function chooseReceiptOrder(): void {
    // 关联采购订单后使用订单供应商和待入库明细，数量仍允许操作员按本批次调整。
    const order = purchaseOrders.value.find(
      (item) => item.id === receiptForm.value.purchase_order_id
    )
    if (!order) {
      receiptForm.value.supplier_id = 0
      receiptForm.value.lines = [{ material_id: 0, quantity: '1' }]
      return
    }
    receiptForm.value.supplier_id = order.supplier_id
    receiptForm.value.lines = order.lines
      .filter((line) => Number(line.remaining_quantity) > 0)
      .map((line) => ({
        material_id: line.material_id,
        quantity: line.remaining_quantity
      }))
  }

  async function createPurchaseOrder(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('createPurchaseOrder', {
        supplier_id: purchaseForm.value.supplier_id,
        reference: purchaseForm.value.reference,
        lines: purchaseForm.value.lines.map((line) => ({
          material_id: line.material_id,
          quantity: line.quantity,
          unit_price: line.unit_price
        }))
      })
      purchaseForm.value = {
        supplier_id: 0,
        reference: '',
        lines: [{ material_id: 0, quantity: '1', unit_price: '0' }]
      }
    }, '采购订单草稿已创建。')
  }

  async function confirmPurchaseOrder(orderId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('confirmPurchaseOrder', { orderId }),
      `采购订单 #${orderId} 已确认。`
    )
  }

  async function cancelPurchaseOrder(orderId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('cancelPurchaseOrder', { orderId }),
      `采购订单 #${orderId} 已取消。`
    )
  }

  async function postReceipt(receiptId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('postReceipt', { receiptId }),
      `入库单 #${receiptId} 已确认，库存流水已生成。`
    )
  }

  async function reverseReceipt(receiptId: number): Promise<void> {
    if (!window.nexora) return
    const reason = receiptReversalReasons.value[receiptId]?.trim() ?? ''
    // 页面只提交纠错原因；关联退货与库存可用量由服务端写事务核对。
    await perform(async () => {
      await window.nexora!.callApi('reverseReceipt', { receiptId, reason })
      delete receiptReversalReasons.value[receiptId]
    }, `入库单 #${receiptId} 已冲销，库存与应付已追加更正记录。`)
  }

  function choosePurchaseReturnReceipt(): void {
    const receipt = selectedPurchaseReturnReceipt.value
    // 原入库行决定退货上限和出库仓库，页面只预填当前尚可退的数量。
    purchaseReturnForm.value.lines =
      receipt?.lines
        .filter((line) => Number(line.returnable_quantity) > 0)
        .map((line) => ({
          receipt_line_id: line.id,
          quantity: line.returnable_quantity
        })) ?? []
  }

  async function createPurchaseReturn(): Promise<void> {
    if (!window.nexora || !purchaseReturnForm.value.lines.length) return
    await perform(async () => {
      await window.nexora!.callApi('createPurchaseReturn', {
        receipt_id: purchaseReturnForm.value.receipt_id,
        reason: purchaseReturnForm.value.reason,
        lines: purchaseReturnForm.value.lines.map((line) => ({ ...line }))
      })
      purchaseReturnForm.value = { receipt_id: 0, reason: '', lines: [] }
    }, '采购退货草稿已创建。')
  }

  async function postPurchaseReturn(returnId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('postPurchaseReturn', { returnId }),
      `采购退货单 #${returnId} 已确认，原入库仓库库存已扣减。`
    )
  }

  async function cancelPurchaseReturn(returnId: number): Promise<void> {
    if (!window.nexora) return
    await perform(
      () => window.nexora!.callApi('cancelPurchaseReturn', { returnId }),
      `采购退货单 #${returnId} 已取消。`
    )
  }

  async function reversePurchaseReturn(returnId: number): Promise<void> {
    if (!window.nexora) return
    const reason = purchaseReturnReversalReasons.value[returnId]?.trim() ?? ''
    // 正向补回库存和应付更正均由服务端写事务完成，页面只提交纠错原因。
    await perform(async () => {
      await window.nexora!.callApi('reversePurchaseReturn', {
        returnId,
        reason
      })
      delete purchaseReturnReversalReasons.value[returnId]
    }, `采购退货单 #${returnId} 已冲销，原仓库存与应付已追加更正记录。`)
  }

  return {
    addLine,
    removeLine,
    createReceipt,
    chooseReceiptOrder,
    createPurchaseOrder,
    confirmPurchaseOrder,
    cancelPurchaseOrder,
    postReceipt,
    reverseReceipt,
    choosePurchaseReturnReceipt,
    createPurchaseReturn,
    postPurchaseReturn,
    cancelPurchaseReturn,
    reversePurchaseReturn
  }
}
