# Nexora ERP（联光 ERP）

面向企业内部的桌面 ERP。当前版本已具备用户与角色权限管理、物料、供应商与客户资料、采购订单及分批入库与退货、销售订单及分批出库与退货、生产 BOM、工单与分批领料、多仓库库存、调拨与盘点流水，以及局域网服务端的创建、发现和连接。

## 当前工作方式

首次打开客户端，可选择**手动连接**、**扫描局域网**或**在本机新建服务端**。服务端由 FastAPI 管理 SQLite 数据库和权限；其他客户端通过 HTTPS 访问同一个服务端。客户端重启后会尝试重连上次选择的服务端，但仍需登录账号。

创建服务端时填写实例名称、数据目录、监听端口和首位管理员账号。已有数据库不会被覆盖。安装版会以 Windows 服务或 macOS LaunchDaemon 运行固定主机；关闭窗口、退出桌面应用或无人登录时服务仍可运行，并可从设置或托盘手动停止。开发模式仍由桌面进程临时启动服务，退出应用后停止。首次安装系统服务与手动启停需要管理员授权。

首次连接其他电脑时，请将客户端展示的 SHA-256 指纹与服务端电脑“服务端已就绪”页面中的指纹完整核对，再输入账号密码。连接记录只保存地址、服务端身份和证书，不保存密码。证书变化时，自动重连会被阻止，需重新核验。

**当前数据集中保存在服务端。**远程客户端断网后不能继续编辑；工作台会提示断线并重试，连接恢复后重新读取服务端数据。没有本地数据合并或离线同步。应收应付来源清单和手工收付款记录已实现；总账、MySQL、跨设备数据同步、人力资源与 CRM 是后续阶段的工作。

## 开发

需要 Node.js 22.12+、Python 3.11+。在仓库根目录运行：

```bash
npm install
python3 -m pip install -r backend/requirements-dev.txt
npm run dev
```

Windows 可把 `python3` 改为 `python`。如果 Python 不在默认路径，可设置 `NEXORA_PYTHON` 指向解释器。桌面应用会在“新建服务端”时自动启动 Python 服务。单独调试后端见 [后端说明](backend/README.md)。

渲染页面已接入 Naive UI 和 Tailwind CSS 4。Vue 组件可从 `naive-ui` 按需导入；`App.vue` 的 `NConfigProvider` 统一提供中文语言与主题色。Tailwind 工具类可直接写在 Vue 模板中，入口为 `src/renderer/src/style.css`。项目保留原有基础样式，因此未启用 Tailwind Preflight 全局重置。

