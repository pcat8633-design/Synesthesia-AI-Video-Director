@echo off
echo ============================================
echo  Synesthesia AI Video Director
echo ============================================
echo.

REM ============================================
REM  Autolaunch paths — update these if needed
REM ============================================
set LM_STUDIO_PATH=C:\Users\rowan\AppData\Local\Programs\LM Studio\LM Studio.exe
set LTX_DESKTOP_PATH=H:\LTX Desktop\LTX Desktop.exe

REM --- Launch LM Studio if not already running ---
tasklist /FI "IMAGENAME eq LM Studio.exe" 2>NUL | find /I "LM Studio.exe" >NUL 2>NUL
if errorlevel 1 (
    if exist "%LM_STUDIO_PATH%" (
        start "" "%LM_STUDIO_PATH%"
    ) else (
        echo WARNING: LM Studio not found at: %LM_STUDIO_PATH%
        echo   Update LM_STUDIO_PATH in run.bat to enable autolaunch.
    )
)

REM --- Launch LTX Desktop if not already running ---
tasklist /FI "IMAGENAME eq LTX Desktop.exe" 2>NUL | find /I "LTX Desktop.exe" >NUL 2>NUL
if errorlevel 1 (
    if exist "%LTX_DESKTOP_PATH%" (
        start "" "%LTX_DESKTOP_PATH%"
    ) else (
        echo WARNING: LTX Desktop not found at: %LTX_DESKTOP_PATH%
        echo   Update LTX_DESKTOP_PATH in run.bat to enable autolaunch.
    )
)

echo.
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting Synesthesia AI Video Director...
echo The app will open in your browser shortly.
echo Press Ctrl+C in this window to stop the application.
echo.
python app.py
if errorlevel 1 (
    echo.
    echo ERROR: Application exited with an error.
    pause
)
