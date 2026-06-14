@echo off
setlocal
cd /d "%~dp0"

echo Starting CoursePack Claude Desktop connection...
echo This may take a minute the first time because MCP packages may be installed.
echo Please do not run this more than once at the same time.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo CoursePack's local Python environment was not found.
  echo Please run "Start CoursePack Local.bat" first, then try this again.
  pause
  exit /b 1
)

echo Step 1 of 2: checking MCP packages...
".venv\Scripts\python.exe" -m pip install -r requirements-mcp.txt
if errorlevel 1 (
  echo Could not install/update required MCP packages.
  pause
  exit /b 1
)

echo.
echo Step 2 of 2: updating Claude Desktop MCP config...
".venv\Scripts\python.exe" -m coursepack.cli_connect_claude
if errorlevel 1 (
  echo.
  echo CoursePack could not be connected to Claude Desktop. Read the message above.
  pause
  exit /b 1
)

echo.
echo Done. Fully quit and reopen Claude Desktop before checking for CoursePack tools.
pause
