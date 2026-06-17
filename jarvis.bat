@echo off
:: ============================================================
::  JARVIS Launcher
::  Run this from anywhere to start the JARVIS CLI.
:: ============================================================

set JARVIS_DIR=c:\Users\pkmuk\Desktop\Apps\jarvis

:: Change to project directory
cd /d "%JARVIS_DIR%"

:: Activate virtual environment if it exists
if exist "%JARVIS_DIR%\venv\Scripts\activate.bat" (
    call "%JARVIS_DIR%\venv\Scripts\activate.bat"
) else if exist "%JARVIS_DIR%\.venv\Scripts\activate.bat" (
    call "%JARVIS_DIR%\.venv\Scripts\activate.bat"
) else (
    echo [JARVIS] No virtual environment found, using system Python.
)

:: Launch JARVIS CLI
python cli.py

:: Keep window open on error
if errorlevel 1 (
    echo.
    echo [JARVIS] Exited with an error. Press any key to close...
    pause > nul
)
