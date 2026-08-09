@echo off
REM PowerShell / CMD entry — delegates to scripts\start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
