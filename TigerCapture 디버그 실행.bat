@echo off
setlocal

cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "APP=%~dp0main.py"
set "PYTHONDONTWRITEBYTECODE=1"

if exist "%PY%" (
    "%PY%" "%APP%"
    goto after_run
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%APP%"
    goto after_run
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%APP%"
    goto after_run
)

echo Python interpreter was not found.
echo Expected: "%PY%"
goto pause_and_exit

:after_run
if not %errorlevel%==0 (
    echo.
    echo TigerCapture exited with error code %errorlevel%.
)
echo.
echo Latest app log:
echo "%LOCALAPPDATA%\TigerCapture\logs\tigercapture.log"

:pause_and_exit
echo.
pause
