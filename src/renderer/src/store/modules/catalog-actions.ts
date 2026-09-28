import type { AppState } from '../state'

// 基础资料操作独立维护；写入后由统一入口刷新服务端快照。
export function createCatalogActions(
  state: AppState,
  perform: (action: () => Promise<unknown>, success: string) => Promise<void>
) {
  const { materialForm, supplierForm } = state

  async function createMaterial(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      // Vue 的响应式代理不能通过 Electron IPC，发送前只取普通字段。
      await window.nexora!.callApi('createMaterial', { ...materialForm.value })
      materialForm.value = { sku: '', name: '', unit: '件' }
    }, '物料已保存。')
  }

  async function createSupplier(): Promise<void> {
    if (!window.nexora) return
    await perform(async () => {
      await window.nexora!.callApi('createSupplier', {
        name: supplierForm.value.name
      })
      supplierForm.value = { name: '' }
    }, '供应商已保存。')
  }

  return { createMaterial, createSupplier }
}
