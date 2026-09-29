# 工作台页面目录

`WorkspaceShell.vue` 根据路由键选择下列页面。目录表示业务领域，文件名表示实际页面；新增入口时同步更新 `router/workspace-routes.ts`、`WorkspaceShell.vue` 和路由测试。

| 目录 | 页面组件 | 页面用途 |
| --- | --- | --- |
| `home/` | `HomeDashboardView.vue` | 以演示数据展示经营指标、趋势、单据构成和待处理事项；数据集中在 `dashboard-data.ts`，尚未接入真实统计 |
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

应用业务状态和主题状态由 Pinia 管理。`store/app-store.ts` 的 `useAppStore()` 保留页面现有的响应式 `ref` 取值接口；应用启动与监听器清理由根组件负责。

业务操作的临时成功与错误反馈写入共享 `notice` / `error` 后，由根组件内的 `AppMessageProvider.vue` 统一显示为右上角通知；页面不再占用内容区显示整行横幅。新页面在组件内需要主动提示时使用 `composables/use-app-message.ts`，不要直接建立第二个消息提供器。底栏继续显示服务端连接状态。
