# ELM327 Live Diagnostics Integration

AI-directed OBD-II diagnostics with live data monitoring and bidirectional control.

## Overview

This module enables the AI to connect to vehicles via ELM327-compatible OBD-II adapters,
read diagnostic trouble codes, monitor live sensor data, and (where supported) control
actuators for diagnostic testing.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Open WebUI    │     │  ELM327 Service │     │   ELM327        │
│   (AI + User)   │────▶│  (This Module)  │────▶│   Adapter       │────▶ Vehicle
│                 │◀────│                 │◀────│   (BT/WiFi/USB) │◀────
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Features

### Tier 1: Standard OBD-II (All Vehicles 1996+)
- Read/Clear DTCs (trouble codes)
- Read live PIDs (sensor data)
- Read VIN
- Read freeze frame data

### Tier 2: Enhanced OBD-II (Many Vehicles)
- Mode $08 actuator tests (fan, EVAP, etc.)
- Vehicle information (calibration IDs)

### Tier 3: Manufacturer-Specific (Vehicle Dependent)
- UDS bidirectional control (where supported)
- Extended PIDs

## Installation

```bash
# Required
pip install pyserial-asyncio

# Optional for Bluetooth
pip install bleak
```

## Quick Start

### Programmatic Usage

```python
import asyncio
from addons.elm327 import ELM327Service

async def main():
    async with ELM327Service() as elm:
        # Connect via WiFi
        await elm.connect('wifi', '192.168.0.10:35000')
        
        # Read DTCs
        dtcs = await elm.read_dtcs()
        for dtc in dtcs:
            print(f"{dtc.code}: {dtc.description}")
        
        # Read live data
        readings = await elm.read_pids(['RPM', 'COOLANT_TEMP', 'STFT_B1'])
        for name, reading in readings.items():
            print(f"{name}: {reading.value} {reading.unit}")
        
        # Monitor fuel trims
        trims = await elm.read_fuel_trims()
        print(f"STFT Bank 1: {trims['STFT_B1'].value}%")

asyncio.run(main())
```

### Open WebUI Tool Usage

The AI can use these tools in conversation:

```
User: "Connect to my scan tool and check for codes"

AI: [calls elm327_connect('wifi', '192.168.0.10:35000')]
    "Connected! VIN: 1J4PN2GK2CW123456, 45 PIDs supported"
    
    [calls elm327_read_dtcs()]
    "Found 2 stored codes:
     • P0171: System Too Lean (Bank 1)
     • P0174: System Too Lean (Bank 2)
     
     Both banks lean - this suggests a common cause like a vacuum leak."

User: "Can you monitor fuel trims while I spray for leaks?"

AI: [calls elm327_monitor_pids('STFT_B1,STFT_B2', 30, 0.5)]
    "Monitoring for 30 seconds... I'll watch for changes.
    
    Baseline: STFT B1: +12%, STFT B2: +14%
    
    [10 seconds in]
    SPIKE detected! STFT B1 dropped to +2% 
    
    I saw a significant change - where were you spraying just now?"
```

## Connection Types

### WiFi (Most Common)
```python
await elm.connect('wifi', '192.168.0.10:35000')
```

### Bluetooth (Linux)
```python
await elm.connect('bluetooth', '/dev/rfcomm0')
```

### USB
```python
await elm.connect('usb', '/dev/ttyUSB0')
```

## Common PIDs

| PID | Name | Description | Unit |
|-----|------|-------------|------|
| 0x0C | RPM | Engine RPM | rpm |
| 0x0D | SPEED | Vehicle Speed | km/h |
| 0x05 | COOLANT_TEMP | Coolant Temperature | °C |
| 0x0F | IAT | Intake Air Temperature | °C |
| 0x04 | LOAD | Calculated Engine Load | % |
| 0x11 | THROTTLE_POS | Throttle Position | % |
| 0x06 | STFT_B1 | Short Term Fuel Trim Bank 1 | % |
| 0x07 | LTFT_B1 | Long Term Fuel Trim Bank 1 | % |
| 0x08 | STFT_B2 | Short Term Fuel Trim Bank 2 | % |
| 0x09 | LTFT_B2 | Long Term Fuel Trim Bank 2 | % |
| 0x10 | MAF | Mass Air Flow | g/s |
| 0x0B | MAP | Manifold Pressure | kPa |
| 0x0E | TIMING_ADV | Timing Advance | degrees |
| 0x42 | VOLTAGE | Control Module Voltage | V |

## AI-Directed Diagnostic Procedures

The AI can guide users through diagnostic tests while monitoring live data:

### Vacuum Leak Test
```python
# AI monitors fuel trims while user sprays brake cleaner
samples = await elm.monitor_pids(['STFT_B1', 'STFT_B2'], 30, 0.5)
# AI analyzes for sudden changes indicating leak location
```

### Cooling Fan Test
```python
# AI commands fan on to verify operation
await elm.actuator_test('cooling_fan', 'on', duration=10)
# User confirms fan is running
```

### RPM-Specific Data Capture
```python
# AI waits for user to reach target RPM
await elm.wait_for_condition('RPM', lambda v: v > 2500, timeout=30)
# Then captures snapshot at that RPM
snapshot = await elm.capture_diagnostic_snapshot()
```

## Module Structure

```
addons/elm327/
├── __init__.py          # Package exports
├── connection.py        # BT/WiFi/USB connection handling
├── protocol.py          # OBD-II protocol implementation
├── pids.py              # PID definitions and decoders
├── bidirectional.py     # Actuator control (Mode $08, UDS)
├── service.py           # High-level API
├── openwebui_tool.py    # Open WebUI tool interface
└── README.md            # This file
```

## Supported Adapters

Tested with:
- Generic ELM327 WiFi adapters
- Generic ELM327 Bluetooth adapters
- OBDLink MX+
- BAFX Products Bluetooth

Note: Cheap clone adapters may have compatibility issues with some vehicles.

## Safety Notes

⚠️ **Actuator Control**: Bidirectional control is disabled by default. Only enable
if you understand what you're doing. Improper use can damage vehicle components.

⚠️ **DTC Clearing**: Clearing DTCs is disabled by default. Only clear codes after
making repairs - the light will return if the problem isn't fixed.

⚠️ **While Driving**: Do not use this tool while driving. Pull over safely first.

## Troubleshooting

### "No Data" Response
- Vehicle may not support that PID
- Check connection and try a different PID
- Some PIDs only available when engine running

### Connection Timeout
- Check adapter is powered (usually has LED)
- Verify IP address/device path
- Try disconnecting and reconnecting

### Intermittent Data
- May indicate weak connection (especially Bluetooth)
- Try moving adapter for better signal
- Consider WiFi adapter for more reliable connection

## Future Enhancements

- [ ] WebSocket streaming for real-time dashboards
- [ ] Vehicle-specific PID databases
- [ ] Freeze frame analysis
- [ ] Data logging to file
- [ ] Integration with predictive diagnostics engine
