@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   MedGraphRAG - One-Click Startup
echo ============================================
echo.

:: ---- Path Config ----
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "CONDA_ENV=DP_QA_improve"
set "CONDA_BASE=D:\Miniconda3"
set "NEO4J_HOME=D:\neo4j-community-5.26.0"
set "PYTHON=%CONDA_BASE%\envs\%CONDA_ENV%\python.exe"

cd /d "%PROJECT_DIR%"

:: ---- 1. Activate Conda ----
echo [1/5] Activating Conda environment...
call "%CONDA_BASE%\Scripts\activate.bat" "%CONDA_BASE%"
call conda activate "%CONDA_ENV%"
if errorlevel 1 (
    echo [ERROR] Failed to activate conda env: %CONDA_ENV%
    echo   Create it first: conda create -n %CONDA_ENV% python=3.13
    pause
    exit /b 1
)
echo   Conda environment %CONDA_ENV% activated

:: ---- 2. Fix encoding + Install deps ----
echo [2/5] Checking and installing Python dependencies...

:: Fix UTF-16 requirements.txt to UTF-8 if needed
set "FIX_SCRIPT=%TEMP%\_fix_req.py"
(
echo import sys
echo with open(r"%PROJECT_DIR%\requirements.txt", "rb"^) as f:
echo     content = f.read(^)
echo if content[:2] == b'\xff\xfe':
echo     content = content[2:].decode('utf-16-le'^).encode('utf-8'^)
echo elif content[:2] == b'\xfe\xff':
echo     content = content[2:].decode('utf-16-be'^).encode('utf-8'^)
echo with open(r"%PROJECT_DIR%\requirements.txt", "wb"^) as f:
echo     f.write(content^)
echo     print("    requirements.txt: UTF-16 -> UTF-8 converted"^)
) > "%FIX_SCRIPT%"

"%PYTHON%" -c "h=open(r'%PROJECT_DIR%\requirements.txt','rb').read(2); exit(0 if h==b'\xff\xfe' or h==b'\xfe\xff' else 1)" >nul 2>&1
if %errorlevel% equ 0 (
    echo   Detected UTF-16 encoding in requirements.txt, converting...
    "%PYTHON%" "%FIX_SCRIPT%"
)
del "%FIX_SCRIPT%" 2>nul

pip install -r requirements.txt -q
echo   Python dependencies ready

:: ---- 3. Start Neo4j ----
echo [3/5] Checking Neo4j status...
curl -s http://localhost:7474 >nul 2>&1
if not errorlevel 1 (
    echo   Neo4j is already running
    goto :neo4j_ready
)
:: Try service mode first, fall back to console mode
call "%NEO4J_HOME%\bin\neo4j.bat" start 2>&1 | findstr /i "not installed" >nul
if %errorlevel% equ 0 (
    echo   Neo4j service not installed, starting in console mode...
    set "NEO4J_BAT=%TEMP%\_neo4j_console.bat"
    (
    echo @echo off
    echo title Neo4j Console
    echo cd /d "%NEO4J_HOME%\bin"
    echo call neo4j.bat console
    ) > "!NEO4J_BAT!"
    start "Neo4j-Console" "!NEO4J_BAT!"
) else (
    echo   Neo4j started in service mode
)
echo   Waiting for Neo4j to be ready...
for /l %%i in (1,1,30) do (
    timeout /t 2 /nobreak >nul
    curl -s http://localhost:7474 >nul 2>&1
    if not errorlevel 1 (
        echo   Neo4j is ready
        goto :neo4j_ready
    )
    echo   Waiting... (%%i/30^)
)
echo   [WARN] Neo4j startup timed out, please check manually
:neo4j_ready

:: ---- 4. Start FastAPI backend ----
echo [4/5] Starting FastAPI backend (port 8000)...

set "BACKEND_BAT=%TEMP%\_medgraph_backend.bat"
(
echo @echo off
echo title MedGraphRAG Backend
echo cd /d "%PROJECT_DIR%"
echo echo Starting FastAPI backend...
echo %PYTHON% -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
echo pause
) > "%BACKEND_BAT%"

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [WARN] Port 8000 is already in use, skip starting
) else (
    start "MedGraphRAG-Backend" "%BACKEND_BAT%"
    echo   FastAPI backend started (http://localhost:8000^)
)

:: ---- 5. Start Vue frontend ----
echo [5/5] Starting Vue frontend (port 3000)...

set "FRONTEND_BAT=%TEMP%\_medgraph_frontend.bat"
(
echo @echo off
echo title MedGraphRAG Frontend
echo cd /d "%PROJECT_DIR%\frontend"
echo echo Starting Vue frontend...
echo npm run dev
echo pause
) > "%FRONTEND_BAT%"

if not exist "%PROJECT_DIR%\frontend\node_modules\" (
    echo   First run: installing frontend dependencies...
    pushd "%PROJECT_DIR%\frontend"
    call npm install
    popd
)
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [WARN] Port 3000 is already in use, skip starting
) else (
    start "MedGraphRAG-Frontend" "%FRONTEND_BAT%"
    echo   Vue frontend started (http://localhost:3000^)
)

echo.
echo ============================================
echo   Startup complete!
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo.
echo   Close this window to stop all services.
echo ============================================
pause
