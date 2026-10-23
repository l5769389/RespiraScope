@echo off
setlocal
rem Works when double-clicked or called from any working directory.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-exe.ps1" %*
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
if not "%BUILD_EXIT_CODE%"=="0" echo Build failed. See the error above.
if "%~1"=="" pause
exit /b %BUILD_EXIT_CODE%
