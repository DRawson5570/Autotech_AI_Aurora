@echo off
REM ELM327 Gateway Server - Windows Launcher
REM
REM Double-click this file to start the gateway server

echo.
echo  ========================================
echo    ELM327 Gateway Server
echo  ========================================
echo.

REM Check if Python is available
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  ERROR: Python not found in PATH
    echo  Install Python from python.org
    pause
    exit /b 1
)

REM Change to the autotech_ai directory
cd /d "%~dp0..\..\..\"

REM Get local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set IP=%%a
    goto :gotip
)
:gotip
set IP=%IP:~1%

echo  Starting server...
echo.
echo  On your phone, open Safari/Chrome and go to:
echo.
echo     http://%IP%:8327/ui
echo.
echo  ========================================
echo.

REM Run the server
python -m addons.scan_tool.gateway.server --port 8327

pause
