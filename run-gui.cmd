@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "BB_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "BB_PYTHON=.venv\Scripts\python.exe"
"%BB_PYTHON%" -m blockblast.desktop %*
exit /b %errorlevel%
