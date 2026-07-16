@echo off
cd /d "%~dp0"
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
echo.
echo Setup complete. Launch with run.bat
pause
