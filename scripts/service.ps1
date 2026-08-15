# Shared start/stop logic for qmt-quant (used by start.ps1 and start.sh)
param(
    [switch]$NoBrowser,
    [switch]$Install,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WebDir = Join-Path $ProjectRoot "web"
$ApiPort = 8788
$WebPort = 5173
$LogDir = Join-Path $ProjectRoot "logs"

function Initialize-ScriptConsole {
    try {
        $null = cmd /c chcp 65001
    } catch {
        # Non-console hosts may reject chcp.
    }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    try {
        [Console]::OutputEncoding = $utf8
        [Console]::InputEncoding = $utf8
    } catch {
        # Git Bash / older hosts may not support console encoding changes.
    }
    $script:OutputEncoding = $utf8
}

function Write-SubprocessLines {
    param([object[]]$Lines)
    foreach ($line in $Lines) {
        if ($null -eq $line) { continue }
        $text = ($line.ToString() -replace "`r", "").TrimEnd()
        if ($text.Length -gt 0) {
            [Console]::Out.WriteLine($text)
        }
    }
}

function Write-Host {
    param(
        [Parameter(Position = 0)]
        [object]$Object,
        [switch]$NoNewline
    )
    $text = if ($null -eq $Object) { "" } else { [string]$Object }
    if ($NoNewline) {
        [Console]::Out.Write($text)
    } else {
        [Console]::Out.WriteLine($text)
    }
}

Initialize-ScriptConsole

$postgresNativePath = Join-Path $PSScriptRoot "postgres-native.ps1"
$postgresNativeScript = [System.IO.File]::ReadAllText(
    $postgresNativePath,
    [System.Text.UTF8Encoding]::new($false)
)
. ([ScriptBlock]::Create($postgresNativeScript))

function Invoke-ExternalQuiet {
    param(
        [string]$Executable,
        [string[]]$Args = @()
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        # Do not pipe native commands — piping resets $LASTEXITCODE to 0.
        & $Executable @Args 1>$null 2>$null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Ensure-DockerEngineReady {
    Add-DockerToPath

    if (Test-DockerDaemonReady) { return $true }

    if (Test-DockerDesktopInstalled) {
        Start-DockerDesktopIfInstalled | Out-Null
    } else {
        Try-Install-DockerDesktop | Out-Null
    }

    Add-DockerToPath
    if (Test-DockerDaemonReady) { return $true }

    Write-Host "等待 Docker 引擎启动（最多 2 分钟）..."
    if (Wait-DockerDaemonReady -TimeoutSec 120) { return $true }

    throw @"
Docker Desktop 已安装，但引擎尚未就绪（docker ps 失败）。
请从开始菜单打开 Docker Desktop，等待托盘图标显示 Engine running 后重试：
  ./scripts/start.sh
Windows ARM64 首次使用可能还需：完成 Docker 向导、启用 WSL2、或重启电脑。
若 Docker Desktop 报 unable to start，请先在 Docker 设置中修复引擎后再运行本脚本。
"@
}

function Test-DockerDesktopInstalled {
    return Test-Path (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe")
}

if ($Restart) {
    $Stop = $true
}

function Refresh-PathEnv {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
        [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Add-DockerToPath {
    Refresh-PathEnv
    $dockerBins = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"),
        (Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\resources\bin")
    )
    foreach ($bin in $dockerBins) {
        if ((Test-Path $bin) -and (($env:Path -split ';') -notcontains $bin)) {
            $env:Path = "$bin;$env:Path"
        }
    }
}

function Test-DockerDaemonReady {
    param([int]$TimeoutSec = 15)
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }

    $path = $env:Path
    $job = Start-Job -ScriptBlock {
        param($DockerPath)
        $env:Path = $DockerPath
        $ErrorActionPreference = "SilentlyContinue"
        & docker ps -q 1>$null 2>$null
        return $LASTEXITCODE
    } -ArgumentList $path

    $completed = Wait-Job -Job $job -Timeout $TimeoutSec
    if (-not $completed) {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -ErrorAction SilentlyContinue
        return $false
    }

    $exitCode = Receive-Job -Job $job
    Remove-Job -Job $job -ErrorAction SilentlyContinue
    return ($exitCode -eq 0)
}

function Wait-DockerDaemonReady {
    param([int]$TimeoutSec = 180)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastHint = [datetime]::MinValue
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerDaemonReady) { return $true }
        if (((Get-Date) - $lastHint).TotalSeconds -ge 15) {
            Write-Host "仍在等待 Docker 引擎就绪..."
            $lastHint = Get-Date
        }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Start-DockerDesktopIfInstalled {
    Add-DockerToPath
    if (Test-DockerDaemonReady) { return $true }

    $dockerDesktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) { return $false }

    Write-Host "Docker 已安装但未运行，正在启动 Docker Desktop..."
    Write-Host "（首次启动可能需 1-3 分钟，请等待托盘图标变为 Engine running）"
    Start-Process $dockerDesktop | Out-Null
    if (Wait-DockerDaemonReady -TimeoutSec 90) {
        Write-Host "Docker Desktop 已就绪"
        return $true
    }
    return $false
}

function Try-Install-DockerDesktop {
    Add-DockerToPath
    if (Test-DockerDaemonReady) { return $true }

    if (Test-DockerDesktopInstalled) {
        return Start-DockerDesktopIfInstalled
    }

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }

    Write-Host "未检测到 Docker，尝试通过 winget 安装 Docker Desktop..."
    Write-Host "（约 537MB；Git Bash 下 winget 进度条可能显示乱码，属正常现象）"
    Write-Host "（可能需要管理员确认；安装完成后会自动尝试启动）"
    winget install --id Docker.DockerDesktop -e `
        --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { return $false }

    Add-DockerToPath
    Start-Sleep -Seconds 5
    return Start-DockerDesktopIfInstalled
}

function Ensure-Config {
    $settingsPath = Join-Path $ProjectRoot "config\settings.yaml"
    $examplePath = Join-Path $ProjectRoot "config\settings.yaml.example"

    if (-not (Test-Path $settingsPath)) {
        if (-not (Test-Path $examplePath)) {
            throw "未找到 config/settings.yaml 或 config/settings.yaml.example"
        }
        Copy-Item $examplePath $settingsPath
        Write-Host "已从模板创建 config/settings.yaml"
        return
    }

    $lines = [System.Collections.Generic.List[string]]@()
    $lines.AddRange([string[]](Get-Content $settingsPath -Encoding UTF8))
    $hasDbUrl = $false
    $changed = $false

    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*db_url:') { $hasDbUrl = $true }
        if ($lines[$i] -match '^\s*db_path:') {
            if (-not $hasDbUrl) {
                $lines[$i] = '  db_url: "postgresql://qmt:qmt@localhost:5432/qmt_quant"'
                $hasDbUrl = $true
                $changed = $true
            }
        }
    }

    if (-not $hasDbUrl) {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^\s*data:\s*$') {
                $lines.Insert($i + 1, '  db_url: "postgresql://qmt:qmt@localhost:5432/qmt_quant"')
                $changed = $true
                break
            }
        }
    }

    if (Repair-YamlQuotedWindowsPaths -Lines $lines) {
        $changed = $true
    }

    if ($changed) {
        Set-Content -Path $settingsPath -Value $lines -Encoding UTF8
        Write-Host "已更新 config/settings.yaml"
    }
}

function Format-YamlQuotedValue {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    $escaped = $Value -replace '\\', '\\\\'
    return "`"$escaped`""
}

function Repair-YamlQuotedWindowsPaths {
    param([System.Collections.Generic.List[string]]$Lines)

    $changed = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -notmatch '^(?<indent>\s+)(?<key>\w+):\s*"(?<val>[^"]*)"\s*(?<comment>#.*)?$') {
            continue
        }
        $val = $Matches["val"]
        if ($val -notmatch '\\' -or $val -match '\\\\') { continue }

        $suffix = if ($Matches["comment"]) { " $($Matches['comment'])" } else { "" }
        $Lines[$i] = "$($Matches['indent'])$($Matches['key']): $(Format-YamlQuotedValue $val)$suffix"
        $changed = $true
    }
    return $changed
}

function Set-YamlValue {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key,
        [string]$Value
    )
    if (-not (Test-Path $Path)) { return }
    $lines = [System.Collections.Generic.List[string]]@()
    $lines.AddRange([string[]](Get-Content $Path -Encoding UTF8))
    $inSection = $false
    $updated = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^$([regex]::Escape($Section)):\s*$") {
            $inSection = $true
            continue
        }
        if ($inSection -and $lines[$i] -match '^\S') { $inSection = $false }
        if ($inSection -and $lines[$i] -match "^\s+$([regex]::Escape($Key)):") {
            $lines[$i] = "  ${Key}: $(Format-YamlQuotedValue $Value)"
            $updated = $true
            break
        }
    }
    if (-not $updated) { return }
    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

