@echo off
setlocal

cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo [RespiraScope] uv was not found on PATH.
  echo [RespiraScope] Install uv first, then run this script again.
  pause
  exit /b 1
)

echo [RespiraScope] Starting from %CD%
echo [RespiraScope] Press Ctrl+C to stop the server.
echo.

uv run RespiraScope
set "exit_code=%ERRORLEVEL%"

echo.
if not "%exit_code%"=="0" (
  echo [RespiraScope] Exited with code %exit_code%.
) else (
  echo [RespiraScope] Stopped.
)
pause
exit /b %exit_code%
