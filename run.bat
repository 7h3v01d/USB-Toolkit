@echo off
cd /d "%~dp0"

rem ============================================================
rem  Project USB-Toolkit — launcher
rem  Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0
rem
rem  Creates the venv on first run. ALWAYS refreshes the editable
rem  install before launch so the venv can never run stale code
rem  after the source folder is updated or moved.
rem ============================================================

set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" (
    echo [SETUP] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    "%PY%" -m pip install --upgrade pip
)

"%PY%" -m pip install -e . --quiet
"%PY%" -m usb_toolkit
if errorlevel 1 pause
