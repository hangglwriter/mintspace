@echo off
chcp 949 >nul
cd /d "D:\Sites\mintspace"
rem === 안전 런처: 이미 떠 있으면 재기동 안 함. 강제 종료(Stop-Process) 절대 안 함 ===
curl -s -m 2 http://localhost:5500/api/health >nul 2>&1
if %errorlevel%==0 (
  echo [mintspace] 헬퍼가 이미 떠 있습니다.
  timeout /t 1 >nul
  exit /b
)
echo [mintspace] 헬퍼를 켜는 중...
start "" /min "C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\pythonw.exe" "D:\Sites\mintspace\helper\server.py"
rem === 기동 확인: 최대 8초 폴링 (부팅 직후 지연 대비) ===
set "MS_OK=0"
for /L %%i in (1,1,8) do (
  timeout /t 1 >nul
  curl -s -m 2 http://localhost:5500/api/health >nul 2>&1
  if not errorlevel 1 (
    set "MS_OK=1"
    goto :ms_done
  )
)
:ms_done
if "%MS_OK%"=="1" (
  echo [mintspace] 완료. 헬퍼가 떴습니다. 창은 닫아도 됩니다.
) else (
  echo [mintspace] 기동 실패 - import 점검 로그를 남깁니다 ^(data\helper-startup.log^).
  echo ---- %date% %time% pythonw 기동 실패, import 점검 ---->> "D:\Sites\mintspace\data\helper-startup.log"
  "C:\Users\ADMIN\AppData\Local\Programs\Python\Python310\python.exe" -c "import sys; sys.path.insert(0, r'D:\Sites\mintspace\helper'); import server" >> "D:\Sites\mintspace\data\helper-startup.log" 2>&1
)
timeout /t 1 >nul
exit /b