function Find-X64Python312 {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312-x64\python.exe"
    if (Test-Path $candidate) {
        return (Resolve-Path $candidate).Path
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $null }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        foreach ($line in (& py -0p 2>$null)) {
            if ($line -match 'Python312-x64\\python\.exe' -and $line -match '(\S:\\.+python\.exe)') {
                return (Resolve-Path $Matches[1]).Path
            }
        }
    } finally {
        $ErrorActionPreference = $prev
    }
    return $null
}

function Resolve-QuantPythonPath {
    param([string]$PythonPath)
    if (-not $PythonPath) { return $PythonPath }
    if ($PythonPath -notmatch 'arm64|ARM64') { return $PythonPath }

    $x64Sibling = $PythonPath -replace 'arm64', 'x64' -replace 'ARM64', 'x64'
    if ((Test-Path $x64Sibling) -and ($x64Sibling -ne $PythonPath)) {
        return (Resolve-Path $x64Sibling).Path
    }

    $x64 = Find-X64Python312
    if ($x64) { return $x64 }
    return $PythonPath
}

function Ensure-QuantPython {
    $settingsPath = Join-Path $ProjectRoot "config\settings.yaml"
    $fromConfig = Get-YamlValue -Path $settingsPath -Key "quant_env"
    if ($fromConfig -and (Test-Path $fromConfig)) {
        $resolved = Resolve-QuantPythonPath (Resolve-Path $fromConfig).Path
        if ($resolved -ne (Resolve-Path $fromConfig).Path) {
            Write-Host "Windows ARM64: quant_env 已切换为 x64 Python（psycopg / PostgreSQL 需要）"
            Write-Host "  $($fromConfig) -> $resolved"
            Set-YamlValue -Path $settingsPath -Section "python" -Key "quant_env" -Value $resolved
        }
        return $resolved
    }

    $venvPython = Join-Path $ProjectRoot ".venv-quant\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return (Resolve-Path $venvPython).Path
    }

    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw @"
