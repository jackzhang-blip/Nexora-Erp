import type { AccountingPeriod, LedgerAccount } from '../../../../shared/erp-api'
import type { AppState } from '../state'

// 资料版本来自打开编辑器时的服务端快照；失败时不清空草稿或刷新版本。
export function createLedgerActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  function editLedgerAccount(item?: LedgerAccount): void {
    state.ledgerAccountForm.value = item ? { ...item, reason: '' } : {
      id: null, version: 1, code: '', name: '', category: 'asset', normal_balance: 'debit', is_active: true, reason: ''
    }
  }
  function editAccountingPeriod(item?: AccountingPeriod): void {
    state.accountingPeriodForm.value = item ? { ...item, reason: '' } : {
      id: null, version: 1, code: '', name: '', start_date: '', end_date: '', reason: ''
    }
  }
  async function saveLedgerAccount(): Promise<boolean> {
    if (!window.nexora) return false
    let saved = false
    await perform(async () => {
      const { id, version, code, name, category, normal_balance, is_active, reason } = state.ledgerAccountForm.value
      if (id !== null) await window.nexora!.callApi('updateLedgerAccount', { id, version, name, is_active, reason })
      else await window.nexora!.callApi('createLedgerAccount', { code, name, category, normal_balance, reason })
      editLedgerAccount()
      saved = true
    }, '总账科目已保存。')
    return saved
  }
  async function saveAccountingPeriod(): Promise<boolean> {
    if (!window.nexora) return false
    let saved = false
    await perform(async () => {
      const { id, version, code, name, start_date, end_date, reason } = state.accountingPeriodForm.value
      if (id !== null) await window.nexora!.callApi('updateAccountingPeriod', { id, version, name, reason })
      else await window.nexora!.callApi('createAccountingPeriod', { code, name, start_date, end_date, reason })
      editAccountingPeriod()
      saved = true
    }, '会计期间已保存。')
    return saved
  }
  async function loadLedgerAccountChanges(id: number) {
    if (!window.nexora) throw new Error('请在桌面应用中查看变更记录。')
    return window.nexora.callApi('ledgerAccountChanges', { id })
  }
  async function loadAccountingPeriodChanges(id: number) {
    if (!window.nexora) throw new Error('请在桌面应用中查看变更记录。')
    return window.nexora.callApi('accountingPeriodChanges', { id })
  }
  return { editLedgerAccount, editAccountingPeriod, saveLedgerAccount, saveAccountingPeriod,
    loadLedgerAccountChanges, loadAccountingPeriodChanges }
}
