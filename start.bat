@echo off
cd /d "%~dp0"

if /i "%1"=="--no-browser" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-helper.ps1" -NoBrowser
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-helper.ps1"
)

REM Uncomment the line below to keep this console open for debugging:
REM pause
exit /b 0

