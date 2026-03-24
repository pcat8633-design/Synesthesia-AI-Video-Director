@echo off
setlocal EnableDelayedExpansion

REM ============================================================
REM  CONFIGURE THESE FOR YOUR MACHINE
REM  GIT_BRANCH: "main" = stable releases (latest tag)
REM              "dev"  = development branch (latest commits)
REM  LM_STUDIO_PATH: C:\Users\<YourName>\AppData\Local\Programs\LM Studio\LM Studio.exe
REM  LTX_DESKTOP_PATH: wherever you installed LTX Desktop
REM ============================================================
set GIT_BRANCH=main
set LM_STUDIO_PATH=C:\Users\rowan\AppData\Local\Programs\LM Studio\LM Studio.exe
set LTX_DESKTOP_PATH=H:\LTX Desktop\LTX Desktop.exe

echo ============================================================
echo  Synesthesia AI Video Director
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
set JUST_INSTALLED=0
if not exist "venv\Scripts\activate.bat" (
    echo No installation found. Running first-time setup...
    echo.

    git --version >nul 2>&1
    if errorlevel 1 (
        echo WARNING: Git is not installed or not in your PATH.
        echo Git is required for automatic updates.
        echo Install Git from https://git-scm.com/
        echo.
    )

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
    set JUST_INSTALLED=1
)

REM ============================================================
REM  UPDATE CHECK  (skipped after first-run install)
REM ============================================================
if "%JUST_INSTALLED%"=="1" goto :LAUNCH

git --version >nul 2>&1
if errorlevel 1 (
    echo NOTE: Git not found - skipping update check.
    echo.
    goto :LAUNCH
)

echo Checking for updates...
if /i "%GIT_BRANCH%"=="dev" (
    REM --- Dev branch: compare local HEAD to origin/dev ---
    git fetch origin >nul 2>&1
    if errorlevel 1 (
        echo WARNING: Could not reach remote - skipping update check.
        echo.
        goto :LAUNCH
    )

    for /f "delims=" %%h in ('git rev-parse HEAD 2^>nul') do set LOCAL_SHA=%%h
    for /f "delims=" %%h in ('git rev-parse origin/dev 2^>nul') do set REMOTE_SHA=%%h

    if not defined REMOTE_SHA (
        echo WARNING: Could not determine remote dev state - skipping update check.
        echo.
        goto :LAUNCH
    )

    if "!LOCAL_SHA!"=="!REMOTE_SHA!" (
        echo Already up to date.
        echo.
        goto :LAUNCH
    )

    echo A new dev update is available.
    set /p DO_UPDATE="Update now? (Y/N): "
    if /i "!DO_UPDATE!"=="Y" (
        echo Pulling latest dev...
        git pull origin dev
        if errorlevel 1 (
            echo WARNING: Update failed - launching with current version.
            echo.
            goto :LAUNCH
        )
        call venv\Scripts\activate.bat
        echo Updating dependencies...
        pip install --upgrade -r requirements.txt
        if errorlevel 1 (
            echo WARNING: Dependency update failed - some features may not work correctly.
        )
        echo.
        echo Update complete.
        echo.
    ) else (
        echo Skipping update.
        echo.
    )
) else (
    REM --- Main branch: compare current tag to latest release tag ---
    git fetch --tags --force >nul 2>&1
    if errorlevel 1 (
        echo WARNING: Could not reach remote - skipping update check.
        echo.
        goto :LAUNCH
    )

    set LATEST_TAG=
    for /f "delims=" %%t in ('git tag --sort=-version:refname 2^>nul') do (
        if not defined LATEST_TAG set LATEST_TAG=%%t
    )

    if not defined LATEST_TAG (
        echo NOTE: No release tags found - skipping update check.
        echo.
        goto :LAUNCH
    )

    set CURRENT_TAG=
    for /f "delims=" %%t in ('git describe --tags --exact-match HEAD 2^>nul') do set CURRENT_TAG=%%t

    if "!CURRENT_TAG!"=="!LATEST_TAG!" (
        echo Already on latest release (!LATEST_TAG!).
        echo.
        goto :LAUNCH
    )

    if not defined CURRENT_TAG (
        echo Current version: (development / untagged^)
    ) else (
        echo Current version: !CURRENT_TAG!
    )
    echo Latest release:  !LATEST_TAG!
    echo.
    set /p DO_UPDATE="Update to !LATEST_TAG!? (Y/N): "
    if /i "!DO_UPDATE!"=="Y" (
        echo Updating to !LATEST_TAG!...
        git checkout !LATEST_TAG!
        if errorlevel 1 (
            echo WARNING: Update failed - launching with current version.
            echo.
            goto :LAUNCH
        )
        call venv\Scripts\activate.bat
        echo Updating dependencies...
        pip install --upgrade -r requirements.txt
        if errorlevel 1 (
            echo WARNING: Dependency update failed - some features may not work correctly.
        )
        echo.
        echo Update complete.
        echo.
    ) else (
        echo Skipping update.
        echo.
    )
)

:LAUNCH
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
        powershell -Command "Start-Process '%LTX_DESKTOP_PATH%'"
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
