# FastAPI 基础服务

## 一次性开发环境准备

需要 Python 3.11+ 和 Node.js 22.12+。从仓库根目录执行（PowerShell）：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
npm install
```

macOS / Linux 将 `backend/.venv/Scripts/python.exe` 替换为 `backend/.venv/bin/python`。
仅运行服务时可以安装 `backend/requirements.txt`，无需开发依赖。

## 启动整个项目

```powershell
npm run dev
```

Electron 自动启动 FastAPI，等待健康检查通过后显示已连接，不需要另开终端启动后端。
`npm run build` 后的 `npm run preview` 也使用同一托管流程。
应用退出时关闭 Python 服务；macOS 关闭最后一个窗口会保留应用，使用退出命令时才停止后端。
后端异常退出后，点击“重新检查连接”会重新启动服务。
缺少运行环境、依赖安装失败或启动超时会显示可重试提示。

后端只监听 `127.0.0.1`，端口由操作系统自动分配，不依赖固定的 8000 端口。
每次启动先绑定端口，再启动 Uvicorn，避免端口竞争，也不会误连到其他项目的服务。
Electron 与 Python 通过标准输入管道关联生命周期：正常退出、开发重载或父进程终止后，
管道关闭会通知 Python 退出；同时监测 Electron 父进程，避免 Windows 继承句柄导致 EOF 延迟。
托管模式不启用 Uvicorn reload，修改 Python 后请重启桌面应用。

默认使用 `backend/.venv` 中的 Python；如需指定现有环境，可在启动前设置
`NEXORA_PYTHON` 为 Python 可执行文件的绝对路径。托管模式不使用 `NEXORA_API_URL`。
目前仓库只有开发/预览流程；未来生成安装包时，需要同时打包 Python 运行环境及 backend，
不能把开发机虚拟环境直接作为可分发运行时。

## 接口

- 健康接口：`GET /api/v1/health`
- Swagger 文档：`/docs`
- OpenAPI：`/openapi.json`
- 响应：`{"status":"ok","service":"nexora-api","version":"0.1.0"}`

健康检查仅表示进程存活；尚未接入数据库、鉴权、业务模块或同步功能。
单独调试接口时可选用以下命令（常规项目启动不需要此步骤）：

```powershell
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

此时可以访问 `http://127.0.0.1:8000/docs`，桌面端仍使用自己的托管实例。

## 验证

在 `backend` 目录执行：

```powershell
.venv/Scripts/python.exe -m pytest tests
```

在仓库根目录执行（Node.js 22.12+）：

```powershell
node --experimental-strip-types --test tests/backend.test.mjs
npm run build
```
