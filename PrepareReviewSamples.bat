@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Preparing TigerCapture review sample resources...
"%PYTHON_EXE%" "tools\prepare_review_sample_resources.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Review sample resources are ready.
    echo Report: debugCapture\review_sample_resources_qa.json
) else (
    echo Review sample resource preparation failed. Exit code: %EXIT_CODE%
)

echo.
pause
exit /b %EXIT_CODE%
