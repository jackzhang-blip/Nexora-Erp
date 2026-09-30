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
| `catalog/` | `CustomersView.vue` | 客户搜索与新增；销售查看权限可浏览，客户管理权限可新增 |
| `catalog/` | `WarehousesView.vue` | 仓库增删改查，默认主仓库禁止删除 |
| `purchase/` | `PurchaseOrdersView.vue` | 建立和管理采购订单 |
| `purchase/` | `PurchaseRequestsView.vue` | 采购申请、审批、分批转采购订单 |
| `purchase/` | `PurchaseGoodsReceiptsView.vue` | 分批记录采购合格实收与拒收，确认后生成待入库单 |
| `purchase/` | `PurchaseReceiptsView.vue` | 建立和确认采购入库单 |
| `purchase/` | `PurchaseReturnsView.vue` | 处理采购退货 |
| `sales/` | `SalesOrdersView.vue` | 建立和管理销售订单；客户资料独立维护，订单弹窗提供快捷入口并保留草稿 |
| `sales/` | `SalesShipmentsView.vue` | 处理销售出库 |
| `sales/` | `SalesReturnsView.vue` | 处理销售退货 |
| `finance/` | `ReceivablesPayablesView.vue` | 应收应付汇总及订单金额核对 |
| `finance/` | `PaymentRecordsView.vue` | 独立查询、登记收付款及冲销，保留审计记录 |
| `finance/` | `FinancialSourcesView.vue` | 查看应收应付的业务来源明细 |
| `finance/` | `InventoryValuationView.vue` | 查看移动平均库存金额、待核价来源和核价修订历史 |
| `production/` | `ProductionBomsView.vue` | 管理生产 BOM 版本 |
| `production/` | `ProductionWorkOrdersView.vue` | 建立和下达生产工单 |
| `production/` | `MaterialIssuesView.vue` | 处理生产领料 |
| `production/` | `MaterialReturnsView.vue` | 处理生产退料 |
| `production/` | `ProductionCompletionsView.vue` | 报工、质检与成品入库 |
| `production/` | `ProductionCostsView.vue` | 库存领料成本、核价、费用归集、完工批次结算与冲销 |
| `system/` | `UserManagementView.vue` | 创建账号并管理用户状态与角色 |
| `system/` | `RolePermissionsView.vue` | 在职务表格中搜索、筛选、新增和配置自定义角色；按模块、单据、操作树授权 |
| `system/` | `PermissionCatalogView.vue` | 独立维护操作权限的中文名称，模块与单据仍按树状目录查看 |
| `system/` | `ConnectionSettingsView.vue` | 查看连接、修改密码和管理本机服务 |

页面组件处理展示与表单绑定；跨页面草稿和服务端快照放在 `store/state.ts`，业务写操作放在 `store/modules/`。权限与地址规则只在 `router/workspace-routes.ts` 维护。

工作台中的表格统一由 `components/workspace/WorkspaceTable.vue` 封装的 vxe-table 渲染。页面传入 `columns`、`data` 和可选的最小宽度，通过 `cell-<列键>` 插槽填写业务单元格；标题、筛选、操作、表前说明、空状态和页脚分别使用 `heading`、`filters`、`actions`、`beforeTable`、`empty`、`footer` 插槽。表格超出可视宽度时，底部提供始终可见的横向滚动条；查询失败可用 `error` 和 `errorActions` 显示失败原因与重试入口。采购与库存报表也使用同一组件，CSV 继续基于相同的服务端查询结果。列表新增入口以按钮打开 Naive UI 弹窗，保存失败保留草稿；复杂单据的确认、冲销仍保留原有操作流程。职务仍沿用现有角色与操作权限数据，内置角色只读；授权树由 `components/workspace/PermissionTreePicker.vue` 提供。权限目录在系统管理下使用单独路由，避免职务列表下方再展开很长的名称维护区域。权限目录可独立重试读取服务端数据，其他业务列表加载失败时不会使目录一直空白。

应用业务状态和主题状态由 Pinia 管理。`store/app-store.ts` 的 `useAppStore()` 保留页面现有的响应式 `ref` 取值接口；应用启动与监听器清理由根组件负责。

业务操作的临时成功与错误反馈写入共享 `notice` / `error` 后，由根组件内的 `AppMessageProvider.vue` 统一显示为右上角通知；页面不再占用内容区显示整行横幅。新页面在组件内需要主动提示时使用 `composables/use-app-message.ts`，不要直接建立第二个消息提供器。底栏继续显示服务端连接状态。

`warehouse/WarehouseOutboundsView.vue` 展示其他出库草稿、仓库确认、取消和冲销；库存仅在确认时变化。

采购退货页提交后展示待出库单号；仓库出库页复用列表确认采购退货，确认后才更新库存与应付。

`warehouse/InventoryLedgerView.vue` 复用工作台表格展示服务端筛选后的期初、逐笔流水与期末。公共表格以完整占位区展示空结果或加载失败；台账查询失败时隐藏上次结果，并提供重新查询。服务端若返回默认 `Not Found`，桌面端会提示核对两端版本，不将失败误当作无流水。

`warehouse/InventoryAdjustmentsView.vue` 管理独立库存调整的提交、异人审批、仓库确认、取消与冲销。

`purchase/PurchaseReportsView.vue` 与 `warehouse/InventoryReportsView.vue` 共用报表表格，查询和 CSV 使用同一份服务端结果。

仓库管理八个页面统一使用公共表格及台账式筛选面板。顶部保留 `NEXORA WORKSPACE` 和页面主标题，主列表设置 `showTitle=false`，仅保留说明与操作，避免重复标题；表格仍保留可访问名称，期初期末等次级列表继续显示标题。筛选面板的间距、底色、换行和明暗主题由 `WorkspaceTable` 统一管理，其他业务表格也沿用该样式。库存总览的汇总卡片放在筛选与表格之间；台账先显示筛选和流水，再显示期初期末。调拨与盘点以单据表格展示，支持按单号、仓库或物料搜索，并保留新增弹窗、权限控制、确认、取消（盘点）与冲销记录。

用户管理单独展示 ID、账号、姓名、工号、手机号和已分配角色；创建/编辑弹窗维护资料与角色，密码通过操作列的重置弹窗修改。账号状态使用 Naive UI Switch，保存失败保留原显示，当前账号不可停用或由此重置密码。

`system/MenuManagementView.vue` 提供「菜单管理」（`/workspace/menu-management`），沿用 `users.manage` 权限。一级导航分组与全部页面入口均可从内置图标库选择图标，支持搜索、预览和恢复默认；选择后点击保存才会写入服务端。页面从路由表构建菜单树，配置由 Pinia 共享，保存失败保留编辑内容。配置不支持上传图片，不改变菜单名称、顺序、路由和授权；其他客户端需重新登录或刷新数据后更新。
