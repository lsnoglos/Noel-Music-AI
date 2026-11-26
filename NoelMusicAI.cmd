@echo off
setlocal
pushd "%~dp0"
if not "%~1"=="" goto cli
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1"
if errorlevel 1 pause
exit /b %errorlevel%
:cli
if exist ".runtime\python\python.exe" (
  ".runtime\python\python.exe" -m noel %*
) else (
  py -3 -m noel %*
)
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
