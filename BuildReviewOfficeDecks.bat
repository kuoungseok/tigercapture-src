@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Building Office-valid TigerCapture review decks...
"%PYTHON_EXE%" "tools\build_review_office_decks.py" --deck-mode all --force %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Review decks are ready.
    if "%TIGERCAPTURE_REVIEW_ROOT%"=="" (
        echo Output: %~dp0..\ReviewAutomationWorkspace\outputs
    ) else (
        echo Output: %TIGERCAPTURE_REVIEW_ROOT%\outputs
    )
) else (
    echo Review deck build failed. Exit code: %EXIT_CODE%
)

echo.
pause
exit /b %EXIT_CODE%
