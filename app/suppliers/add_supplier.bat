@echo off
chcp 65001 >nul
cd /d "%~dp0..\.."

if not exist ".venv\Scripts\python.exe" (
  echo Нет виртуального окружения. Сначала запустите run.bat в корне проекта.
  echo.
  pause
  exit /b 1
)

echo Добавление поставщика. Корень проекта: %CD%
echo.
".venv\Scripts\python.exe" -m app.suppliers.add_supplier
echo.
pause
