@echo off
setlocal

set "ROOT=%~dp0"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "APP=%ROOT%main.py"
set "PYTHONDONTWRITEBYTECODE=1"

if exist "%PYW%" (
    start "TigerCapture" "%PYW%" "%APP%"
    exit /b 0
)

if exist "%PY%" (
    start "TigerCapture" "%PY%" "%APP%"
    exit /b 0
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "TigerCapture" py -3 "%APP%"
    exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "TigerCapture" python "%APP%"
    exit /b 0
)

echo Python interpreter was not found.
echo Expected: "%PY%"
echo.
echo Install dependencies or recreate the virtual environment, then try again.
pause
