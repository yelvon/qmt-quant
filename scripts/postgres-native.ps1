# Native PostgreSQL setup (Windows) — preferred over Docker on ARM64 / no-WSL hosts.

function Get-PostgresDbUrl {
    $settingsPath = Join-Path $ProjectRoot "config\settings.yaml"
    $fromConfig = Get-YamlValue -Path $settingsPath -Key "db_url"
    if ($fromConfig) { return $fromConfig.Trim().Trim('"').Trim("'") }
    return "postgresql://qmt:qmt@localhost:5432/qmt_quant"
}

function Test-PostgresConnection {
    param(
        [string]$Python,
        [string]$DbUrl = ""
    )
    if (-not $Python -or -not (Test-Path $Python)) { return $false }
    if (-not $DbUrl) { $DbUrl = Get-PostgresDbUrl }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $env:DATABASE_URL = $DbUrl
        & $Python -c "import os, psycopg; psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=5).close()" 2>$null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $prev
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
    }
}

function Find-PsqlPath {
    $candidates = @(
        (Join-Path $env:ProgramFiles "PostgreSQL\16\bin\psql.exe"),
        (Join-Path $env:ProgramFiles "PostgreSQL\17\bin\psql.exe"),
        (Join-Path $env:ProgramFiles "PostgreSQL\15\bin\psql.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    $root = Join-Path $env:ProgramFiles "PostgreSQL"
    if (Test-Path $root) {
        $found = Get-ChildItem -Path $root -Filter "psql.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    if (Get-Command psql -ErrorAction SilentlyContinue) {
        return (Get-Command psql).Source
    }
    return $null
}

function Get-PostgresWindowsServices {
    return @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "postgres" })
}

function Start-PostgresWindowsService {
    $services = Get-PostgresWindowsServices
    if (-not $services) { return $false }

    $started = $false
    foreach ($svc in $services) {
        if ($svc.Status -eq "Running") {
            $started = $true
            continue
        }
        try {
            Write-Host "启动 PostgreSQL 服务 ($($svc.Name))..."
            Start-Service -Name $svc.Name -ErrorAction Stop
            $started = $true
        } catch {
            Write-Warning "无法启动服务 $($svc.Name): $_"
        }
    }
    return $started
}

