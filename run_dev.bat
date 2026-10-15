@echo off
rem Runs Oh Fudge, My Battery Chat! straight from the source code - no build needed.
rem The dev copy keeps its own settings in a "Data" folder inside this project
rem folder, shows "(dev)" in its title bar, and can run next to the installed exe.
setlocal
cd /d "%~dp0"

set "PY="
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY python -c "import sys; sys.exit(sys.version_info[:2] != (3, 12))" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Python 3.12 wasn't found. Install it from https://www.python.org/downloads/ and run this again.
    pause
    exit /b 1
)

%PY% -c "import openvr, PIL, pystray, pycaw, comtypes" >nul 2>&1
if errorlevel 1 (
    echo Installing the packages the app needs - this only happens once...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Installing the packages failed - see the messages above.
        pause
        exit /b 1
    )
)

echo Starting the dev version. Close the app window to stop it.
%PY% main.py
if errorlevel 1 (
    echo.
    echo The app stopped with an error - see above, or Data\crash.log and Data\error.log in this folder.
    pause
)
