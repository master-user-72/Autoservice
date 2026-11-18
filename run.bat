@echo off
if /I not "%~1"=="hidden" (
  start "" wscript.exe //nologo "%~dp0scripts\launch_hidden.vbs" "%~f0" app
  exit /b 0
)

chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt >nul 2>&1

if not exist ".env" (
  copy ".env.example" ".env" >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0scripts\run_agent.ps1" -Mode app
exit /b %ERRORLEVEL%
