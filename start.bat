@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
pushd "%ROOT%"

echo ============================================
echo  PRISM Phase 1 - Legal Cognition Engine
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    popd
    pause
    exit /b 1
)

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Install Node.js 18+ from nodejs.org
    popd
    pause
    exit /b 1
)

:: Stop stale PRISM listeners so the launcher always lands on the expected ports.
call :FreePort 8000
call :FreePort 3000
call :FreePort 3001
call :FreePort 3002

echo Starting PRISM backend on http://localhost:8000...
start "PRISM Backend" cmd /k "%ROOT%backend\run_backend.bat"

timeout /t 3 /nobreak >nul

echo Starting PRISM frontend on http://localhost:3000...
if not exist "%ROOT%frontend\node_modules\" (
    pushd "%ROOT%frontend"
    npm install
    if errorlevel 1 (
        echo ERROR: Frontend dependency install failed.
        popd
        popd
        pause
        exit /b 1
    )
    popd
)
start "PRISM Frontend" /D "%ROOT%frontend" cmd /k "npm run dev -- --port 3000"

echo.
echo ============================================
echo  PRISM is starting up!
echo  Backend:  http://localhost:8000
echo  Frontend: http://localhost:3000
echo  API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo NOTE: First startup takes a few minutes to
echo download models (spaCy + sentence-transformers)
echo.
popd
pause
exit /b 0

:FreePort
set "PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R ":%PORT% .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
exit /b 0
