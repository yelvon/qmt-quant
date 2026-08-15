# Start qmt-quant Web workbench (API + Vite frontend).
# Usage:
#   .\scripts\start.ps1           # start both servers
#   .\scripts\start.ps1 -Install  # npm install before start
#   .\scripts\start.ps1 -Stop     # stop servers on ports 8788 / 5173
#   .\scripts\start.ps1 -Restart  # stop then start
#   .\scripts\start.ps1 -SetupOnly # setup env only (config, deps, postgres, init-db)
#
# Git Bash users: use ./scripts/start.sh instead (see README).

param(
    [switch]$NoBrowser,
    [switch]$Install,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$SetupOnly
)

& (Join-Path $PSScriptRoot "service.ps1") @PSBoundParameters
