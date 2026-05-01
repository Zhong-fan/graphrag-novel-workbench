@echo off
setlocal EnableExtensions
chcp 65001 >nul

cd /d "%~dp0"
title GraphRAG Novel Workbench

echo.
echo ==========================================
echo   GraphRAG Novel Workbench Launcher
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

where ollama >nul 2>nul
if errorlevel 1 (
  echo [Error] Ollama is not installed or not in PATH.
  goto :fail
)

echo [1/5] Checking local Ollama model...
ollama list | findstr /i /c:"bge-m3" >nul
if errorlevel 1 (
  echo [Error] Model "bge-m3" was not found in Ollama.
  echo         Run: ollama pull bge-m3
  goto :fail
)

echo [2/5] Starting MySQL and Neo4j...
docker compose up -d mysql neo4j
if errorlevel 1 (
  echo [Error] Failed to start docker services.
  goto :fail
)

echo [3/5] Installing frontend dependencies if needed...
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

echo [4/5] Building frontend...
pushd frontend
call npm run build
if errorlevel 1 (
  popd
  echo [Error] Frontend build failed.
  goto :fail
)
popd

echo [5/5] Starting backend server...
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
