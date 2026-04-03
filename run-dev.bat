@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  CONFIGURE THESE FOR YOUR MACHINE
REM  LM_STUDIO_PATH: C:\Users\<YourName>\AppData\Local\Programs\LM Studio\LM Studio.exe
REM  LTX_DESKTOP_PATH: wherever you installed LTX Desktop
REM ============================================================
set LM_STUDIO_PATH=C:\Users\rowan\AppData\Local\Programs\LM Studio\LM Studio.exe
set LTX_DESKTOP_PATH=H:\LTX Desktop\LTX Desktop.exe

echo ============================================================
echo  Synesthesia AI Video Director  [DEV MODE - no update check]
echo ============================================================
echo.

REM ============================================================
REM  PYTHON CHECK
REM ============================================================
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM  FIRST-RUN INSTALL
REM ============================================================
if not exist "venv\Scripts\activate.bat" (
    echo No installation found. Running first-time setup...
    echo.

    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo Activating virtual environment...
    call venv\Scripts\activate.bat

    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )

    echo.
    echo ============================================================
    echo  Installation complete!
    echo ============================================================
    echo.
    echo IMPORTANT: You also need FFmpeg installed and on your PATH.
    echo Download FFmpeg from https://ffmpeg.org/ if you haven't already.
    echo.
)

REM ============================================================
REM  OPEN EXPLORER AND CLAUDE PROMPT (skip if already running)
REM ============================================================
explorer "F:\Music Video Maker\Synesthesia-AI-Video-Director"
set CLAUDE_RUNNING=0
tasklist /FI "IMAGENAME eq claude.exe" 2>NUL | find /I "claude.exe" >NUL 2>NUL
if not errorlevel 1 set CLAUDE_RUNNING=1
if "!CLAUDE_RUNNING!"=="0" (
    wmic process where "name='node.exe'" get commandline 2>nul | find /i "claude" >nul 2>nul
    if not errorlevel 1 set CLAUDE_RUNNING=1
)
if "!CLAUDE_RUNNING!"=="0" (
    start cmd /k "cd /d "F:\Music Video Maker\Synesthesia-AI-Video-Director" && claude"
)

REM ============================================================
REM  LAUNCH LM STUDIO (if not already running)
REM ============================================================
tasklist /FI "IMAGENAME eq LM Studio.exe" 2>NUL | find /I "LM Studio.exe" >NUL 2>NUL
if errorlevel 1 (
    if exist "%LM_STUDIO_PATH%" (
        powershell -Command "Start-Process '%LM_STUDIO_PATH%'"
    )
)

REM ============================================================
REM  LAUNCH LTX DESKTOP (if not already running)
REM ============================================================
tasklist /FI "IMAGENAME eq LTX Desktop.exe" 2>NUL | find /I "LTX Desktop.exe" >NUL 2>NUL
if errorlevel 1 (
    if exist "%LTX_DESKTOP_PATH%" (
        start "" "%LTX_DESKTOP_PATH%"
    )
)

REM ============================================================
REM  ACTIVATE VENV AND RUN APP
REM ============================================================
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found. This should not happen.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python app.py

if errorlevel 1 (
    echo.
    echo ERROR: Application exited with an error.
    pause
)
