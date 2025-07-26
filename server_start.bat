@echo off
REM Ableton Set Manager - Start HTTP Server
REM Place this file in the same directory as server.py and setlist.json

REM Switch to script directory and start server
cd /d "%~dp0"
python server.py

REM Close this window to stop the server