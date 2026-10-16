@echo off
setlocal EnableExtensions

:: PRISM launcher.
::   start.bat         set up what is missing, then run the full app (production build)
::   start.bat dev     same, with hot reload for backend and frontend
::   start.bat stop    stop the PRISM servers

set "ROOT=%~dp0"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=prod"
if /I "%MODE%"=="stop" goto :Stop
if /I not "%MODE%"=="prod" if /I not "%MODE%"=="dev" (
    echo Usage: start.bat [dev^|stop]
    exit /b 1
)

set "VENV=%ROOT%.venv"
set "PY=%VENV%\Scripts\python.exe"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo ============================================
echo  PRISM  -  statutes, read and run
echo  mode: %MODE%
echo ============================================
echo.

:: ---------------------------------------------------------------- tools
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js not found. Install Node.js 18 or newer from nodejs.org
    goto :Fail
)
where curl >nul 2>&1
if errorlevel 1 (set "HAVE_CURL=0") else (set "HAVE_CURL=1")

:: ---------------------------------------------------------------- stale servers
call :Stop quiet

:: ---------------------------------------------------------------- python env
if exist "%PY%" goto :VenvReady
echo [setup] Creating the Python environment in .venv ...
set "SYSPY="
py -3.12 --version >nul 2>&1 && set "SYSPY=py -3.12"
if not defined SYSPY (
    python --version >nul 2>&1 && set "SYSPY=python"
)
if not defined SYSPY (
    echo ERROR: Python not found. Install Python 3.10 or newer from python.org
    goto :Fail
)
%SYSPY% -m venv "%VENV%"
if errorlevel 1 (
    echo ERROR: could not create .venv
    goto :Fail
)
:VenvReady

:: Install backend requirements only when requirements.txt changed.
fc /b "%BACKEND%\requirements.txt" "%VENV%\.prism-requirements" >nul 2>&1
if not errorlevel 1 goto :ReqsReady
echo [setup] Installing backend dependencies, first run takes several minutes ...
"%PY%" -m pip install --disable-pip-version-check -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo ERROR: pip install failed, see the output above.
    goto :Fail
)
copy /y "%BACKEND%\requirements.txt" "%VENV%\.prism-requirements" >nul
:ReqsReady

"%PY%" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('en_core_web_sm') else 1)"
if errorlevel 1 (
    echo [setup] Downloading the spaCy model en_core_web_sm ...
    "%PY%" -m spacy download en_core_web_sm
    if errorlevel 1 (
        echo ERROR: spaCy model download failed.
        goto :Fail
    )
)

if not exist "%BACKEND%\.env" (
    echo [setup] No backend\.env yet, copying backend\.env.example
    copy /y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
)

:: ---------------------------------------------------------------- ollama
set "LLM_BACKEND="
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"LLM_BACKEND=" "%BACKEND%\.env"') do (
    for /f "tokens=1" %%V in ("%%B") do set "LLM_BACKEND=%%V"
)
echo %LLM_BACKEND% | findstr /B /I "ollama" >nul
if errorlevel 1 goto :OllamaDone
if "%HAVE_CURL%"=="1" (
    curl -s -f -o nul --max-time 2 http://127.0.0.1:11434/api/tags
    if not errorlevel 1 (
        echo [ok] Ollama is already running
        goto :OllamaDone
    )
)
set "OLLAMA="
for /f "delims=" %%O in ('where ollama 2^>nul') do if not defined OLLAMA set "OLLAMA=%%O"
if not defined OLLAMA if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if defined OLLAMA (
    echo [start] Ollama on http://127.0.0.1:11434
    start "PRISM Ollama" /min "%OLLAMA%" serve
) else (
    echo [warn] LLM_BACKEND is %LLM_BACKEND% but Ollama is not installed.
    echo        The app runs; LLM extraction and chat answers need Ollama or LLM_BACKEND=groq.
)
:OllamaDone

:: ---------------------------------------------------------------- backend
set "RELOAD="
if /I "%MODE%"=="dev" set "RELOAD=--reload"
echo [start] Backend on http://127.0.0.1:8000
start "PRISM Backend" /D "%BACKEND%" cmd /k ""%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000 %RELOAD%"

