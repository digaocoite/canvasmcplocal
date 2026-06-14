@echo off
title CoursePack Local Installer
echo.
echo CoursePack Local installer
echo This window will stay open so you can read the messages.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "iex (irm 'https://raw.githubusercontent.com/digaocoite/canvasmcplocal/main/install.ps1')"
exit /b %ERRORLEVEL%
