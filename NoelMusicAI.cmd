@echo off
setlocal
pushd "%~dp0"
where py >nul 2>nul || (echo Instale Python 3.11 x64 con el lanzador py. & exit /b 1)
py -3.11 -m noel %*
set "RESULT=%ERRORLEVEL%"
popd
exit /b %RESULT%
