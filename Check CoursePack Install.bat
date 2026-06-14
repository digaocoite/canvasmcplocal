@echo off
setlocal
cd /d "%~dp0"

echo Checking CoursePack Local installation...
echo.

if not exist ".venv\Scripts\python.exe" (
  echo CoursePack's local Python environment was not found.
  echo Run "Start CoursePack Local.bat" first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" check_install.py
pause
