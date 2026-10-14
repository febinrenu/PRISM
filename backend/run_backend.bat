@echo off
:: Run the backend on its own. start.bat at the project root sets up the
:: environment and runs the full app; use this only for the API alone.
cd /d "%~dp0"

set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo No .venv found. Run start.bat from the project root once to set it up.
    pause
    exit /b 1
)

echo Starting uvicorn on http://127.0.0.1:8000 ...
"%PY%" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
