@echo off
cd /d "%~dp0"

rem ============================================================
rem  Project USB-Toolkit — launcher
rem  Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0
rem  Creates the venv + editable install on first run, then launches.
rem ============================================================

set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%PY%" (
    echo [SETUP] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    "%PY%" -m pip install --upgrade pip
    "%PY%" -m pip install -e .
)

"%PY%" -m usb_toolkit
if errorlevel 1 pause
