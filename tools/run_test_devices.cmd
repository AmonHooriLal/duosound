@echo off
rem Runs the DuoSound device test (started by "Test Devices.bat", normally inside Windows Terminal).
chcp 65001 >nul
rem always show colours and the bot, even if a parent program set NO_COLOR
set "NO_COLOR="
title DuoSound Device Test
cd /d "%~dp0"
python test_devices.py %*
echo.
pause
