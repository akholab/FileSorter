@echo off
echo Installing Smart File Indexer Dependencies...
echo.
echo This will install all required Python packages.
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Trying global installation instead...
        goto :global_install
    )
)

REM Try virtual environment installation
echo Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment
    echo Trying global installation instead...
    goto :global_install
)

echo Installing in virtual environment...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo Virtual environment installation failed!
    echo Trying global installation...
    goto :global_install
)

echo.
echo Installation complete in virtual environment!
echo You can now run the application with: run.bat
pause
exit /b 0

:global_install
echo.
echo Installing packages globally...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo Installation failed! Please check the error messages above.
    echo Try running install_debug.bat for more detailed information.
    pause
    exit /b 1
)
echo.
echo Installation complete globally!
echo You can now run the application with: run.bat
pause 