未找到 quant-env Python。请任选其一：
  1. 安装 Python 3.12+ 并执行: py -3.12 -m venv .venv-quant
  2. 在 config/settings.yaml 配置 python.quant_env
"@
    }

    Write-Host "创建 quant-env 虚拟环境 (.venv-quant)..."
    Push-Location $ProjectRoot
    try {
        $created = $false
        $venvArgs = @(
            @("-3.12-x64"),
            @("-3.12"),
            @("-3.13"),
            @("-3.11"),
            @()
        )
        foreach ($verArgs in $venvArgs) {
            if ($verArgs.Count -gt 0) {
                & py @verArgs -m venv .venv-quant 2>$null
            } else {
                & py -m venv .venv-quant 2>$null
            }
            if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) {
                $created = $true
                break
            }
        }
        if (-not $created) {
            & py -m venv .venv-quant
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
                throw "py -m venv .venv-quant 失败"
            }
        }
    } finally {
        Pop-Location
    }

    $resolved = (Resolve-Path $venvPython).Path
    Set-YamlValue -Path $settingsPath -Section "python" -Key "quant_env" -Value $resolved
    Write-Host "quant-env: $resolved"
    return $resolved
}

function Test-PythonImports {
    param([string]$Python, [string]$Expression)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $Python -c $Expression 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-QuantPythonIsArm64Native {
    param([string]$Python)
    return $Python -match 'arm64|ARM64'
}

function Install-StartupPythonDependencies {
    param([string]$Python)

    Invoke-PipInstall $Python @("install", "-U", "pip", "wheel")

    if (Test-QuantPythonIsArm64Native $Python) {
        Write-Host "检测到 ARM64 Python，安装启动依赖（跳过 psycopg-binary / vectorbt）..."
        Invoke-PipInstall $Python @("install", "-e", ".", "--no-deps")
        Invoke-PipInstall $Python @(
            "install",
            "typer>=0.12",
            "pyyaml>=6.0",
            "pandas>=2.0",
            "numpy>=1.24",
            "psycopg>=3.1",
            "fastapi>=0.110",
            "uvicorn[standard]>=0.27",
            "websockets>=12.0"
        )
    } else {
        Invoke-PipInstall $Python @("install", "-e", ".[web]")
    }
}

function Invoke-PipInstall {
    param(
        [string]$Python,
        [string[]]$PipArgs
    )
    $env:PIP_PROGRESS_BAR = "on"
    $env:PIP_DISABLE_PIP_VERSION_CHECK = "1"
    & $Python -m pip @PipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip install 失败 (exit $LASTEXITCODE): pip $($PipArgs -join ' ')"
    }
}

