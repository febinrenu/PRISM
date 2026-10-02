
@echo off
cd /d "%~dp0"

echo Installing backend dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. See above for details.
    pause
    exit /b 1
)

python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('en_core_web_sm') else 1)"
if errorlevel 1 (
    echo Downloading spaCy model en_core_web_sm...
    python -m spacy download en_core_web_sm
    if errorlevel 1 (
        echo ERROR: spaCy model download failed.
        pause
        exit /b 1
    )
)

echo Starting uvicorn on http://127.0.0.1:8000 ...
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
