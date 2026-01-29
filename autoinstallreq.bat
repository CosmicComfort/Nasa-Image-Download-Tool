@echo off
setlocal enabledelayedexpansion

echo ========================================
echo NASA Download Tool - Auto Setup
echo ========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Installing Python...
    echo.
    
    :: Download Python installer (latest stable version)
    echo Downloading Python installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.1/python-3.12.1-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"
    
    :: Install Python with pip and add to PATH
    echo Installing Python (this may take a minute)...
    %TEMP%\python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0
    
    :: Clean up installer
    del "%TEMP%\python-installer.exe"
    
    echo Python installation complete!
    echo Please close this window and run the script again for changes to take effect.
    pause
    exit /b
) else (
    echo Python is already installed.
    python --version
)

echo.
echo ========================================
echo Installing Requirements
echo ========================================
echo.

:: Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

:: Check if requirements.txt exists
if not exist "%SCRIPT_DIR%requirements.txt" (
    echo ERROR: requirements.txt not found in %SCRIPT_DIR%
    echo Please make sure requirements.txt is in the same folder as this batch file.
    pause
    exit /b 1
)

:: Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install requirements
echo.
echo Installing packages from requirements.txt...
python -m pip install -r "%SCRIPT_DIR%requirements.txt"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo Setup Complete!
    echo ========================================
    echo.
    echo You can now run NASA_DownloadToolV2.0.py
    echo.
) else (
    echo.
    echo ERROR: Failed to install requirements.
    echo Please check the error messages above.
)

pause