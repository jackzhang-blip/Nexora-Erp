# Nexora FastAPI 服务

需要 Python 3.11+。开发环境从仓库根目录安装依赖：

```bash
python3 -m pip install -r backend/requirements-dev.txt
```

开发模式的桌面客户端在“新建服务端”时临时启动 `app.server`，并传入 SQLite 数据目录、实例名称和端口。安装版会复制打包后的服务程序到系统数据目录，注册 Windows 服务或 macOS LaunchDaemon；服务独立于桌面窗口和登录会话。单独调试服务时，可在仓库根目录运行：

```bash
cd backend
python3 -m app.server --data-dir /tmp/nexora-dev-data --name '开发服务端' --port 8000
```

正式数据请选持久化目录，不要使用临时目录。服务入口会迁移数据库、生成或复用实例证书，并通过 HTTPS 监听局域网。`GET /api/v1/health` 说明进程和数据库可用；`GET /api/v1/server/info` 提供公开的实例名称、身份、版本和初始化状态。

## 初始化与权限

只有来自本机环回地址的请求可调用 `POST /api/v1/setup/admin` 创建首位管理员。管理员密码至少 12 位。服务端已有用户时，该接口返回冲突；局域网设备不能抢注管理员。内置管理员、采购员、销售员、仓库员、查看员、财务员、生产计划员七种角色，权限在后端逐项校验。

管理员可通过 `/api/v1/users` 创建用户、调整角色，通过 `/api/v1/users/{id}/status` 启用或停用账号，并通过 `/api/v1/users/{id}/reset-password` 重置密码。`/api/v1/permissions` 列出固定权限代码；`/api/v1/roles` 可创建自定义角色，`/api/v1/roles/{code}` 可修改其授权范围。内置角色只读，最后一位启用的内置管理员不可停用或撤权。账号停用、管理员重置密码以及用户自行调用 `/api/v1/auth/change-password` 后，相关旧会话立即失效。角色和权限变化对现有会话立即生效。

物料、供应商和客户资料、采购订单与分批入库及退货、销售订单与分批出库及退货、入库单草稿、确认入库、多仓库库存、仓库调拨、库存盘点及库存流水已实现。确认入库、出库、退货、调拨或有差异的盘点会在单个事务中生成库存流水；重复确认返回冲突。所有数据由服务端 SQLite 保存，远程客户端没有离线副本或自动同步。

## 采购订单

`POST /api/v1/purchase-orders` 创建含供应商、物料、数量与单价的草稿；`POST /api/v1/purchase-orders/{id}/confirm` 确认后才能关联入库单；未入库的订单可调用 `/cancel` 取消。`GET /api/v1/purchase-orders` 返回订单金额、每行已入库与剩余数量。金额按每行数量乘单价后四舍五入到分；当前只按人民币展示。创建、确认和取消分别需要 `purchase_order.create`、`purchase_order.confirm`、`purchase_order.cancel` 权限。

新入库单可选填 `purchase_order_id`。服务端核对供应商、物料及剩余数量，确认入库时在同一写事务内重新核算并更新订单为“部分入库”或“全部入库”，防止多个草稿使订单超量。旧入库单没有采购订单关联，仍可正常确认。已入库订单不可取消。

`POST /api/v1/purchase-returns` 创建采购退货草稿，指定已确认的原入库单、入库明细、数量和原因。`GET /api/v1/purchase-returns` 查看记录；`POST /api/v1/purchase-returns/{id}/post` 确认退货，`/cancel` 取消草稿。服务端在建单和确认时核对累计可退量；确认时在同一写事务内核对原入库仓库余额并写入负向库存流水。若货物已调走，须先调回原仓库。原入库流水与订单状态不修改，另展示已退及净入库量。关联采购订单时按原单价展示退货金额；历史自由入库无单价则金额为空，待业务核对。应付来源清单会显示退货负向调整；实际退款需在财务页另行登记。采购员可创建及取消草稿，仓库员可创建、确认及取消，管理员可执行全部操作；已确认退货不能直接取消。

## 应收应付来源

`GET /api/v1/finance/receivables-payables` 逐行列出已确认销售出库形成的应收、采购入库形成的应付及销售、采购退货形成的负向调整。每笔记录包含往来单位、订单、来源单据与明细、物料、数量、原单价、确认人和确认时间。金额按每行数量乘原单价四舍五入到分，币种暂固定为人民币。草稿与取消单不产生金额；升级前的已确认单据同样从原记录推导，无需改写历史。没有采购订单单价的入库及其退货标记为待核价，不计入已知应付总额。此接口需要 `finance.view`，仅内置管理员和财务员默认拥有；其他角色需管理员显式授权。当前合计是业务净额；订单级收付款和未结金额由下述独立记录计算，税费和总账尚未实现。

