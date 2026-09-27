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

只有来自本机环回地址的请求可调用 `POST /api/v1/setup/admin` 创建首位管理员。管理员密码至少 12 位。服务端已有用户时，该接口返回冲突；局域网设备不能抢注管理员。内置管理员、采购员、仓库员、查看员四种角色，权限在后端逐项校验。

管理员可通过 `/api/v1/users` 创建用户、调整角色，通过 `/api/v1/users/{id}/status` 启用或停用账号，并通过 `/api/v1/users/{id}/reset-password` 重置密码。`/api/v1/permissions` 列出固定权限代码；`/api/v1/roles` 可创建自定义角色，`/api/v1/roles/{code}` 可修改其授权范围。内置角色只读，最后一位启用的内置管理员不可停用或撤权。账号停用、管理员重置密码以及用户自行调用 `/api/v1/auth/change-password` 后，相关旧会话立即失效。角色和权限变化对现有会话立即生效。

物料和供应商资料、入库单草稿、确认入库、库存流水及当前库存已实现。确认入库会在单个事务中生成流水；重复确认返回冲突。所有数据由服务端 SQLite 保存，远程客户端没有离线副本或自动同步。

## 数据与证书

数据库路径由桌面程序设置为所选数据目录下的 `nexora.db`。独立运行或测试时可以用 `NEXORA_DB_PATH` 指定完整路径。服务端身份随数据库保存；证书和私钥位于相同数据目录的 `server.crt`、`server.key`。如果证书与数据库实例不匹配，服务拒绝启动。备份和恢复时应把整个目录作为一组保留。

服务端证书为每个实例独立生成的自签名证书。客户端首次连接时应通过服务端电脑或其他可信渠道核对 SHA-256 指纹；此后客户端固定该证书。当前设计只供单家公司内部局域网使用，不开放公网连接。

服务进程自行发布 `_nexora._tcp` 局域网发现记录；桌面窗口不承担广播。网卡尚未就绪或地址变化时会重试，广播失败时仍可使用手动地址连接。

## 固定主机管理与升级

安装版的桌面设置提供系统服务状态、手动启停和使用当前安装包升级的入口。首次安装和手动启停需要操作系统管理员授权。服务配置位于 Windows `%PROGRAMDATA%\Nexora ERP\host.json` 或 macOS `/Library/Application Support/Nexora ERP/host.json`；其中不保存管理员账号密码。Windows 安装时会给 LocalSystem 授予所选实例数据目录及现有文件的访问权限，同时保留该目录原有的访问规则，以便服务在用户退出后继续使用数据库和证书。服务启动异常会记录在同一系统目录的 `logs/host.err.log`，供管理员排查。旧版由 Electron 持有的主机在下一次点击“启动本机服务”时迁移到系统服务，并沿用原数据目录及证书。

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

测试覆盖身份持久化、远程首次管理员抢注拒绝、角色越权拒绝、账号停用与会话失效、自定义角色授权、最后管理员保护、入库只确认一次、库存流水、成组备份恢复、发现广播与系统服务安装升级回退。
