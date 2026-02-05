<#
.SYNOPSIS
    ELM327 Simulator Control Script for Windows PowerShell

.DESCRIPTION
    Start, stop, and manage the ELM327 OBD-II simulator service.
    
.PARAMETER Action
    The action to perform: Start, Stop, Restart, Status

.PARAMETER State
    The vehicle state to simulate (default: lean_both_banks)
    
.PARAMETER Port
    The TCP port to listen on (default: 35000)

.EXAMPLE
    .\elm327_simulator.ps1 Start
    
.EXAMPLE
    .\elm327_simulator.ps1 Start -State overheating
    
.EXAMPLE
    .\elm327_simulator.ps1 Stop
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("Start", "Stop", "Restart", "Status", "Logs")]
    [string]$Action,
    
    [Parameter(Position=1)]
    [ValidateSet("normal", "overheating", "running_cold", "lean_both_banks", 
                 "lean_bank1", "rich_both_banks", "misfire_cyl3", "random_misfire",
                 "cat_degraded", "o2_sensor_lazy", "maf_dirty")]
    [string]$State = "lean_both_banks",
    
    [int]$Port = 35000,
    
    [string]$Host = "0.0.0.0"
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path "$ScriptDir\..\..\..").Path
$LogFile = "$env:TEMP\elm327_simulator.log"
$ProcessName = "ELM327Simulator"

# Find Python
function Find-Python {
    $pythonPaths = @(
        "$env:USERPROFILE\anaconda3\envs\open-webui\python.exe",
        "$env:USERPROFILE\miniconda3\envs\open-webui\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    )
    
    foreach ($path in $pythonPaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    
    # Try PATH
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    
    throw "Python not found. Please install Python or conda environment 'open-webui'"
}

function Get-SimulatorProcess {
    Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
            $cmdLine -match "addons\.scan_tool\.simulator"
        } catch {
            $false
        }
    }
}

function Test-PortInUse {
    param([int]$Port)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return ($connections | Where-Object { $_.State -eq "Listen" }).Count -gt 0
}

function Start-Simulator {
    Write-Host "Starting ELM327 Simulator..." -ForegroundColor Cyan
    Write-Host "  Port: $Port"
    Write-Host "  Host: $Host"
    Write-Host "  State: $State"
    Write-Host "  Log: $LogFile"
    Write-Host ""
    
    # Check if already running
    if (Test-PortInUse -Port $Port) {
        Write-Host "[WARN] Port $Port is already in use" -ForegroundColor Yellow
        Get-SimulatorStatus
        return
    }
    
    $python = Find-Python
    Write-Host "Using Python: $python" -ForegroundColor DarkGray
    
    # Start the process
    Push-Location $ProjectRoot
    try {
        $processArgs = @{
            FilePath = $python
            ArgumentList = "-m", "addons.scan_tool.simulator", "--port", $Port, "--host", $Host, "--state", $State
            WindowStyle = "Hidden"
            RedirectStandardOutput = $LogFile
            RedirectStandardError = $LogFile
            PassThru = $true
        }
        
        $process = Start-Process @processArgs
        
        # Wait for startup
        Start-Sleep -Seconds 2
        
        if (Test-PortInUse -Port $Port) {
            Write-Host ""
            Write-Host "[OK] ELM327 Simulator started (PID: $($process.Id))" -ForegroundColor Green
            Write-Host "    Connect with: telnet localhost $Port" -ForegroundColor Gray
        } else {
            Write-Host ""
            Write-Host "[FAIL] Failed to start ELM327 Simulator" -ForegroundColor Red
            Write-Host "       Check log: $LogFile" -ForegroundColor Yellow
            if (Test-Path $LogFile) {
                Get-Content $LogFile -Tail 20
            }
        }
    } finally {
        Pop-Location
    }
}

function Stop-Simulator {
    Write-Host "Stopping ELM327 Simulator..." -ForegroundColor Cyan
    
    $processes = Get-SimulatorProcess
    
    if ($processes) {
        foreach ($proc in $processes) {
            Write-Host "  Killing process $($proc.Id)..." -ForegroundColor DarkGray
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
        
        Start-Sleep -Seconds 1
        
        if (-not (Test-PortInUse -Port $Port)) {
            Write-Host "[OK] ELM327 Simulator stopped" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Port $Port still in use" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[--] No simulator process found" -ForegroundColor Yellow
        
        # Try to find by port
        if (Test-PortInUse -Port $Port) {
            Write-Host "     But port $Port is in use by another process" -ForegroundColor Yellow
        }
    }
}

function Get-SimulatorStatus {
    Write-Host "ELM327 Simulator Status" -ForegroundColor Cyan
    Write-Host "========================" -ForegroundColor Cyan
    Write-Host ""
    
    $processes = Get-SimulatorProcess
    $portInUse = Test-PortInUse -Port $Port
    
    if ($processes -and $portInUse) {
        Write-Host "[OK] Simulator is running" -ForegroundColor Green
        foreach ($proc in $processes) {
            Write-Host "    PID: $($proc.Id)" -ForegroundColor Gray
            Write-Host "    Memory: $([math]::Round($proc.WorkingSet64/1MB, 2)) MB" -ForegroundColor Gray
        }
        Write-Host "    Port: $Port (listening)" -ForegroundColor Gray
    } elseif ($portInUse) {
        Write-Host "[WARN] Port $Port is in use but simulator process not found" -ForegroundColor Yellow
    } else {
        Write-Host "[--] Simulator is NOT running" -ForegroundColor Yellow
    }
}

function Show-Logs {
    if (Test-Path $LogFile) {
        Write-Host "Showing logs from: $LogFile" -ForegroundColor Cyan
        Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
        Write-Host ""
        Get-Content $LogFile -Wait -Tail 50
    } else {
        Write-Host "No log file found at: $LogFile" -ForegroundColor Yellow
    }
}

# Main execution
switch ($Action) {
    "Start" { Start-Simulator }
    "Stop" { Stop-Simulator }
    "Restart" { 
        Stop-Simulator
        Start-Sleep -Seconds 2
        Start-Simulator
    }
    "Status" { Get-SimulatorStatus }
    "Logs" { Show-Logs }
}
