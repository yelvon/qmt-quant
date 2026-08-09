$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

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

$settingsPath = Join-Path $ProjectRoot "config\settings.yaml"
$python = Get-YamlValue -Path $settingsPath -Key "quant_env"
if (-not $python -or -not (Test-Path $python)) {
    $python = Join-Path $ProjectRoot ".venv-quant\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    Write-Error "未找到 quant-env Python，请配置 config/settings.yaml"
    exit 1
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")

Set-Location $ProjectRoot
$logFile = Join-Path $LogDir "api.log"
Write-Host "[qmt-quant API] $python -m qmt_quant.cli serve api"
Write-Host "日志: $logFile"
& $python -m qmt_quant.cli serve api *>&1 | Tee-Object -FilePath $logFile
