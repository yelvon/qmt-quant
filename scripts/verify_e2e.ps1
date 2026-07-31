# Windows E2E verification (requires QMT for full run)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== doctor (quant-env) =="
& qmt-quant doctor
if ($LASTEXITCODE -ne 0) { Write-Warning "doctor reported issues — continue if expected" }

Write-Host "== init-db =="
& qmt-quant init-db

Write-Host "== catalog export (flat) =="
& qmt-quant catalog export --fmt flat

Write-Host "== pytest subset =="
python -m pytest tests/test_walk_forward.py tests/test_job_dispatch.py -q

Write-Host @"
SKIP (manual): sync universe/bars/financial — requires QMT online
SKIP (optional): catalog export --fmt nt — requires nautilus_trader
See docs/windows-e2e.md for full checklist
"@

Write-Host "Done."
