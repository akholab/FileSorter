@echo off
REM Smart File Indexer - Hidden Launcher
REM This version runs without showing any terminal window

REM Try to activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat >nul 2>&1
    if %errorlevel% equ 0 (
        REM Use pythonw from virtual environment
        start "" /B "venv\Scripts\pythonw.exe" launcher.py
    ) else (
        REM Fallback to global pythonw
        start "" /B pythonw.exe launcher.py
    )
) else (
    REM No virtual environment, use global pythonw
    start "" /B pythonw.exe launcher.py
)

REM Exit immediately without showing any window
exit 