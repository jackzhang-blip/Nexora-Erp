import type { AppState } from '../state'

// 核价写入后由统一刷新读取重算金额及完整修订记录。
export function createValuationActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  const { inventoryCostForm } = state

  async function recordInventoryCost(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('recordInventoryCost', { ...inventoryCostForm.value })
      inventoryCostForm.value = { movement_id: 0, unit_cost: '', reference: '', reason: '' }
    }, '库存核价已保存，相关金额已重新计算。')
  }

  return { recordInventoryCost }
}