`GET /api/v1/finance/overview` 在同一读取事务中返回金额来源、订单余额和收付款记录，供桌面工作台显示。`GET /api/v1/finance/accounts` 也可单独按已发生业务的订单查询业务净额、收付款净额、未结金额和来源行编号；负未结额表示需退款的贷方余额。`GET /api/v1/finance/payment-records` 返回全部手工收付款与冲销记录。`POST /api/v1/finance/payment-records` 以 `kind`（`receivable` 或 `payable`）、`order_id`、`action`（`settlement` 收款/付款或 `refund` 退款）、正金额、外部 `reference` 和可选 `note` 登记。金额最多两位小数，不得超过当前订单未结金额或贷方余额；写事务同时核对余额，防止并行超额。同一订单、类别和动作的参考号不得重复。`POST /api/v1/finance/payment-records/{id}/reverse` 以原因新增等额反向记录；原记录保留，且只能冲销一次。查看需要 `finance.view`，登记和冲销分别需要 `finance.record`、`finance.reverse`；管理员和财务员默认拥有。系统仅记录人工录入的资金事实，不连接银行，也不自动证明资金已到账；无采购订单单价的旧入库目前无法在系统内登记对应付款，需后续补价流程。

## 生产 BOM

`POST /api/v1/boms` 创建成品物料的 BOM 草稿，记录基准产出数量、组件物料及基准用量；同一物料不能重复作为组件，也不能直接作为自身组件。服务端在写事务中按成品分配递增版本号。`GET /api/v1/boms` 返回含物料名称的全部历史版本；`POST /api/v1/boms/{id}/activate` 启用草稿，`/retire` 停用启用版本，`/cancel` 取消草稿。每个成品只允许一个启用版本，启用时检查其他启用 BOM 的组件链，阻止循环引用。停用和取消后的内容保留审计；修订需新建版本，不能改写历史。查看、创建、启用、停用和取消分别要求 `production.view`、`bom.create`、`bom.activate`、`bom.retire`、`bom.cancel`。管理员和生产计划员可管理，仓库员可查看。BOM 不影响库存。

## 生产工单

`POST /api/v1/work-orders` 使用启用的 BOM、目标产量及目标仓库创建草稿。服务端在写事务内固定 BOM 版本引用，并按目标产量与 BOM 基准产量计算每个组件的需求，向上取整到库存的三位精度。`GET /api/v1/work-orders` 返回全部工单及需料快照；`POST /api/v1/work-orders/{id}/release` 下达草稿，BOM 已停用时拒绝下达，须取消草稿并按新版本建单；`/cancel` 可取消未发料的草稿或已下达工单。旧工单在 BOM 换版后仍保留原组件和数量。查看要求 `production.view`，创建、下达、取消分别要求 `work_order.create`、`work_order.release`、`work_order.cancel`；管理员与生产计划员默认拥有，仓库员可查看。此阶段不扣料、不锁定库存、不产生成品入库或成本；领料、完工、质检及成本归集尚未实现。

## 多仓库库存与调拨

数据库升级时自动建立 `MAIN` 主仓库，旧入库单和历史流水归入主仓库。新入库单可指定 `warehouse_id`；旧客户端省略时仍入主仓库。`GET /api/v1/warehouses` 查看仓库，`POST /api/v1/warehouses` 创建仓库。`GET /api/v1/stock` 返回所有仓库合计，添加 `warehouse_id` 查询参数可查看指定仓库；`GET /api/v1/movements` 返回带仓库、单据来源和操作者的有符号流水。

`POST /api/v1/transfers` 创建调拨草稿，`POST /api/v1/transfers/{id}/post` 确认调拨。确认时在写事务内检查来源仓库库存，再生成等额出库与入库流水；库存不足、重复确认均返回 409。已确认流水不可直接编辑。仓库管理、调拨创建和确认分别要求 `warehouse.manage`、`transfer.create`、`transfer.post` 权限；查看仍要求 `inventory.view`。

`POST /api/v1/stocktakes` 创建盘点草稿，保存指定仓库各物料的账面快照与实盘量；`GET /api/v1/stocktakes` 查看历史，`POST /api/v1/stocktakes/{id}/post` 确认差异，`/cancel` 取消草稿。确认时在写事务内重新核对账面量及最后一笔流水；若期间发生入库、出库或调拨，即使余额相抵未变也返回 409，须取消旧草稿并重新盘点。非零差异生成带盘点单、明细和操作者来源的有符号库存流水；零差异不生成流水。已确认盘点不可取消，后续错误须另建更正单。创建、确认、取消分别要求 `stocktake.create`、`stocktake.post`、`stocktake.cancel`，查看要求 `inventory.view`。

## 销售订单、出库与退货

`POST /api/v1/customers` 创建客户资料，`GET /api/v1/customers` 查询。`POST /api/v1/sales-orders` 创建包含客户、物料、数量及单价的草稿；`/confirm` 确认后才能出库，未出库订单可调用 `/cancel` 取消。`GET /api/v1/sales-orders` 返回金额、每行已出库及剩余数量。金额按每行数量乘单价后四舍五入到分，目前仅按人民币展示；税费、折扣与应收款尚未计算。

