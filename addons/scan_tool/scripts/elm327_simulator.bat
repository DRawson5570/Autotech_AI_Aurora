@echo off
REM ELM327 Simulator for Windows
REM Usage: elm327_simulator.bat [start|stop|status] [state]
REM
REM Example: elm327_simulator.bat start lean_both_banks

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."
set "PID_FILE=%TEMP%\elm327_simulator.pid"
set "LOG_FILE=%TEMP%\elm327_simulator.log"

REM Default settings
if not defined ELM327_SIM_PORT set "ELM327_SIM_PORT=35000"
if not defined ELM327_SIM_HOST set "ELM327_SIM_HOST=0.0.0.0"
if not defined ELM327_SIM_STATE set "ELM327_SIM_STATE=lean_both_banks"

REM Allow state override from command line
if not "%2"=="" set "ELM327_SIM_STATE=%2"

REM Find Python - check common locations
set "PYTHON="
if exist "%USERPROFILE%\anaconda3\envs\open-webui\python.exe" (
    set "PYTHON=%USERPROFILE%\anaconda3\envs\open-webui\python.exe"
) else if exist "%USERPROFILE%\miniconda3\envs\open-webui\python.exe" (
    set "PYTHON=%USERPROFILE%\miniconda3\envs\open-webui\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON=python"
    ) else (
        echo Error: Python not found. Please install Python or set PYTHON environment variable.
        exit /b 1
    )
)

if "%1"=="" goto usage
if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="status" goto status
if "%1"=="restart" goto restart
goto usage

:start
echo Starting ELM327 Simulator...
echo   Port: %ELM327_SIM_PORT%
echo   Host: %ELM327_SIM_HOST%
echo   State: %ELM327_SIM_STATE%
echo   Log: %LOG_FILE%
echo.

cd /d "%PROJECT_ROOT%"

REM Check if already running
netstat -an | findstr ":%ELM327_SIM_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo Port %ELM327_SIM_PORT% is already in use. Simulator may already be running.
    goto status
)

REM Start the simulator in background
start /b "" "%PYTHON%" -m addons.scan_tool.simulator --port %ELM327_SIM_PORT% --host %ELM327_SIM_HOST% --state %ELM327_SIM_STATE% > "%LOG_FILE%" 2>&1

REM Wait a moment for startup
timeout /t 2 /nobreak >nul

REM Verify it started
netstat -an | findstr ":%ELM327_SIM_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo.
    echo [OK] ELM327 Simulator started successfully
    echo     Connect with: telnet localhost %ELM327_SIM_PORT%
) else (
    echo.
    echo [FAIL] Failed to start ELM327 Simulator
    echo        Check log: %LOG_FILE%
    type "%LOG_FILE%"
)
goto end

:stop
echo Stopping ELM327 Simulator...

REM Find and kill Python processes running the simulator
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /fo list ^| findstr "PID:"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr "addons.scan_tool.simulator" >nul 2>&1
    if !errorlevel! equ 0 (
        echo Killing process %%a
        taskkill /f /pid %%a >nul 2>&1
    )
)

REM Also check pythonw.exe
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq pythonw.exe" /fo list ^| findstr "PID:"') do (
    wmic process where "ProcessId=%%a" get CommandLine 2>nul | findstr "addons.scan_tool.simulator" >nul 2>&1
    if !errorlevel! equ 0 (
        echo Killing process %%a
        taskkill /f /pid %%a >nul 2>&1
    )
)

timeout /t 1 /nobreak >nul

netstat -an | findstr ":%ELM327_SIM_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo [WARN] Port %ELM327_SIM_PORT% still in use. May need manual cleanup.
) else (
    echo [OK] ELM327 Simulator stopped
)
goto end

:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
goto end

:status
echo Checking ELM327 Simulator status...
echo.

netstat -an | findstr ":%ELM327_SIM_PORT% " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] ELM327 Simulator is running on port %ELM327_SIM_PORT%
    
    REM Try to find the process
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%ELM327_SIM_PORT% " ^| findstr "LISTENING"') do (
        echo     PID: %%a
    )
) else (
    echo [--] ELM327 Simulator is NOT running
)
goto end

:usage
echo.
echo ELM327 Simulator Control Script for Windows
echo ============================================
echo.
echo Usage: %~nx0 {start^|stop^|restart^|status} [state]
echo.
echo Commands:
echo   start   - Start the simulator
echo   stop    - Stop the simulator
echo   restart - Restart the simulator
echo   status  - Check if simulator is running
echo.
echo Environment variables:
echo   ELM327_SIM_PORT  - Port to listen on (default: 35000)
echo   ELM327_SIM_HOST  - Host to bind to (default: 0.0.0.0)
echo   ELM327_SIM_STATE - Vehicle state to simulate (default: lean_both_banks)
echo.
echo Available states:
echo   normal, overheating, running_cold, lean_both_banks, lean_bank1,
echo   rich_both_banks, misfire_cyl3, random_misfire, cat_degraded,
echo   o2_sensor_lazy, maf_dirty
echo.
echo Examples:
echo   %~nx0 start
echo   %~nx0 start overheating
echo   set ELM327_SIM_PORT=35001 ^& %~nx0 start
goto end

:end
endlocal
