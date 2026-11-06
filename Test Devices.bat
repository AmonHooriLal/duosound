@echo off
rem DuoSound device test - lists sound outputs and plays a test beep on the headphones you pick.
rem Extra options pass through, e.g.  "Test Devices.bat" --yes
rem Opens in Windows Terminal, maximised (real-picture welcome scene + roaming bot); runs here if it is not installed.
if not defined WT_SESSION (
  where wt >nul 2>&1 && (
    start "" wt.exe --maximized -d "%~dp0." cmd /c call "%~dp0tools\run_test_devices.cmd" %*
    exit /b
  )
)
call "%~dp0tools\run_test_devices.cmd" %*
