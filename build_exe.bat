@echo off
rem Build DuoSound executables.
rem Usage:
rem   build_exe.bat installer  - builds DuoSound.exe + DuoSound_Lite.exe, then runs Inno Setup
rem   build_exe.bat portable   - builds both as --onedir, then zips to dist\DuoSound_Full_Portable.zip
rem                              and dist\DuoSound_Lite_Portable.zip
rem
rem Prerequisites (once):  pip install -r requirements.txt pyinstaller
rem                        Flet client (~43 MB) is downloaded on first build, then cached.
rem                        Installer mode also needs Inno Setup (https://jrsoftware.org/isinfo.php).

cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

if /I "%1"=="installer" goto :installer
if /I "%1"=="portable"  goto :portable

echo.
echo Usage:  build_exe.bat [installer^|portable]
echo.
echo   installer  Builds DuoSound.exe + DuoSound_Lite.exe (one file each), then
echo              runs Inno Setup to produce dist\DuoSound_Setup.exe.
echo.
echo   portable   Builds both as one-directory bundles, then zips each to:
echo              dist\DuoSound_Full_Portable.zip  and  dist\DuoSound_Lite_Portable.zip
echo.
exit /b 1

rem -------------------------------------------------------------------------
:installer
echo [1/5] Generating icon and version info...
%PY% packaging\make_icon.py || goto :fail

echo [2/5] Fetching Flet desktop client (skipped if already cached)...
%PY% packaging\fetch_flet_client.py || goto :fail

rem onefile + windowed are defined in the .spec files themselves (a.binaries inline, console=False);
rem PyInstaller 6.x rejects those flags on the command line when a .spec is given.
echo [3/5] Building DuoSound.exe (Flet / Full Graphics)...
%PY% -m PyInstaller --noconfirm --clean ^
     --distpath dist --workpath "%TEMP%\duosound_build" ^
     packaging\duosound_flet.spec || goto :fail

echo [4/5] Building DuoSound_Lite.exe (tkinter / Classic Graphics)...
%PY% -m PyInstaller --noconfirm --clean ^
     --distpath dist --workpath "%TEMP%\duosound_build" ^
     packaging\duosound_lite.spec || goto :fail

echo [5/5] Running Inno Setup...
rem Prefer iscc on PATH; otherwise fall back to the default install locations, so a plain
rem "install Inno Setup with defaults" is enough and no PATH edit is required.
rem Covers Inno Setup 7 and 6, machine-wide and per-user (the installer offers both).
set "ISCC="
where iscc >nul 2>&1 && set "ISCC=iscc"
for %%V in (7 6) do (
    if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup %%V\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup %%V\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup %%V\ISCC.exe"     set "ISCC=%ProgramFiles(x86)%\Inno Setup %%V\ISCC.exe"
    if not defined ISCC if exist "%ProgramFiles%\Inno Setup %%V\ISCC.exe"          set "ISCC=%ProgramFiles%\Inno Setup %%V\ISCC.exe"
)
if not defined ISCC (
    echo WARNING: Inno Setup not found ^(not on PATH, not in Program Files^).
    echo          Get it from https://jrsoftware.org/isdl.php and re-run this script.
    echo          Skipping installer build. DuoSound.exe and DuoSound_Lite.exe are in dist\.
    goto :done
)
"%ISCC%" packaging\duosound_installer.iss || goto :fail

echo.
echo Done: dist\DuoSound_Setup.exe
goto :done

rem -------------------------------------------------------------------------
:portable
echo [1/4] Generating icon and version info...
%PY% packaging\make_icon.py || goto :fail

echo [2/4] Fetching Flet desktop client (skipped if already cached)...
%PY% packaging\fetch_flet_client.py || goto :fail

rem The .spec files build one-file executables (a.binaries inline, no COLLECT), so --onedir
rem cannot apply here and PyInstaller 6.x rejects it alongside a .spec. The one-file exes are
rem already self-contained, so "portable" ships those directly rather than a one-dir bundle.
echo [3/4] Building DuoSound Full portable...
%PY% -m PyInstaller --noconfirm --clean ^
     --distpath dist\DuoSound_Full --workpath "%TEMP%\duosound_build" ^
     packaging\duosound_flet.spec || goto :fail

echo [4/4] Building DuoSound Lite portable...
%PY% -m PyInstaller --noconfirm --clean ^
     --distpath dist\DuoSound_Lite --workpath "%TEMP%\duosound_build" ^
     packaging\duosound_lite.spec || goto :fail

echo Zipping portable builds...
powershell -NoProfile -Command ^
  "Compress-Archive -Path 'dist\DuoSound_Full\*' -DestinationPath 'dist\DuoSound_Full_Portable.zip' -Force; ^
   Compress-Archive -Path 'dist\DuoSound_Lite\*' -DestinationPath 'dist\DuoSound_Lite_Portable.zip' -Force" || goto :fail

echo.
echo Done:
echo   dist\DuoSound_Full_Portable.zip
echo   dist\DuoSound_Lite_Portable.zip
goto :done

rem -------------------------------------------------------------------------
:done
pause
exit /b 0

:fail
echo.
echo Build FAILED - see messages above.
pause
exit /b 1
