@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"
title GraphRAG Novel Workbench Stopper

echo.
echo ==========================================
echo   GraphRAG Novel Workbench Stopper
echo ==========================================
echo.

set "BACKEND_FOUND="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*-m app.api*' } | Select-Object -ExpandProperty ProcessId"`) do (
  set "BACKEND_FOUND=1"
  echo [1/2] Stopping backend process PID %%P...
  powershell -NoProfile -Command "Stop-Process -Id %%P -Force"
)

if not defined BACKEND_FOUND (
  for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($conn) { $conn.OwningProcess }"`) do (
    set "BACKEND_FOUND=1"
    echo [1/2] Stopping process on 127.0.0.1:8000 with PID %%P...
    powershell -NoProfile -Command "Stop-Process -Id %%P -Force"
  )
)

if not defined BACKEND_FOUND (
  echo [1/2] No running backend process was found.
)

echo [2/2] Stopping MySQL and Neo4j containers...
docker compose stop mysql neo4j >nul 2>nul
if errorlevel 1 (
  echo       Docker services were not running or could not be stopped.
) else (
  echo       Docker services stopped.
)

echo.
echo Workbench stop routine finished.
pause
endlocal
