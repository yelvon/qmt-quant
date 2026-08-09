# Shared start/stop logic for qmt-quant (used by start.ps1 and start.sh)
param(
    [switch]$NoBrowser,
    [switch]$Install,
    [switch]$Stop,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WebDir = Join-Path $ProjectRoot "web"
$ApiPort = 8788
$WebPort = 5173
$LogDir = Join-Path $ProjectRoot "logs"

if ($Restart) {
    $Stop = $true
}

function Refresh-PathEnv {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
}

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

function Test-HttpReady([string]$Url, [int]$TimeoutSec = 15) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Stop-PortListeners([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) { return 0 }
    $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    $count = 0
    foreach ($procId in $procIds) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "已停止端口 $Port 上的进程 (PID $procId)"
            $count++
        } catch {
            Write-Warning "无法停止 PID ${procId}: $_"
        }
    }
    return $count
}

function Wait-PortFree([int]$Port, [int]$TimeoutSec = 20) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-PortInUse $Port)) { return $true }
        Start-Sleep -Milliseconds 300
    }
    return -not (Test-PortInUse $Port)
}

function Wait-ForService {
    param(
        [int]$Port,
        [string]$HealthUrl,
        [int]$TimeoutSec = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ($HealthUrl) {
            if (Test-HttpReady $HealthUrl) { return $true }
        } elseif (Test-PortInUse $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Ensure-PortFree([int]$Port) {
    if (Test-PortInUse $Port) {
        Stop-PortListeners $Port | Out-Null
        if (-not (Wait-PortFree $Port)) {
            throw "端口 $Port 仍被占用，无法启动服务"
        }
    }
}

function Start-ServiceWindow([string]$ScriptPath) {
    $psArgs = @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", $ScriptPath
    )
    Start-Process -FilePath "powershell.exe" -ArgumentList $psArgs -WorkingDirectory $ProjectRoot | Out-Null
}

if ($Stop) {
    $stopped = (Stop-PortListeners $ApiPort) + (Stop-PortListeners $WebPort)
    Wait-PortFree $ApiPort | Out-Null
    Wait-PortFree $WebPort | Out-Null
    if (-not $Restart) {
        if ($stopped -eq 0) {
            Write-Host "没有在 $ApiPort / $WebPort 上运行的服务。"
        } else {
            Write-Host "已停止 $ApiPort / $WebPort 上的服务。"
        }
        exit 0
    }
    Start-Sleep -Seconds 1
}

Refresh-PathEnv
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

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Ensure-PortFree $ApiPort
Write-Host "启动 API (http://127.0.0.1:$ApiPort)..."
$apiScript = Join-Path $PSScriptRoot "run-api.ps1"
Start-ServiceWindow $apiScript
if (-not (Wait-ForService -Port $ApiPort -HealthUrl "http://127.0.0.1:$ApiPort/docs")) {
    throw "API 启动失败或超时，请查看弹出的 API 窗口或 logs/api.log"
}
Write-Host "API 已就绪"

Ensure-PortFree $WebPort
Write-Host "启动前端 (http://localhost:$WebPort)..."
$webScript = Join-Path $PSScriptRoot "run-web.ps1"
Start-ServiceWindow $webScript
if (-not (Wait-ForService -Port $WebPort -HealthUrl "http://localhost:$WebPort/")) {
    throw "前端启动失败或超时，请查看弹出的前端窗口或 logs/web.log"
}
Write-Host "前端已就绪"

if (-not ((Test-HttpReady "http://127.0.0.1:$ApiPort/docs") -and (Test-HttpReady "http://localhost:$WebPort/"))) {
    throw "服务健康检查未通过，请查看 logs/ 或弹出的终端窗口"
}

Write-Host ""
Write-Host "qmt-quant 已启动："
Write-Host "  前端  http://localhost:$WebPort"
Write-Host "  API   http://127.0.0.1:$ApiPort"
Write-Host "停止服务: .\scripts\start.ps1 -Stop  或  ./scripts/start.sh --stop"

if (-not $NoBrowser) {
    Start-Process "http://localhost:$WebPort"
}
