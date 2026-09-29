# 工作台页面目录

`router/index.ts` 根据路由键装载下列页面，`WorkspaceShell.vue` 通过 `RouterView` 显示当前页面。目录表示业务领域，文件名表示实际页面；新增入口时同步更新 `router/workspace-routes.ts`、`router/index.ts` 和路由测试。

| 目录 | 页面组件 | 页面用途 |
| --- | --- | --- |
| `home/` | `HomeDashboardView.vue` | 以演示数据展示经营指标、趋势、单据构成和待处理事项；数据集中在 `dashboard-data.ts`，尚未接入真实统计 |
| `warehouse/` | `InventoryOverviewView.vue` | 查看当前库存与库存流水 |
| `warehouse/` | `OtherInboundsView.vue` | 处理期初、赠品等非采购入库及冲销 |
| `warehouse/` | `WarehouseTransfersView.vue` | 建立、确认及冲销仓库调拨 |
| `warehouse/` | `InventoryStocktakesView.vue` | 建立、确认及冲销库存盘点 |
| `catalog/` | `MaterialsView.vue` | 物料列表、搜索、增删改及关联供应商展示；沿用 `/workspace/catalog` 地址 |
| `catalog/` | `SuppliersView.vue` | 供应商增删改查及供货物料绑定、解绑 |
| `catalog/` | `WarehousesView.vue` | 仓库增删改查，默认主仓库禁止删除 |
| `purchase/` | `PurchaseOrdersView.vue` | 建立和管理采购订单 |
| `purchase/` | `PurchaseRequestsView.vue` | 采购申请、审批、分批转采购订单 |
| `purchase/` | `PurchaseGoodsReceiptsView.vue` | 分批记录采购合格实收与拒收，确认后生成待入库单 |
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
| `system/` | `RolePermissionsView.vue` | 在职务表格中搜索、筛选、新增和配置自定义角色；按模块、单据、操作树授权 |
| `system/` | `PermissionCatalogView.vue` | 独立维护操作权限的中文名称，模块与单据仍按树状目录查看 |
| `system/` | `ConnectionSettingsView.vue` | 查看连接、修改密码和管理本机服务 |

页面组件处理展示与表单绑定；跨页面草稿和服务端快照放在 `store/state.ts`，业务写操作放在 `store/modules/`。权限与地址规则只在 `router/workspace-routes.ts` 维护。

需要“上方功能区、下方列表”的业务页可复用 `components/workspace/WorkspaceTable.vue`：原生表格由页面传入标题、列头、结果数量和可选的最小宽度，按业务填充 `actions`、`filters`、`rows`、`empty` 与 `footer` 插槽；需要保留特殊标题或表格前表单时使用 `heading`、`beforeTable` 插槽。提供 `table` 插槽时，仅由页面接管表格本体，公共组件仍负责上方功能区。原生表格与 vxe table 的表头、数据单元格均按垂直居中显示。当前物料列表试接 vxe table 的纯表格版本，通过该插槽保留搜索、增删改和 Naive UI 的删除确认；供应商、仓库、供货物料及职务列表仍使用原生表格。vxe table 尚未推广到其他页面，也未启用表内编辑或批量写入。职务仍沿用现有角色与操作权限数据，内置角色只读；授权树由 `components/workspace/PermissionTreePicker.vue` 提供。权限目录在系统管理下使用单独路由，避免职务列表下方再展开很长的名称维护区域。权限目录可独立重试读取服务端数据，其他业务列表加载失败时不会使目录一直空白。

应用业务状态和主题状态由 Pinia 管理。`store/app-store.ts` 的 `useAppStore()` 保留页面现有的响应式 `ref` 取值接口；应用启动与监听器清理由根组件负责。

业务操作的临时成功与错误反馈写入共享 `notice` / `error` 后，由根组件内的 `AppMessageProvider.vue` 统一显示为右上角通知；页面不再占用内容区显示整行横幅。新页面在组件内需要主动提示时使用 `composables/use-app-message.ts`，不要直接建立第二个消息提供器。底栏继续显示服务端连接状态。

`warehouse/WarehouseOutboundsView.vue` 展示其他出库草稿、仓库确认、取消和冲销；库存仅在确认时变化。

采购退货页提交后展示待出库单号；仓库出库页复用列表确认采购退货，确认后才更新库存与应付。
