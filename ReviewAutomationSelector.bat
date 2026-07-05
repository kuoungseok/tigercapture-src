@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Opening TigerCapture review automation selector...
"%PYTHON_EXE%" "tools\review_automation_launcher.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

exit /b %EXIT_CODE%
