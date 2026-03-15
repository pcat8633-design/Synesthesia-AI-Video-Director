@echo off
echo ============================================
echo  Synesthesia AI Video Director
echo ============================================
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
