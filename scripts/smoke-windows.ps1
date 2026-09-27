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

# CI 运行器以管理员身份执行时，验证 SCM 接管、停止和重新启动打包后的服务。
$request = Join-Path $env:RUNNER_TEMP 'nexora-service-request.json'
$serviceData = Join-Path $env:RUNNER_TEMP 'nexora-system-service-data'
@{ name = 'CI 固定主机'; data_dir = $serviceData; port = 18762 } | ConvertTo-Json | Set-Content -Path $request -Encoding utf8
$serviceStartedAt = Get-Date
& $service install --request $request --source (Split-Path $service -Parent)
if ($LASTEXITCODE -ne 0) {
  # 安装命令回滚服务注册后，保留系统事件记录以区分权限、程序路径和进程内部错误。
  $serviceLog = Join-Path $env:ProgramData 'Nexora ERP/logs/host.err.log'
  if (Test-Path $serviceLog) { Get-Content $serviceLog -Tail 80 | Write-Host }
  Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Service Control Manager'; StartTime = $serviceStartedAt } -ErrorAction SilentlyContinue |
    Select-Object -First 8 TimeCreated, Id, Message | Format-List | Out-String | Write-Host
  # 用系统自带程序验证当前运行器是否允许 SCM 启动新建服务，退出码仅作诊断。
  & sc.exe create NexoraCIProbe 'binPath=' "$env:WINDIR\System32\cmd.exe /c exit 0" 'start=' 'demand'
  & sc.exe start NexoraCIProbe
  Write-Host "SCM probe start exit code: $LASTEXITCODE"
  & sc.exe delete NexoraCIProbe
  throw 'Windows 系统服务安装失败。'
}
try {
  $running = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $status = (& $service status | ConvertFrom-Json)
    if ($status.running) { $running = $true; break }
    Start-Sleep -Milliseconds 250
  }
  if (-not $running) {
    # 进程可能已退出；先保留状态、服务自身日志和系统事件，再报告检查失败。
    & sc.exe queryex NexoraERPHost
    $serviceLog = Join-Path $env:ProgramData 'Nexora ERP/logs/host.err.log'
    if (Test-Path $serviceLog) { Get-Content $serviceLog -Tail 80 | Write-Host }
    Get-WinEvent -FilterHashtable @{ LogName = 'Application'; StartTime = $serviceStartedAt } -ErrorAction SilentlyContinue |
      Select-Object -First 8 TimeCreated, Id, ProviderName, Message | Format-List | Out-String | Write-Host
    throw 'SCM 没有保持固定主机运行。'
  }
  & $service stop
  if ($LASTEXITCODE -ne 0) { throw 'Windows 系统服务停止失败。' }
  & $service start
  if ($LASTEXITCODE -ne 0) { throw 'Windows 系统服务重新启动失败。' }
} finally {
  # 服务已自行退出时不再执行 stop，保留最初的失败信息。
  if ((Get-Service -Name NexoraERPHost -ErrorAction SilentlyContinue).Status -eq 'Running') { & $service stop }
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
