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

echo Fetching latest release tags from GitHub...
git fetch --tags --force
if errorlevel 1 (
    echo ERROR: Git fetch failed. Check your internet connection.
    pause
    exit /b 1
)

:: Find the latest release tag
set LATEST_TAG=
for /f "delims=" %%t in ('git tag --sort=-version:refname') do (
    if not defined LATEST_TAG set LATEST_TAG=%%t
)

if not defined LATEST_TAG (
    echo ERROR: No release tags found in repository.
    pause
    exit /b 1
)

echo Latest release: %LATEST_TAG%
git checkout %LATEST_TAG%
if errorlevel 1 (
    echo ERROR: Failed to checkout %LATEST_TAG%.
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
pip install --upgrade -r requirements.txt
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