function Wait-PostgresConnection {
    param(
        [string]$Python,
        [int]$TimeoutSec = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PostgresConnection -Python $Python) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Initialize-QmtPostgresDatabase {
    param(
        [string]$Psql,
        [string]$SuperUser = "postgres",
        [string]$SuperPassword = "qmt"
    )
    if (-not $Psql) { return $false }

    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $env:PGPASSWORD = $SuperPassword
        & $Psql -U $SuperUser -h localhost -p 5432 -d postgres -c "CREATE USER qmt WITH PASSWORD 'qmt' CREATEDB;" 2>$null
        & $Psql -U $SuperUser -h localhost -p 5432 -d postgres -c "CREATE DATABASE qmt_quant OWNER qmt;" 2>$null
        & $Psql -U $SuperUser -h localhost -p 5432 -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE qmt_quant TO qmt;" 2>$null
        return $true
    } finally {
        $ErrorActionPreference = $prev
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Try-Install-NativePostgres {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        return $false
    }

    if (Find-PsqlPath) {
        return $true
    }

    Write-Host "尝试通过 winget 安装本机 PostgreSQL 16（无需 Docker/WSL）..."
    Write-Host "（安装时使用超级用户密码: qmt，与应用配置一致）"

    $wingetIds = @(
        "PostgreSQL.PostgreSQL.16",
        "PostgreSQL.PostgreSQL.17",
        "PostgreSQL.PostgreSQL"
    )

    foreach ($pkgId in $wingetIds) {
        $wingetOutput = winget install --id $pkgId -e `
            --accept-package-agreements --accept-source-agreements `
            --override "--mode unattended --superpassword qmt --serverport 5432" 2>&1
        Write-SubprocessLines @($wingetOutput)
        if ($LASTEXITCODE -eq 0 -and (Find-PsqlPath)) {
            return $true
        }
    }
    return $false
}

function Ensure-NativePostgres {
    param([string]$Python)

    if (Test-PostgresConnection -Python $Python) {
        Write-Host "PostgreSQL 已就绪 ($(Get-PostgresDbUrl))"
        return $true
    }

    Write-Host "优先使用本机 PostgreSQL（无需 Docker）..."

    if (Test-PortInUse 5432) {
        Write-Host "检测到 5432 端口已占用，尝试初始化 qmt 用户/数据库..."
        Initialize-QmtPostgresDatabase -Psql (Find-PsqlPath) | Out-Null
        if (Test-PostgresConnection -Python $Python) {
            Write-Host "PostgreSQL 已就绪（本机）"
            return $true
        }
    }

    $serviceStarted = Start-PostgresWindowsService
    if ($serviceStarted) {
        Write-Host "等待本机 PostgreSQL 启动..."
        if (Wait-PostgresConnection -Python $Python -TimeoutSec 60) {
            Write-Host "PostgreSQL 已就绪（本机服务）"
            return $true
        }
    }

    if (-not (Find-PsqlPath)) {
        Try-Install-NativePostgres | Out-Null
        Refresh-PathEnv
        Start-PostgresWindowsService | Out-Null
    }

    if (-not (Wait-PostgresConnection -Python $Python -TimeoutSec 120)) {
        if (Find-PsqlPath) {
            Write-Host "尝试创建 qmt / qmt_quant 数据库..."
            Initialize-QmtPostgresDatabase -Psql (Find-PsqlPath) | Out-Null
        }
    }

    if (Test-PostgresConnection -Python $Python) {
        Write-Host "PostgreSQL 已就绪（本机 winget 安装）"
        return $true
    }

    return $false
}

function Ensure-PostgresViaDocker {
    $composeFile = Join-Path $ProjectRoot "docker-compose.yml"
    if (-not (Test-Path $composeFile)) {
        Write-Warning "未找到 docker-compose.yml，跳过 Docker PostgreSQL。"
        return $false
    }

    Ensure-DockerEngineReady | Out-Null

    $compose = Get-DockerComposeCommand
    if (-not $compose) {
        return $false
    }

    Write-Host "启动 PostgreSQL (docker compose up -d)..."
    Push-Location $ProjectRoot
    try {
        $args = @($compose.Prefix + @("up", "-d"))
        & $compose.Executable @args
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose up -d 失败 (exit $LASTEXITCODE)"
        }
    } finally {
        Pop-Location
    }

    if (-not (Wait-PostgresPortReady -TimeoutSec 60)) {
        throw "PostgreSQL (Docker) 启动超时，请执行 docker compose logs postgres 查看详情"
    }
    Write-Host "PostgreSQL 已就绪 (Docker, localhost:5432)"
    return $true
}

function Wait-PostgresPortReady {
    param([int]$TimeoutSec = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortInUse 5432) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Ensure-Postgres {
    param([string]$Python)

    if (Test-PostgresConnection -Python $Python) {
        Write-Host "PostgreSQL 已就绪，跳过启动"
        return
    }

    if (Ensure-NativePostgres -Python $Python) {
        return
    }

    Write-Host ""
    Write-Host "本机 PostgreSQL 未就绪，尝试 Docker 备选方案..."
    if (Ensure-PostgresViaDocker) {
        if (-not (Test-PostgresConnection -Python $Python)) {
            throw "Docker PostgreSQL 已启动但连接失败，请检查 config/settings.yaml 中的 db_url"
        }
        return
    }

    throw @"
无法启动 PostgreSQL。

推荐（Windows ARM64 / 无 WSL）— 本机安装：
  winget install PostgreSQL.PostgreSQL.16
  安装完成后重新运行: ./scripts/start.sh

或手动启动 Docker Desktop 后再试。
默认连接串: postgresql://qmt:qmt@localhost:5432/qmt_quant
详见 docs/postgres-setup.md
"@
}
