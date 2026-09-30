import type { LedgerCategory } from '../../../../../shared/erp-api'

export const ledgerCategoryLabels: Record<LedgerCategory, string> = {
  asset: '资产', liability: '负债', equity: '权益', income: '收入', expense: '费用', cost: '成本'
}
