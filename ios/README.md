# Autotech Scan - iOS App

Native iOS app for connecting to OBD2 Bluetooth scanners and getting AI-powered vehicle diagnostics.

## Features

- **Bluetooth LE Connection**: Connects to OBDLink MX+, Veepeak, and other BLE OBD adapters
- **VIN Reading**: Automatically reads and decodes vehicle identification
- **DTC Scanning**: Reads stored and pending diagnostic trouble codes
- **Live Data**: Real-time monitoring of engine RPM, speed, temperatures, and more
- **AI Diagnosis**: Sends data to Autotech AI server for intelligent analysis
- **Clear Codes**: Ability to clear DTCs after repairs

## Requirements

- iOS 16.0+
- iPhone or iPad with Bluetooth LE
- Compatible OBD2 Bluetooth adapter (BLE, not Classic Bluetooth)

## Supported Adapters

- OBDLink MX+ (recommended)
- OBDLink CX
- Veepeak OBDCheck BLE+
- Carista OBD2 Adapter
- Other ELM327/STN-based BLE adapters

## Building

1. Open `AutotechScan.xcodeproj` in Xcode 15+
2. Select your development team in Signing & Capabilities
3. Build and run on a physical device (Bluetooth requires real hardware)

## Architecture

```
AutotechScan/
├── AutotechScanApp.swift      # App entry point
├── ContentView.swift          # Main view with connection UI
├── Bluetooth/
│   ├── BluetoothManager.swift # CoreBluetooth wrapper
│   └── ELM327Protocol.swift   # OBD command protocol
├── API/
│   └── APIClient.swift        # Server communication
├── Models/
│   └── Models.swift           # Data models
├── Views/
│   ├── ScanView.swift         # Main scanning interface
│   └── DiagnosisView.swift    # AI diagnosis display
└── ViewModels/
    └── ScanViewModel.swift    # Business logic
```

## API Integration

The app communicates with the Autotech AI server at:
- Production: `https://automotive.aurora-sentient.net/api/v1/scan/`

Endpoints used:
- `POST /diagnose` - Send scan data for AI analysis
- `GET /vin/decode?vin=XXX` - Decode VIN for vehicle info

## Notes

- Classic Bluetooth adapters (non-BLE) are NOT supported on iOS
- The app requires physical hardware for testing - simulator has no Bluetooth
- Bluetooth permissions must be granted for the app to function
