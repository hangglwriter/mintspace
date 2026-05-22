@echo off
title mintspace-stop
echo Stopping mintspace helper...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5500" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a
)
echo Done.
timeout /t 2 /nobreak >nul
exit
