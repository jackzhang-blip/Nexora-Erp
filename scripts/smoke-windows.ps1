$ErrorActionPreference = 'Stop'
$service = Join-Path $PWD 'release/win-unpacked/resources/backend-service/nexora-server.exe'
$desktop = Join-Path $PWD 'release/win-unpacked/Nexora ERP.exe'
if (-not (Test-Path $service) -or -not (Test-Path $desktop)) {
  throw 'Windows 安装包缺少桌面程序或 FastAPI 服务程序。'
}

# 在 CI 的临时目录启动打包后的真实服务，验证证书、数据库和 HTTPS 监听。
$dataDir = Join-Path $env:RUNNER_TEMP 'nexora-packaged-smoke'
$process = Start-Process -FilePath $service -ArgumentList @('--data-dir', "`"$dataDir`"", '--name', '"CI ERP"', '--port', '18751') -PassThru -WindowStyle Hidden
try {
  $healthy = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($process.HasExited) { throw '打包后的服务程序提前退出。' }
    try {
      $response = Invoke-RestMethod 'https://127.0.0.1:18751/api/v1/health' -SkipCertificateCheck -TimeoutSec 1
      if ($response.status -eq 'ok' -and $response.service -eq 'nexora-api') {
        $healthy = $true
        break
      }
    } catch { Start-Sleep -Milliseconds 250 }
  }
  if (-not $healthy) { throw '打包后的服务程序没有通过 HTTPS 健康检查。' }
} finally {
  if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
}

# 桌面程序也必须实际渲染首次进入页，不能只检查可执行文件存在。
$env:NEXORA_USER_DATA_DIR = Join-Path $env:RUNNER_TEMP 'nexora-desktop-smoke'
$desktopProcess = Start-Process -FilePath $desktop -ArgumentList '--remote-debugging-port=18752' -PassThru
try {
  node scripts/smoke-desktop.mjs http://127.0.0.1:18752
  if ($LASTEXITCODE -ne 0) { throw '桌面首次进入页检查失败。' }
} finally {
  if (-not $desktopProcess.HasExited) { Stop-Process -Id $desktopProcess.Id -Force }
}
