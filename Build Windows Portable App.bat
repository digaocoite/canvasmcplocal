@echo off
setlocal
cd /d "%~dp0"

echo Building CoursePack Local portable Windows app...
echo This creates a no-admin folder in dist\CoursePack Local.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ first.
  pause
  exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
  echo Creating build environment...
  python -m venv .venv-build
  if errorlevel 1 (
    echo Could not create build environment.
    pause
    exit /b 1
  )
)

echo Installing build dependencies...
".venv-build\Scripts\python.exe" -m pip install --upgrade pip
".venv-build\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-mcp.txt pyinstaller
if errorlevel 1 (
  echo Could not install build dependencies.
  pause
  exit /b 1
)

echo.
echo Running PyInstaller...
".venv-build\Scripts\python.exe" build_portable.py
if errorlevel 1 (
  echo Portable build failed. Read the message above.
  pause
  exit /b 1
)

echo.
echo Done.
echo Open dist\CoursePack Local and double-click Start CoursePack Local.bat.
pause
