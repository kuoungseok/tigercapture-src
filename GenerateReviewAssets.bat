@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

if "%~1"=="" (
    echo Opening TigerCapture review automation selector...
    "%PYTHON_EXE%" "tools\review_automation_launcher.py"
) else (
    echo Generating TigerCapture review automation assets...
    "%PYTHON_EXE%" "tools\generate_review_assets.py" %*
)
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Review automation assets are ready.
    if "%TIGERCAPTURE_REVIEW_ROOT%"=="" (
        echo Root:   %~dp0..\ReviewAutomationWorkspace
        echo Report: %~dp0..\ReviewAutomationWorkspace\outputs\review_report.json
        echo HTML:   %~dp0..\ReviewAutomationWorkspace\outputs\site\index.html
        echo PPTX:   %~dp0..\ReviewAutomationWorkspace\outputs\TigerCapture_Review_Automation.pptx
    ) else (
        echo Root:   %TIGERCAPTURE_REVIEW_ROOT%
        echo Report: %TIGERCAPTURE_REVIEW_ROOT%\outputs\review_report.json
        echo HTML:   %TIGERCAPTURE_REVIEW_ROOT%\outputs\site\index.html
        echo PPTX:   %TIGERCAPTURE_REVIEW_ROOT%\outputs\TigerCapture_Review_Automation.pptx
    )
) else (
    echo Review automation generation failed. Exit code: %EXIT_CODE%
)

echo.
pause
exit /b %EXIT_CODE%