function Ensure-PythonDependencies {
    param(
        [string]$Python,
        [switch]$Force
    )
    $setupDir = Join-Path $ProjectRoot ".setup"
    $startupMarker = Join-Path $setupDir "startup-deps.ok"
    $fullMarker = Join-Path $setupDir "quant-deps.ok"
    $reqFile = Join-Path $ProjectRoot "requirements-quant.txt"
    $projFile = Join-Path $ProjectRoot "pyproject.toml"
    $startupReady = Test-PythonImports $Python "import qmt_quant, fastapi, uvicorn, psycopg"
    $fullReady = Test-PythonImports $Python "import qmt_quant, fastapi, vectorbt"

    if ($startupReady -and -not $Force) {
        Write-Host "Python 启动依赖已就绪，跳过安装"
        if (-not (Test-Path $startupMarker)) {
            New-Item -ItemType Directory -Force -Path $setupDir | Out-Null
            Set-Content -Path $startupMarker -Value (Get-Date -Format o) -Encoding UTF8
        }
        if (-not $fullReady) {
            Write-Host "提示: 研究/回测功能需 vectorbt，完整依赖请执行: .\scripts\start.ps1 -Install"
        }
        return
    }

    Push-Location $ProjectRoot
    try {
        if (-not $startupReady -or $Force) {
            Write-Host "安装 Python 启动依赖..."
            Install-StartupPythonDependencies $Python
            New-Item -ItemType Directory -Force -Path $setupDir | Out-Null
            Set-Content -Path $startupMarker -Value (Get-Date -Format o) -Encoding UTF8
            Write-Host "Python 启动依赖安装完成"
        }

        if ($Force) {
            $needFull = $true
            if (Test-Path $fullMarker) {
                $markerTime = (Get-Item $fullMarker).LastWriteTime
                $needFull = $false
                foreach ($depFile in @($reqFile, $projFile)) {
                    if ((Get-Item $depFile).LastWriteTime -gt $markerTime) {
                        $needFull = $true
                        break
                    }
                }
            }
            if ($needFull -or -not $fullReady) {
                Write-Host "安装完整 quant 依赖 (pip install -r requirements-quant.txt，可能较慢)..."
                Invoke-PipInstall $Python @("install", "-r", $reqFile)
                Set-Content -Path $fullMarker -Value (Get-Date -Format o) -Encoding UTF8
                Write-Host "完整 quant 依赖安装完成"
            }
        }
    } finally {
        Pop-Location
    }
}

function Ensure-NpmDependencies {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "未找到 npm，请先安装 Node.js: https://nodejs.org/"
    }
    if ($Install -or -not (Test-Path (Join-Path $WebDir "node_modules"))) {
        Write-Host "安装前端依赖 (npm install)..."
        Push-Location $WebDir
        try {
            npm install
            if ($LASTEXITCODE -ne 0) { throw "npm install 失败 (exit $LASTEXITCODE)" }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "前端依赖已就绪，跳过 npm install"
    }
}

function Ensure-DatabaseInit {
    param([string]$Python)
    Write-Host "初始化数据库 schema (init-db)..."
    Push-Location $ProjectRoot
    try {
        $output = & $Python -m qmt_quant.cli init-db 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-SubprocessLines @($output)
            throw "init-db 失败 (exit $LASTEXITCODE)，请确认 PostgreSQL 已启动"
        }
        Write-SubprocessLines @($output)
    } finally {
        Pop-Location
    }
}

function Ensure-ProjectEnvironment {
    Write-Host ""
    Write-Host "== 检查/搭建运行环境 =="
    Ensure-Config
    $python = Ensure-QuantPython
    Ensure-PythonDependencies -Python $python -Force:$Install
    Ensure-NpmDependencies
    Ensure-Postgres -Python $python
    Ensure-DatabaseInit -Python $python
    Write-Host "== 环境就绪 =="
    Write-Host ""
    return $python
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

function Get-DockerComposeCommand {
    Add-DockerToPath
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $null
    }
    if (Invoke-ExternalQuiet "docker" @("compose", "version")) {
        return @{ Executable = "docker"; Prefix = @("compose") }
    }
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        return @{ Executable = "docker-compose"; Prefix = @() }
    }
    return $null
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
$Python = Ensure-ProjectEnvironment

if ($SetupOnly) {
    Write-Host "环境搭建完成（未启动服务）。启动请执行: .\scripts\start.ps1"
    exit 0
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host "项目目录: $ProjectRoot"
Write-Host "Python:   $Python"

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
Write-Host "  数据库 PostgreSQL localhost:5432（本机优先，Docker 备选）"
Write-Host "停止服务: .\scripts\start.ps1 -Stop  或  ./scripts/start.sh --stop"

if (-not $NoBrowser) {
    Start-Process "http://localhost:$WebPort"
}
