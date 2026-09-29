import type { Material, Supplier } from '../../../../shared/erp-api'
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

  async function saveMaterial(data: Omit<Material, 'id'>, id?: number): Promise<boolean> {
    if (!window.nexora) return false
    let saved = false
    await perform(async () => {
      if (id) await window.nexora!.callApi('updateMaterial', { ...data, id })
      else await window.nexora!.callApi('createMaterial', { ...data })
      saved = true
    }, '物料已保存。')
    return saved
  }

  async function deleteMaterial(id: number): Promise<void> {
    if (!window.nexora) return
    await perform(() => window.nexora!.callApi('deleteMaterial', { id }), '物料已删除。')
  }

  async function saveSupplier(data: Omit<Supplier, 'id'>, id?: number): Promise<boolean> {
    if (!window.nexora) return false
    let saved = false
    await perform(async () => {
      if (id) await window.nexora!.callApi('updateSupplier', { ...data, id })
      else await window.nexora!.callApi('createSupplier', { ...data })
      saved = true
    }, '供应商已保存。')
    return saved
  }

  async function deleteSupplier(id: number): Promise<void> {
    if (!window.nexora) return
    await perform(() => window.nexora!.callApi('deleteSupplier', { id }), '供应商已删除。')
  }

  async function setSupplierMaterial(supplierId: number, materialId: number, bound: boolean): Promise<void> {
    if (!window.nexora) return
    await perform(() => window.nexora!.callApi(bound ? 'bindSupplierMaterial' : 'unbindSupplierMaterial', {
      supplierId, materialId
    }), bound ? '物料已绑定。' : '已解除物料绑定。')
  }

  return { createMaterial, createSupplier, saveMaterial, deleteMaterial, saveSupplier, deleteSupplier, setSupplierMaterial }
}
