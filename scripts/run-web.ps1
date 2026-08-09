$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$WebDir = Join-Path $ProjectRoot "web"
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "未找到 npm，请安装 Node.js 并确保在 PATH 中"
    exit 1
}

Set-Location $WebDir
$logFile = Join-Path $LogDir "web.log"
Write-Host "[qmt-quant Web] npm run dev  ($WebDir)"
Write-Host "日志: $logFile"
npm run dev *>&1 | Tee-Object -FilePath $logFile
