@echo off
REM Ableton Set Manager - Windows server launcher

echo Starting Ableton Set Manager...

REM Switch to repository root.
cd /d "%~dp0.."

REM Check if virtual environment exists, create if not.
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment. Make sure Python is installed.
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import psutil, win32api, win32con, win32gui" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install shared dependencies.
        pause
        exit /b 1
    )
    pip install -r windows\requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install Windows dependencies.
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
) else (
    echo Dependencies already installed.
)

echo Starting server...
python server.py

deactivate

echo Server stopped. Press any key to close...
pause