`POST /api/v1/shipments` 从已确认订单创建出库草稿并指定仓库；`POST /api/v1/shipments/{id}/post` 确认出库，`/cancel` 取消草稿。确认时在同一写事务内重新核对订单剩余量与仓库库存，写入带订单、出库单明细和操作者来源的负库存流水，并更新订单为部分或全部出库。库存不足、超量、重复确认返回 409。已出库不可取消。销售单据查看要求 `sales.view`，客户管理要求 `customer.manage`；销售订单创建、确认、取消和出库单创建、确认、取消分别由 `sales_order.*`、`shipment.*` 权限控制。销售员可创建订单和出库草稿，仓库员可确认出库，管理员可执行全部操作。

`POST /api/v1/sales-returns` 创建退货草稿，必须指定已确认的原出库单、该单的出库明细及数量、退回仓库与原因。`GET /api/v1/sales-returns` 查询退货记录；`POST /api/v1/sales-returns/{id}/post` 确认，`/cancel` 取消草稿。创建及确认时均核对原出库数量减去已确认退货数量；确认在一个写事务中写入正向库存流水，两个并行草稿无法累计退超。原出库流水与订单的已出库状态不被改写；订单和出库明细会显示已退、净交付或可退数量。退货金额沿用原销售单价展示，应收来源清单会显示退货负向调整；实际退款需在财务页另行登记。销售员可创建及取消草稿，仓库员可创建、确认及取消，管理员可执行全部操作；已确认退货不能直接取消。

## 数据与证书

数据库路径由桌面程序设置为所选数据目录下的 `nexora.db`。独立运行或测试时可以用 `NEXORA_DB_PATH` 指定完整路径。服务端身份随数据库保存；证书和私钥位于相同数据目录的 `server.crt`、`server.key`。如果证书与数据库实例不匹配，服务拒绝启动。备份和恢复时应把整个目录作为一组保留。

服务端证书为每个实例独立生成的自签名证书。客户端首次连接时应通过服务端电脑或其他可信渠道核对 SHA-256 指纹；此后客户端固定该证书。当前设计只供单家公司内部局域网使用，不开放公网连接。

服务进程自行发布 `_nexora._tcp` 局域网发现记录；桌面窗口不承担广播。网卡尚未就绪或地址变化时会重试，广播失败时仍可使用手动地址连接。

## 固定主机管理与升级

安装版的桌面设置提供系统服务状态、手动启停和使用当前安装包升级的入口。首次安装和手动启停需要操作系统管理员授权。服务配置位于 Windows `%PROGRAMDATA%\Nexora ERP\host.json` 或 macOS `/Library/Application Support/Nexora ERP/host.json`；其中不保存管理员账号密码。Windows 安装时会给 LocalSystem 授予所选实例数据目录及现有文件的访问权限，同时保留该目录原有的访问规则，以便服务在用户退出后继续使用数据库和证书。无控制台服务的运行日志写入同一系统目录的 `logs/host.out.log`，启动异常写入 `logs/host.err.log`；两者仅允许系统账户与管理员访问。旧版由 Electron 持有的主机在下一次点击“启动本机服务”时迁移到系统服务，并沿用原数据目录及证书。

升级先停服务，在上述系统目录的 `backups/` 中生成数据库与证书的成组备份，然后替换程序；程序替换或重新启动失败会恢复上一份程序。若新版已经变更数据库结构，程序回退后可能还需使用升级前备份恢复数据库。恢复应先停止服务，再使用下面的 `restore` 命令恢复到新的目录，核验实例与证书后把 `host.json` 的 `data_dir` 指向新目录，再启动服务。请保留原目录作为额外回退点。Windows 和 macOS 的开机及升级流程仍需真实设备验收。

## 备份与恢复

从仓库根目录运行以下命令；打包后的 `nexora-server` 可直接使用相同的 `backup`、`restore` 子命令：

```bash
PYTHONPATH=backend python3 -m app.backup backup --data-dir /path/to/instance --output /path/to/instance.nexora-backup
PYTHONPATH=backend python3 -m app.backup restore --archive /path/to/instance.nexora-backup --data-dir /path/to/new-instance
```

备份使用 SQLite 在线快照，并把数据库、证书和私钥放在同一归档中；归档含敏感业务数据及私钥，应存放在受控位置。恢复会校验哈希、数据库完整性和证书身份，只写入尚不存在的新目录，不覆盖运行中的原实例。恢复后还需让服务端配置指向新目录，并在启动前确认旧服务已停止。

## 测试

从仓库根目录运行：

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

测试覆盖身份持久化、远程首次管理员抢注拒绝、角色越权拒绝、账号停用与会话失效、自定义角色授权、最后管理员保护、旧数据库迁移、采购订单分批入库与超量拦截、采购退货累计数量与库存不足回滚、销售订单分批出库与库存不足拦截、销售退货累计数量与权限、应收应付来源和角色授权、收付款限额与冲销及退货退款、BOM 版本与循环引用、工单需料快照与下达状态、多仓库调拨与库存不足拦截、盘点快照与差异流水、入库只确认一次、库存流水、成组备份恢复、发现广播与系统服务安装升级回退。
