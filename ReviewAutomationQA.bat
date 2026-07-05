@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Validating TigerCapture review automation outputs...
"%PYTHON_EXE%" "tools\qa_review_automation.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Review automation QA passed.
    echo Report: debugCapture\review_automation_qa.json
) else (
    echo Review automation QA failed. Exit code: %EXIT_CODE%
)

echo.
pause
exit /b %EXIT_CODE%
