@echo off
echo ========================================
echo Smart File Indexer - Simple Installation
echo ========================================
echo.
echo This will install packages globally (no virtual environment)
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

echo Checking pip installation...
pip --version
if %errorlevel% neq 0 (
    echo ERROR: pip is not installed or not in PATH
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)
echo.

echo Upgrading pip...
python -m pip install --upgrade pip
echo.

echo Installing requirements globally...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo INSTALLATION FAILED
    echo ========================================
    echo.
    echo Trying alternative installation method...
    echo.
    
    echo Installing packages individually...
    pip install pillow
    pip install watchdog
    pip install psutil
    pip install pystray
    
    echo.
    echo Individual installation completed.
    echo Some packages may have failed, but the core functionality should work.
    echo.
    pause
    exit /b 0
)

echo.
echo ========================================
echo INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo You can now run the application with: run.bat
echo.
pause 