# Start qmt-quant Web workbench (API + Vite frontend).
# Usage:
#   .\scripts\start.ps1           # start both servers
#   .\scripts\start.ps1 -Install  # npm install before start
#   .\scripts\start.ps1 -Stop     # stop servers on ports 8788 / 5173

param(
    [switch]$NoBrowser,
    [switch]$Install,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WebDir = Join-Path $ProjectRoot "web"
$ApiPort = 8788
$WebPort = 5173

function Get-YamlValue {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return $null }
    foreach ($line in Get-Content $Path) {
        if ($line -match "^\s*$([regex]::Escape($Key)):\s*(.+?)\s*(#.*)?$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Get-QuantPython {
    $settingsPath = Join-Path $ProjectRoot "config\settings.yaml"
    $fromConfig = Get-YamlValue -Path $settingsPath -Key "quant_env"
    if ($fromConfig -and (Test-Path $fromConfig)) {
        return (Resolve-Path $fromConfig).Path
    }

    $venvPython = Join-Path $ProjectRoot ".venv-quant\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return (Resolve-Path $venvPython).Path
    }

    throw @"
未找到 quant-env Python。请任选其一：
  1. 在 config/settings.yaml 配置 python.quant_env
  2. 创建虚拟环境: py -3.12 -m venv .venv-quant
"@
}

function Test-PortInUse([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-PortListeners([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) { return 0 }

    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "已停止端口 $Port 上的进程 (PID $procId)"
        } catch {
            Write-Warning "无法停止 PID $procId : $_"
        }
    }
    return $pids.Count
}

function Wait-ForPort([int]$Port, [int]$TimeoutSec = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortInUse $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

if ($Stop) {
    $stopped = (Stop-PortListeners $ApiPort) + (Stop-PortListeners $WebPort)
    if ($stopped -eq 0) {
        Write-Host "没有在 $ApiPort / $WebPort 上运行的服务。"
    }
    exit 0
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "未找到 npm，请先安装 Node.js: https://nodejs.org/"
}

$Python = Get-QuantPython
Write-Host "项目目录: $ProjectRoot"
Write-Host "Python:   $Python"

if ($Install -or -not (Test-Path (Join-Path $WebDir "node_modules"))) {
    Write-Host "安装前端依赖 (npm install)..."
    Push-Location $WebDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install 失败 (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
}

if (Test-PortInUse $ApiPort) {
    Write-Warning "端口 $ApiPort 已被占用，跳过启动 API。可用 -Stop 先停止。"
} else {
    Write-Host "启动 API (http://127.0.0.1:$ApiPort)..."
    $apiCmd = "Set-Location '$ProjectRoot'; & '$Python' -m qmt_quant.cli serve api"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd | Out-Null
    if (-not (Wait-ForPort $ApiPort)) {
        throw "API 在 ${ApiPort} 端口启动超时，请查看 API 窗口中的报错。"
    }
}

if (Test-PortInUse $WebPort) {
    Write-Warning "端口 $WebPort 已被占用，跳过启动前端。"
} else {
    Write-Host "启动前端 (http://localhost:$WebPort)..."
    $webCmd = "Set-Location '$WebDir'; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $webCmd | Out-Null
    if (-not (Wait-ForPort $WebPort)) {
        throw "前端在 ${WebPort} 端口启动超时，请查看前端窗口中的报错。"
    }
}

Write-Host ""
Write-Host "qmt-quant 已启动："
Write-Host "  前端  http://localhost:$WebPort"
Write-Host "  API   http://127.0.0.1:$ApiPort"
Write-Host "停止服务: .\scripts\start.ps1 -Stop"

if (-not $NoBrowser) {
    Start-Process "http://localhost:$WebPort"
}
