@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"
title ChenFlow Workbench

echo.
echo ==========================================
echo   ChenFlow Workbench Launcher
echo ==========================================
echo.

where docker >nul 2>nul
if errorlevel 1 (
  echo [Error] Docker is not installed or not in PATH.
  goto :fail
)

docker version >nul 2>nul
if errorlevel 1 (
  echo [Error] Docker Desktop is not running.
  echo         Start Docker Desktop first, then run this file again.
  goto :fail
)

where python >nul 2>nul
if errorlevel 1 (
  echo [Error] Python is not installed or not in PATH.
  goto :fail
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [Error] Node.js and npm are not installed or not in PATH.
  goto :fail
)

echo [1/4] Starting MySQL...
docker compose up -d mysql
if errorlevel 1 (
  echo [Error] Failed to start MySQL.
  goto :fail
)

echo [2/4] Installing frontend dependencies if needed...
if not exist "frontend\node_modules" (
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo [Error] npm install failed.
    goto :fail
  )
  popd
)

echo [3/4] Building frontend...
pushd frontend
call npm run build
if errorlevel 1 (
  popd
  echo [Error] Frontend build failed.
  goto :fail
)
popd

echo [4/4] Starting backend server...
echo.
echo Open in browser: http://127.0.0.1:8000
echo Stop the server with Ctrl+C in this window.
echo.
python -m app.api
goto :end

:fail
echo.
echo Launcher stopped.
pause
exit /b 1

:end
echo.
echo Server stopped.
pause
endlocal
