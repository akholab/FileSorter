@echo off
echo Starting Smart File Indexer Launcher...
echo.
echo This will open the launcher where you can choose between GUI and System Tray modes.
echo.

REM Try to activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    if %errorlevel% neq 0 (
        echo Warning: Failed to activate virtual environment, using global Python
    )
) else (
    echo No virtual environment found, using global Python
)

echo Starting launcher...
python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start the launcher!
    echo.
    echo Possible solutions:
    echo 1. Make sure Python is installed and in PATH
    echo 2. Try running: python --version
    echo 3. Try installing dependencies first: install.bat
    echo 4. Try the simple installation: install_simple.bat
    echo.
    pause
    exit /b 1
)

pause 