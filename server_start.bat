@echo off
REM Ableton Set Manager - Start HTTP Server with Environment Setup
REM Place this file in the same directory as server.py and setlist.json

echo Starting Ableton Set Manager...

REM Switch to script directory
cd /d "%~dp0"

REM Check if virtual environment exists, create if not
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

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
python -c "import pyautogui, psutil" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    if exist "requirements.txt" (
        pip install -r requirements.txt
    ) else (
        pip install pyautogui psutil pywin32
    )
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo Dependencies installed successfully.
) else (
    echo Dependencies already installed.
)

REM Start the server
echo Starting server...
python server.py

REM Deactivate virtual environment when done
deactivate

echo Server stopped. Press any key to close...
pause