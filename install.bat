@echo off
echo ============================================
echo  Synesthesia AI Video Director - Installer
echo ============================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Check for Git
git --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Git is not installed or not in your PATH.
    echo Git is required for update.bat to work.
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
echo ============================================
echo  Installation complete!
echo ============================================
echo.
echo IMPORTANT: You also need FFmpeg installed and on your PATH.
echo Download FFmpeg from https://ffmpeg.org/ if you haven't already.
echo.
echo You can now run the application by double-clicking run.bat
echo.
pause
