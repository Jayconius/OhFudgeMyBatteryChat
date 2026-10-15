@echo off
rem Runs the Demo Simulator straight from the source code - no build needed.
rem It feeds fake devices and microphones to the dev version of the app
rem (run_dev.bat): both use the "Data" folder inside this project folder.
rem Start either one first - the app picks the simulator up within a second.
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

echo Starting the Demo Simulator for the dev version. Close its window to stop it.
%PY% tools\fake_vr_signal_simulator.py --data-dir "%~dp0Data"
if errorlevel 1 (
    echo.
    echo The simulator stopped with an error - see the messages above.
    pause
)
