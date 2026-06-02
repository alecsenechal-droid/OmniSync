@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\activate.bat (
  echo Environnement virtuel absent. Lancez install.bat d'abord.
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m omnisync %*
