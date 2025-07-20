@echo off
echo ========================================
echo Smart File Indexer - Simple Launcher
echo ========================================
echo.

echo Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)
echo.

echo Checking if launcher exists...
if not exist "launcher.py" (
    echo ERROR: launcher.py not found!
    echo Make sure you're running this from the correct directory.
    pause
    exit /b 1
)
echo.

echo Starting launcher...
python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo LAUNCHER FAILED TO START
    echo ========================================
    echo.
    echo This might be due to missing dependencies.
    echo Try installing dependencies first:
    echo.
    echo 1. Run: install_simple.bat
    echo 2. Then try this launcher again
    echo.
    pause
    exit /b 1
)

echo.
echo Launcher closed successfully.
pause 