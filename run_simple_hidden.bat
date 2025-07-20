@echo off
REM Smart File Indexer - Simple Hidden Launcher
REM This version runs without showing any terminal window

REM Check if pythonw is available
pythonw.exe --version >nul 2>&1
if %errorlevel% neq 0 (
    REM If pythonw not available, try to show error in a minimal way
    echo Python is not installed or pythonw.exe not available
    echo Please install Python from https://python.org
    timeout /t 3 >nul
    exit /b 1
)

REM Check if launcher exists
if not exist "launcher.py" (
    echo launcher.py not found!
    timeout /t 3 >nul
    exit /b 1
)

REM Start launcher without showing any window
start "" /B pythonw.exe launcher.py

REM Exit immediately
exit 