:: ---------------------------------------------------------------- frontend
pushd "%FRONTEND%"
fc /b "package-lock.json" "node_modules\.prism-lock" >nul 2>&1
if not errorlevel 1 goto :ModulesReady
echo [setup] Installing frontend dependencies ...
call npm install --no-audit --no-fund
if errorlevel 1 (
    echo ERROR: npm install failed, see the output above.
    popd
    goto :Fail
)
copy /y "package-lock.json" "node_modules\.prism-lock" >nul
:ModulesReady

if not exist ".env.local" (
    echo [setup] Writing frontend\.env.local
    > ".env.local" echo NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
)
:: 127.0.0.1, not localhost: another server on port 8000 (Docker, WSL) can answer
:: "localhost" over IPv6. Move an untouched old default over.
findstr /X /C:"NEXT_PUBLIC_API_URL=http://localhost:8000" ".env.local" >nul 2>&1
if not errorlevel 1 (
    echo [setup] Pointing the frontend at 127.0.0.1:8000
    > ".env.local" echo NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
)

if /I "%MODE%"=="dev" (
    echo [start] Frontend on http://localhost:3000, dev server
    start "PRISM Frontend" /D "%FRONTEND%" cmd /k "npm run dev -- --port 3000"
    popd
    goto :Wait
)

node scripts\needs-build.mjs
if errorlevel 1 (
    echo [ok] Production build is up to date
) else (
    echo [build] Building the frontend, takes a few minutes ...
    call npm run build
    if errorlevel 1 (
        echo ERROR: the frontend build failed. Try: start.bat dev
        popd
        goto :Fail
    )
)
echo [start] Frontend on http://localhost:3000
start "PRISM Frontend" /D "%FRONTEND%" cmd /k "npm run start -- --port 3000"
popd

:: ---------------------------------------------------------------- wait, then open
:Wait
if not "%HAVE_CURL%"=="1" goto :Ready
echo.
echo Waiting for the backend, first start loads the language models ...
set /a N=0
:WaitBackend
curl -s -f -o nul --max-time 2 http://127.0.0.1:8000/health
if not errorlevel 1 goto :BackendUp
set /a N+=1
if %N% GEQ 150 (
    echo [warn] The backend is not answering yet, check the "PRISM Backend" window.
    goto :WaitFrontend0
)
timeout /t 2 /nobreak >nul
goto :WaitBackend
:BackendUp
echo [ok] Backend ready

:WaitFrontend0
set /a N=0
:WaitFrontend
curl -s -o nul --max-time 5 http://127.0.0.1:3000/
if not errorlevel 1 goto :FrontendUp
set /a N+=1
if %N% GEQ 90 (
    echo [warn] The frontend is not answering yet, check the "PRISM Frontend" window.
    goto :Ready
)
timeout /t 2 /nobreak >nul
goto :WaitFrontend
:FrontendUp
echo [ok] Frontend ready
start "" http://localhost:3000

:Ready
echo.
echo ============================================
echo  PRISM is running
echo  App:       http://localhost:3000
echo  Research:  http://localhost:3000/research
echo  API docs:  http://127.0.0.1:8000/docs
echo  Stop:      start.bat stop, or close the server windows
echo ============================================
echo.
exit /b 0

:Fail
echo.
pause
exit /b 1

:: ---------------------------------------------------------------- stop
:Stop
for %%T in ("PRISM Backend" "PRISM Frontend") do (
    taskkill /F /T /FI "WINDOWTITLE eq %%~T*" >nul 2>&1
)
for %%P in (8000 3000) do call :FreePort %%P
if /I not "%~1"=="quiet" echo PRISM servers stopped. Ollama, if started, is left running.
exit /b 0

:FreePort
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do (
    if not "%%P"=="0" call :StopIfPrism %%P
)
exit /b 0

:StopIfPrism
:: Only PRISM's own servers (python for the backend, node for the frontend);
:: never another program that happens to use the port, such as Docker.
for /f "tokens=1" %%I in ('tasklist /FI "PID eq %~1" /NH 2^>nul') do (
    if /I "%%I"=="python.exe" taskkill /F /T /PID %~1 >nul 2>&1
    if /I "%%I"=="node.exe" taskkill /F /T /PID %~1 >nul 2>&1
)
exit /b 0
