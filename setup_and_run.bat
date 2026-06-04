@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_run.ps1"

echo.
echo Setup window finished. If the web UI is running, keep that server window open.
pause
