# FastAPI 基础服务

需要 Python 3.11+。从仓库根目录执行（PowerShell）：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

macOS / Linux 将 `backend/.venv/Scripts/python.exe` 替换为 `backend/.venv/bin/python`。
仅运行服务时可以安装 `backend/requirements.txt`，无需开发依赖。

另开终端，在仓库根目录运行 `npm install`、`npm run dev`，桌面启动页会自动检查连接。
停止后端后点击“重新检查连接”，页面会显示未连接；重新启动后再次检查即可恢复。
桌面应用目前不负责启动或停止 Python 服务。

- 健康接口：`GET http://127.0.0.1:8000/api/v1/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`
- OpenAPI：`http://127.0.0.1:8000/openapi.json`
- 响应：`{"status":"ok","service":"nexora-api","version":"0.1.0"}`

健康接口仅表示进程存活；尚未接入数据库、鉴权、业务接口或同步功能。
开发服务默认只监听本机。

## 自定义连接地址

在启动桌面应用的 PowerShell 中设置：

```powershell
$env:NEXORA_API_URL = 'http://127.0.0.1:8001'
npm run dev
```

同时将 Uvicorn 的 `--port` 改为 `8001`。地址应为 HTTP(S) 源站，接口路径固定为
`/api/v1/health`；无需在地址后追加路径。环境变量由 Electron 主进程读取，不自动加载 `.env`。
主进程请求限制为 5 秒，拒绝重定向并校验响应结构；页面仅通过预加载接口查询健康状态，
不能传入 URL。浏览器预览会提示使用桌面端；此流程不需要放开 CORS。

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
