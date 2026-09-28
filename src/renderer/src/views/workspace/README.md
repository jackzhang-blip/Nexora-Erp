# 工作台页面目录

`WorkspaceShell.vue` 根据路由键选择下列页面。目录表示业务领域，文件名表示实际页面；新增入口时同步更新 `router/workspace-routes.ts`、`WorkspaceShell.vue` 和路由测试。

| 目录 | 页面组件 | 页面用途 |
| --- | --- | --- |
| `warehouse/` | `InventoryOverviewView.vue` | 查看当前库存与库存流水 |
| `warehouse/` | `WarehouseTransfersView.vue` | 建立、确认及冲销仓库调拨 |
| `warehouse/` | `InventoryStocktakesView.vue` | 建立、确认及冲销库存盘点 |
| `catalog/` | `MaterialsSuppliersView.vue` | 维护物料与供应商资料 |
| `purchase/` | `PurchaseOrdersView.vue` | 建立和管理采购订单 |
| `purchase/` | `PurchaseReceiptsView.vue` | 建立和确认采购入库单 |
| `purchase/` | `PurchaseReturnsView.vue` | 处理采购退货 |
| `sales/` | `SalesOrdersView.vue` | 建立和管理销售订单 |
| `sales/` | `SalesShipmentsView.vue` | 处理销售出库 |
| `sales/` | `SalesReturnsView.vue` | 处理销售退货 |
| `finance/` | `ReceivablesPayablesView.vue` | 查看应收应付并登记收付款 |
| `production/` | `ProductionBomsView.vue` | 管理生产 BOM 版本 |
| `production/` | `ProductionWorkOrdersView.vue` | 建立和下达生产工单 |
| `production/` | `MaterialIssuesView.vue` | 处理生产领料 |
| `production/` | `MaterialReturnsView.vue` | 处理生产退料 |
| `production/` | `ProductionCompletionsView.vue` | 报工、质检与成品入库 |
| `production/` | `ProductionCostsView.vue` | 核价、费用归集与成本冲销 |
| `system/` | `UserManagementView.vue` | 创建账号并管理用户状态与角色 |
| `system/` | `RolePermissionsView.vue` | 创建角色并设置权限 |
| `system/` | `ConnectionSettingsView.vue` | 查看连接、修改密码和管理本机服务 |

页面组件处理展示与表单绑定；跨页面草稿和服务端快照放在 `store/state.ts`，业务写操作放在 `store/modules/`。权限与地址规则只在 `router/workspace-routes.ts` 维护。
