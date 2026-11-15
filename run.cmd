@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "BB_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "BB_PYTHON=.venv\Scripts\python.exe"
if "%~1"=="" (
  "%BB_PYTHON%" -m blockblast.desktop
) else (
  "%BB_PYTHON%" -m blockblast %*
)
exit /b %errorlevel%