界面图标使用 [Remix Icon](https://icones.js.org/collection/ri)。在 Vue 组件中按需导入，例如 `import IconRefreshLine from '~icons/ri/refresh-line'`；构建时将 SVG 编入页面，运行时无需请求在线图标服务。

品牌标志使用 `resources/nexora-nexus-aurora-logo.png`。需要重新生成 macOS、Windows 和托盘图标时，安装 Pillow 后运行 `python3 scripts/create-icons.py`；页面页眉与侧栏使用生成的 `resources/icon.png`。

新增或修改前端界面时，请遵循 [前端 UI 开发规范](docs/frontend-ui-guidelines.md)。

常用检查：

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
node --experimental-strip-types --test tests/backend.test.mjs
node --test tests/branding.test.mjs
npm run build
```

## 内部安装包

在 Apple Silicon Mac 上安装 PyInstaller 和后端依赖后运行 `npm run dist:mac`；在 Windows x64 上运行 `npm run dist:win`。两个平台都需先执行 `npm install`。仓库中的 GitHub Actions 工作流可在 Windows runner 上构建并上传内部测试安装包。PyInstaller 必须在目标操作系统上分别构建服务程序。产物位于忽略 Git 的 `release/`。

内部包尚未签名或公证，macOS Gatekeeper 或 Windows SmartScreen 可能提示开发者身份未验证。macOS 首次扫描可能要求授予本地网络权限；Windows 应允许应用在专用网络通信。mDNS 受路由器或防火墙限制时，可改用手动地址连接。系统服务可从设置使用当前安装包升级；升级前会在系统服务目录生成数据库与证书的成组备份。具体恢复步骤见 [后端说明](backend/README.md)。跨 Windows 与 macOS 的真实设备组合、无人登录开机启动和恢复演练仍需按 [实机验收清单](docs/lan-host-acceptance.md) 检查。

## 安全与数据

- 首位管理员只能从服务端电脑本机创建；后续用户和角色由管理员管理。业务接口在服务端校验权限。
- 管理员可停用账号、重置密码并配置自定义角色的权限；修改密码后旧登录立即失效。系统始终保留至少一位启用的内置管理员。
- 服务端为每个实例生成独立 HTTPS 证书，私钥保存在数据目录。使用成组备份命令保存 `nexora.db`、`server.crt` 和 `server.key`；丢失私钥会要求客户端重新核验身份。
- 采购订单确认后可关联多张入库单，服务端按已确认入库量计算剩余数量并阻止超量；没有关联订单的旧入库流程继续可用。
- 采购退货关联已确认入库明细；确认时重新核对累计可退量和原入库仓库库存，并记录负向库存流水。原入库与订单已收数量保留，同时展示已退与净入库数量。未关联订单的历史入库无单价，退货金额显示待核对。
- 应收应付清单从已确认出库、入库及对应退货逐行计算，保留单据、物料、往来单位和确认人来源。按订单核对业务净额、收付款净额和未结金额；历史无价入库列为待核价，不计入已知应付总额。
- 财务员可按订单登记客户收款、供应商付款及退货后的退款，保存外部参考号和操作人。金额超出未结或可退余额会被拒绝；录错的记录通过新冲销记录更正，原记录不删除。当前是手工登记，不会自动连接银行账户或确认资金实际到账。
- 生产计划员可建立 BOM 草稿并启用版本；同一成品只允许一个启用版本，启用时阻止物料循环引用。工单创建时固定 BOM 版本、目标产量及组件需求。下达后可分批建领料单，仓库员确认时重新核对剩余需料和源仓库存，写入可追溯的负向库存流水；已确认领料不能取消。退料更正、完工入库、质检与成本归集仍待实现。
- 销售订单可分批出库；确认出库时在同一写事务中检查订单剩余数量和指定仓库的可用库存，记录带单据来源的负库存流水。
- 销售退货关联已确认出库明细；确认时重新核对累计可退量，在所选仓库记录正库存流水。原出库记录保留，订单另外显示已退与净交付数量。退货金额按原销售单价展示，并计入应收来源清单的负向调整；实际退款需另行登记。
- 一张入库单、调拨单或盘点单只允许确认一次。确认状态与库存流水在同一个事务中写入，当前库存可按仓库或全部仓库从流水汇总；调拨前检查来源仓库可用量。盘点在建单时保存账面量，确认前如有库存变化须重新盘点。
- 切换服务端会退出当前账号；不同服务端的数据保持独立，不会自动合并。

## English summary

Nexora ERP currently supports a LAN host and connected desktop clients, with FastAPI, SQLite, HTTPS certificate pinning, user and role administration, purchase orders with partial receipts and linked returns, sales orders with partial shipments and linked returns, versioned production BOMs, work orders and partial material issues, a source-linked receivables/payables list, multi-warehouse stock, transfers, stocktakes, and stock movements. A host can be created locally, discovered with mDNS, or connected by address. Packaged hosts use an OS service; remote clients require a live connection. Payment records are entered manually and reconciled to orders. Posted material issues consume warehouse stock; returns, finished goods receipts and costing remain future work. Offline synchronization and MySQL are future work. Internal macOS Apple Silicon and Windows x64 packaging scripts are included. Cross-platform device acceptance remains pending.
