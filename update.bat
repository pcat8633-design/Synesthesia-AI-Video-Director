@echo off
echo ============================================
echo  Synesthesia AI Video Director - Updater
echo ============================================
echo.

:: Check for Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in your PATH.
    echo Install Git from https://git-scm.com/
    echo.
    pause
    exit /b 1
)

echo Pulling latest changes from GitHub...
git pull
if errorlevel 1 (
    echo ERROR: Git pull failed. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

echo Updating dependencies...
pip install --upgrade gradio pandas pydub requests keyboard && pip install "moviepy<2"
if errorlevel 1 (
    echo ERROR: Failed to update dependencies.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Update complete!
echo ============================================
echo.
pause
