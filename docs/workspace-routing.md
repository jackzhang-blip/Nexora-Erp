# 工作台路由表

工作台页面统一登记在 `src/renderer/src/workspace-routes.ts`。侧栏分类、页面地址和进入页面所需的**查看权限**均从该表读取。地址使用 `#` 前缀，便于 Electron 桌面页面在刷新后恢复当前模块。

| 分类 | 页面 | 地址 | 查看权限 |
| --- | --- | --- | --- |
| 仓库管理 | 库存总览 | `#/workspace/stock` | `inventory.view` |
| 仓库管理 | 仓库调拨 | `#/workspace/transfers` | `inventory.view` |
| 仓库管理 | 库存盘点 | `#/workspace/stocktakes` | `inventory.view` |
| 基础资料 | 物料与供应商 | `#/workspace/catalog` | `inventory.view` |
| 采购管理 | 采购订单 | `#/workspace/purchase-orders` | `inventory.view` |
| 采购管理 | 采购入库 | `#/workspace/receipts` | `inventory.view` |
| 采购管理 | 采购退货 | `#/workspace/purchase-returns` | `inventory.view` |
| 销售管理 | 销售订单 | `#/workspace/sales-orders` | `sales.view` |
| 销售管理 | 销售出库 | `#/workspace/shipments` | `sales.view` |
| 销售管理 | 销售退货 | `#/workspace/sales-returns` | `sales.view` |
| 财务管理 | 应收应付 | `#/workspace/finance` | `finance.view` |
| 生产管理 | 生产 BOM | `#/workspace/boms` | `production.view` |
| 生产管理 | 生产工单 | `#/workspace/work-orders` | `production.view` |
| 生产管理 | 生产领料 | `#/workspace/material-issues` | `production.view` |
| 生产管理 | 生产退料 | `#/workspace/material-returns` | `production.view` |
| 生产管理 | 完工与质检 | `#/workspace/production-completions` | `production.view` |
| 生产管理 | 生产成本 | `#/workspace/production-costs` | `production_cost.view` |
| 系统管理 | 用户权限 | `#/workspace/users` | `users.manage` |
| 系统管理 | 连接与服务 | `#/workspace/settings` | 已登录账号均可访问 |

登录后，工作台依据服务端返回的权限显示导航。直接打开地址、浏览器历史切换，以及刷新服务端权限后，都会重新核对当前页面；未知或无权访问的地址会替换为当前账号可访问的第一个页面。没有业务查看权限的账号仍可进入“连接与服务”管理自己的连接和密码。

侧栏分类默认全部收起。点击分类标题展开页面入口，再次点击收起；展开另一分类时，之前的分类自动收起。展开与收起有短暂的高度和透明度过渡，箭头同步转动；系统启用“减少动态效果”时取消这些过渡。当前页面所属分类即使收起也会保留高亮提示。

路由表只控制页面展示。创建、确认、冲销和其他写操作仍按各自权限由 FastAPI 服务端校验；客户端侧栏隐藏或页面拦截不能代替服务端授权。增加页面时，需要同步登记路由、页面内容和测试。当前登录与初次连接流程仍由应用启动状态管理，不属于工作台路由。
