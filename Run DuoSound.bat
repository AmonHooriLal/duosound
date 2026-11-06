@echo off
rem DuoSound - play the laptop's sound on several headphones at once, in sync.  Made by Amon Lal.
rem Runs DuoSound from the source code (no console window). Most people should use dist\DuoSound.exe instead.
rem Finds Python the way Windows installs it: the "py" launcher first, then python on PATH.
cd /d "%~dp0"
where pyw >nul 2>&1 && ( start "" pyw -3 "%~dp0main.py" %* & exit /b )
where pythonw >nul 2>&1 && ( pythonw -c "import sys" >nul 2>&1 && ( start "" pythonw "%~dp0main.py" %* & exit /b ) )
where py >nul 2>&1 && ( py -3 "%~dp0main.py" %* & if errorlevel 1 pause & exit /b )
python -c "import sys" >nul 2>&1 && ( python "%~dp0main.py" %* & if errorlevel 1 pause & exit /b )
echo.
echo  DuoSound needs Python 3.10 or newer to run from source.
echo   1. Install it from https://www.python.org/downloads/  (tick "Add python.exe to PATH")
echo   2. In this folder run:  pip install -r requirements.txt
echo   3. Double-click "Run DuoSound.bat" again.
echo  Or simply use DuoSound.exe, which needs nothing installed.
echo.
pause
