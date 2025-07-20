@echo off
echo ========================================
echo Smart File Indexer - Installation Debug
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

echo Checking pip installation...
pip --version
if %errorlevel% neq 0 (
    echo ERROR: pip is not installed or not in PATH
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)
echo.

echo Checking if virtual environment exists...
if not exist "venv" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Please ensure you have venv module available
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
) else (
    echo Virtual environment found.
)
echo.

echo Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    echo Please check if venv\Scripts\activate.bat exists
    pause
    exit /b 1
)
echo Virtual environment activated.
echo.

echo Upgrading pip...
python -m pip install --upgrade pip
echo.

echo Installing requirements...
echo Current directory: %CD%
echo Requirements file: requirements.txt
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found in current directory
    pause
    exit /b 1
)
echo.

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo INSTALLATION FAILED
    echo ========================================
    echo.
    echo Common solutions:
    echo 1. Make sure you have internet connection
    echo 2. Try running: pip install --upgrade pip
    echo 3. Try installing packages one by one:
    echo    pip install pillow
    echo    pip install watchdog
    echo    pip install psutil
    echo    pip install pystray
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo You can now run the application with: run.bat
echo.
pause 