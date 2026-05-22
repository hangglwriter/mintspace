@echo off
chcp 65001 >nul
title mintspace
cd /d "%~dp0"

REM ---- Check dependencies ----
python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo Installing dependencies (FastAPI, uvicorn)...
    python -m pip install -r helper\requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo Please run: python -m pip install -r helper\requirements.txt
        pause
        exit /b 1
    )
)

REM ---- Kill old helper if running ----
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5500" ^| findstr "LISTENING"') do (
    echo Killing old helper PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

REM ---- Start helper in background ----
echo Starting mintspace helper...
start "mintspace-helper" /min python helper\server.py

REM ---- Wait until helper is up ----
set retries=0
:wait
timeout /t 1 /nobreak >nul
curl -s http://localhost:5500/api/health >nul 2>&1
if errorlevel 1 (
    set /a retries+=1
    if %retries% lss 10 goto wait
    echo [WARN] Helper did not respond in time. Opening browser anyway.
)

REM ---- Open browser (skip if --no-browser flag) ----
if /i "%1"=="--no-browser" goto done
echo Opening browser...
start "" http://localhost:5500

:done
exit
