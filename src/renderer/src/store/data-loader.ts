import type { AppState } from './state'

// 每次写入后重新读取有权访问的数据，避免各业务页面保留过期快照。
export function createDataLoader(
  state: AppState,
  can: (permission: string) => boolean,
  syncWorkspaceRoute: () => void
) {
  const {
    user,
    materials,
    suppliers,
    supplierMaterials,
    stock,
    movements,
    receipts,
    purchaseOrders,
    purchaseReturns,
    receivablesPayables,
    financeAccounts,
    paymentRecords,
    boms,
    workOrders,
    materialIssues,
    materialReturns,
    productionCompletions,
    productionCostReport,
    warehouses,
    transfers,
    stocktakes,
    customers,
    salesOrders,
    shipments,
    salesReturns,
    selectedWarehouseId,
    roles,
    permissions,
    permissionLabelDrafts,
    users,
    roleDrafts,
    rolePermissionDrafts,
    roleLabelDrafts,
    inspectionDrafts
  } = state
  async function refreshData(): Promise<void> {
    if (!window.nexora || !user.value) return
    // 每次写操作后重新读取服务端权限；角色变化立即反映到当前页面。
    user.value = await window.nexora.callApi('me', undefined)
    syncWorkspaceRoute()
    // 页面只显示当前角色可访问的入口；数据访问仍以服务端授权为准。
    if (can('inventory.view')) {
      ;[
        materials.value,
        suppliers.value,
        supplierMaterials.value,
        stock.value,
        receipts.value,
        movements.value,
        warehouses.value,
        transfers.value,
        purchaseOrders.value,
        stocktakes.value,
        purchaseReturns.value
      ] = await Promise.all([
        window.nexora.callApi('materials', undefined),
        window.nexora.callApi('suppliers', undefined),
        window.nexora.callApi('supplierMaterials', undefined),
        window.nexora.callApi(
          'stock',
          selectedWarehouseId.value
            ? { warehouseId: selectedWarehouseId.value }
            : undefined
        ),
        window.nexora.callApi('receipts', undefined),
        window.nexora.callApi('movements', undefined),
        window.nexora.callApi('warehouses', undefined),
        window.nexora.callApi('transfers', undefined),
        window.nexora.callApi('purchaseOrders', undefined),
        window.nexora.callApi('stocktakes', undefined),
        window.nexora.callApi('purchaseReturns', undefined)
      ])
    }
    if (can('sales.view')) {
      ;[
        customers.value,
        salesOrders.value,
        shipments.value,
        salesReturns.value
      ] = await Promise.all([
        window.nexora.callApi('customers', undefined),
        window.nexora.callApi('salesOrders', undefined),
        window.nexora.callApi('shipments', undefined),
        window.nexora.callApi('salesReturns', undefined)
      ])
    }
    if (can('finance.view')) {
      // 单次服务端快照避免并发收付款时来源、余额和记录短暂不一致。
      const overview = await window.nexora.callApi('financeOverview', undefined)
      receivablesPayables.value = overview.report
      financeAccounts.value = overview.accounts
      paymentRecords.value = overview.payments
    } else {
      receivablesPayables.value = null
      financeAccounts.value = []
      paymentRecords.value = []
    }
    if (can('production.view')) {
      ;[
        boms.value,
        workOrders.value,
        materialIssues.value,
        materialReturns.value,
        productionCompletions.value
      ] = await Promise.all([
        window.nexora.callApi('boms', undefined),
        window.nexora.callApi('workOrders', undefined),
        window.nexora.callApi('materialIssues', undefined),
        window.nexora.callApi('materialReturns', undefined),
        window.nexora.callApi('productionCompletions', undefined)
      ])
      // 刷新列表时保留尚未提交的质检输入，避免其他业务操作意外清空填写内容。
      const previousInspections = inspectionDrafts.value
      inspectionDrafts.value = Object.fromEntries(
        productionCompletions.value
          .filter((item) => item.status === 'draft')
          .map((item) => [
            item.id,
            previousInspections[item.id] ?? {
              accepted_quantity: item.reported_quantity,
              qc_note: ''
            }
          ])
      )
    } else {
      boms.value = []
      workOrders.value = []
      materialIssues.value = []
      materialReturns.value = []
      productionCompletions.value = []
      inspectionDrafts.value = {}
    }
    productionCostReport.value = can('production_cost.view')
      ? await window.nexora.callApi('productionCosts', undefined)
      : null
    if (can('users.manage')) {
      ;[permissions.value, roles.value, users.value] = await Promise.all([
        window.nexora.callApi('permissions', undefined),
        window.nexora.callApi('roles', undefined),
        window.nexora.callApi('users', undefined)
      ])
      permissionLabelDrafts.value = Object.fromEntries(
        permissions.value.map((entry) => [entry.code, entry.label])
      )
      roleDrafts.value = Object.fromEntries(
        users.value.map((entry) => [entry.id, [...entry.roles]])
      )
      rolePermissionDrafts.value = Object.fromEntries(
        roles.value.map((entry) => [entry.code, [...entry.permissions]])
      )
      roleLabelDrafts.value = Object.fromEntries(
        roles.value.map((entry) => [entry.code, entry.label])
      )
    } else {
      permissions.value = []
      permissionLabelDrafts.value = {}
      roles.value = []
      users.value = []
    }
  }
  return refreshData
}
