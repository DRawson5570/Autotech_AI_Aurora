# ELM327 Bluetooth Setup Script for Windows
# Run in PowerShell as Administrator
#
# Usage: .\setup_windows.ps1

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  ELM327 Bluetooth Setup for Windows" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Warning: Some operations may need Administrator privileges" -ForegroundColor Yellow
}

# Check Bluetooth
Write-Host "1. Checking Bluetooth..." -ForegroundColor White
$btAdapter = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' }
if ($btAdapter) {
    Write-Host "   OK Bluetooth adapter found" -ForegroundColor Green
} else {
    Write-Host "   X No Bluetooth adapter found or not enabled" -ForegroundColor Red
    Write-Host "   Enable Bluetooth in Settings > Bluetooth & devices"
    exit 1
}

# List paired Bluetooth devices
Write-Host ""
Write-Host "2. Looking for paired Bluetooth devices..." -ForegroundColor White
$btDevices = Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -match "OBD|ELM|VGATE|VEEPEAK|Vlink|BAFX" }
if ($btDevices) {
    Write-Host "   Found ELM327-like devices:" -ForegroundColor Green
    $btDevices | ForEach-Object { Write-Host "     - $($_.FriendlyName)" }
} else {
    Write-Host "   No ELM327 devices found. Checking all Bluetooth devices:" -ForegroundColor Yellow
    Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' } | ForEach-Object { Write-Host "     - $($_.FriendlyName)" }
}

# List COM ports
Write-Host ""
Write-Host "3. Available COM ports:" -ForegroundColor White
$comPorts = [System.IO.Ports.SerialPort]::GetPortNames()
if ($comPorts) {
    $comPorts | ForEach-Object { 
        Write-Host "     $_" -ForegroundColor Cyan
    }
} else {
    Write-Host "   No COM ports found" -ForegroundColor Yellow
}

# Get Bluetooth COM ports from registry
Write-Host ""
Write-Host "4. Bluetooth Serial Ports (from registry):" -ForegroundColor White
try {
    $btComPorts = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Enum\BTHENUM\*\*" -ErrorAction SilentlyContinue | 
        Where-Object { $_.FriendlyName -like "*Serial*" -or $_.FriendlyName -like "*SPP*" }
    if ($btComPorts) {
        $btComPorts | ForEach-Object { Write-Host "     $($_.FriendlyName)" }
    } else {
        Write-Host "   Check Device Manager > Ports (COM & LPT) for Bluetooth ports" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   Could not read registry (try running as Administrator)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Setup Instructions" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If your ELM327 is not paired yet:" -ForegroundColor White
Write-Host "  1. Turn on your ELM327 (plug into car OBD port)"
Write-Host "  2. Go to Settings > Bluetooth & devices"
Write-Host "  3. Click 'Add device' > Bluetooth"
Write-Host "  4. Select your ELM327 (OBDII, VEEPEAK, etc.)"
Write-Host "  5. PIN is usually: 1234 or 0000"
Write-Host ""
Write-Host "After pairing:" -ForegroundColor White
Write-Host "  1. Open Device Manager"
Write-Host "  2. Expand 'Ports (COM & LPT)'"
Write-Host "  3. Find 'Standard Serial over Bluetooth link (COMx)'"
Write-Host "  4. Note the COM port number (e.g., COM5)"
Write-Host ""
Write-Host "Start the gateway:" -ForegroundColor Green
Write-Host "  python -m addons.scan_tool.gateway.server"
Write-Host ""
Write-Host "Then connect using the COM port (e.g., COM5)" -ForegroundColor Green
Write-Host ""

# Prompt for COM port
$comPort = Read-Host "Enter your ELM327 COM port (e.g., COM5) or press Enter to skip"
if ($comPort) {
    Write-Host ""
    Write-Host "Testing connection to $comPort..." -ForegroundColor White
    
    # Quick test - try to open the port
    try {
        $port = New-Object System.IO.Ports.SerialPort $comPort, 38400, None, 8, One
        $port.ReadTimeout = 2000
        $port.Open()
        $port.WriteLine("ATZ")
        Start-Sleep -Milliseconds 500
        $response = $port.ReadExisting()
        $port.Close()
        
        if ($response -match "ELM") {
            Write-Host "   OK ELM327 responded: $response" -ForegroundColor Green
        } else {
            Write-Host "   Got response: $response" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "   X Could not open $comPort : $_" -ForegroundColor Red
        Write-Host "   Make sure no other application is using the port" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Ready to start gateway!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run:" -ForegroundColor White
Write-Host "  python -m addons.scan_tool.gateway.server" -ForegroundColor Cyan
Write-Host ""
Write-Host "Then on your phone browser:" -ForegroundColor White
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
Write-Host "  http://${ip}:8327/ui" -ForegroundColor Cyan
Write-Host ""
