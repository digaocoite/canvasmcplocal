@echo off
setlocal
cd /d "%~dp0"

echo Starting CoursePack Local...
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on this computer.
  echo Please install Python 3.10 or newer from https://www.python.org/downloads/
  echo Make sure to check "Add python.exe to PATH" during install.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment. This happens only the first time...
  python -m venv .venv
  if errorlevel 1 (
    echo Could not create the local Python environment.
    pause
    exit /b 1
  )
)

echo Installing/updating required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install required packages.
  pause
  exit /b 1
)

echo.
echo Opening CoursePack Local at http://127.0.0.1:3333
echo Leave this window open while using the app.
echo Press CTRL+C in this window when you want to stop it.
echo.
".venv\Scripts\python.exe" run_web.py
pause
