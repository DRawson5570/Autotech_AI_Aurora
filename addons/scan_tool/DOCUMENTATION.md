# ELM327 Scan Tool System - Complete Documentation

A comprehensive OBD-II diagnostic system for Autotech AI that supports both real hardware 
connections and a built-in simulator for testing and training.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Simulator](#simulator)
5. [Real Hardware](#real-hardware)
6. [Gateway Server](#gateway-server)
7. [Open WebUI Integration](#open-webui-integration)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)

---

## System Overview

The ELM327 Scan Tool system enables AI-directed vehicle diagnostics through OBD-II. It consists of:

| Component | Purpose | Location |
|-----------|---------|----------|
| **Simulator** | Test without hardware | `simulator.py` |
| **Service** | Core OBD-II logic | `service.py` |
| **Gateway** | REST/WebSocket API | `gateway/server.py` |
| **Open WebUI Tool** | Chat integration | `openwebui_tool_standalone.py` |

### Key Capabilities

- ✅ Read Diagnostic Trouble Codes (DTCs)
- ✅ Clear DTCs (with safety prompts)
- ✅ Read live sensor data (PIDs)
- ✅ Monitor fuel trims for leak detection
- ✅ Read Vehicle Identification Number (VIN)
- ✅ Capture diagnostic snapshots
- ✅ Multiple connection types (WiFi, Bluetooth, USB)
- ✅ Simulate various vehicle fault conditions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Open WebUI                                  │
│                         (AI Chat Interface)                              │
│                                  │                                       │
│                    elm327_read_dtcs(), elm327_connect(), etc.           │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTP/REST
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Gateway Server                                  │
│                       (localhost:8327)                                   │
│                                                                          │
│   Endpoints: /connect, /dtcs, /pids, /fuel_trims, /monitor, etc.        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          ELM327 Service                                  │
│                        (service.py)                                      │
│                                                                          │
│   High-level API: read_all_dtcs(), read_pid(), read_fuel_trims()        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │      Simulator            │   │    Real Hardware          │
    │   (localhost:35000)       │   │   (192.168.x.x:35000)     │
    │                           │   │                           │
    │   - No hardware needed    │   │   - WiFi adapter          │
    │   - Configurable faults   │   │   - Bluetooth adapter     │
    │   - Training/testing      │   │   - USB adapter           │
    └───────────────────────────┘   └───────────────────────────┘
```

---

## Quick Start

### 1. Start the Simulator (for testing)

```bash
# Linux/Mac
./elm327_simulator.sh start

# Or directly
python -m addons.scan_tool.simulator --port 35000 --state lean_both_banks
```

### 2. Start the Gateway Server

```bash
python -m addons.scan_tool.gateway.server --port 8327
```

### 3. Test via cURL

```bash
# Check gateway status
curl http://localhost:8327/

# Connect to simulator
curl -X POST http://localhost:8327/connect \
  -H "Content-Type: application/json" \
  -d '{"connection_type": "wifi", "address": "localhost:35000"}'

# Read DTCs
curl http://localhost:8327/dtcs

# Read fuel trims
curl http://localhost:8327/fuel_trims

# Disconnect
curl -X POST http://localhost:8327/disconnect
```

### 4. Use in Open WebUI Chat

Once the tool is registered in Open WebUI:

```
User: "Connect to my scan tool and check for codes"

AI: [Connects and reads DTCs]
    Found 2 pending codes:
    • P0171: System Too Lean (Bank 1)
    • P0174: System Too Lean (Bank 2)
    
    Both banks lean indicates a common cause. Let me check fuel trims...
    
    [Reads fuel trims]
    STFT1: +2.3%, LTFT1: +12.5%
    STFT2: +17.2%, LTFT2: +9.4%
    
    High positive fuel trims confirm lean condition. Possible causes:
    1. Vacuum leak (most common)
    2. Dirty/faulty MAF sensor
    3. Low fuel pressure
```

---

## Simulator

The simulator emulates an ELM327 adapter for testing without real hardware.

### Starting the Simulator

**Linux/Mac (Service Script):**
```bash
# Start
./elm327_simulator.sh start

# Stop
./elm327_simulator.sh stop

# Check status
./elm327_simulator.sh status

# View logs
./elm327_simulator.sh logs

# Custom state
ELM327_SIM_STATE=overheating ./elm327_simulator.sh start
```

**Windows (PowerShell):**
```powershell
# Start
.\scripts\elm327_simulator.ps1 Start

# Start with specific fault
.\scripts\elm327_simulator.ps1 Start -State overheating

# Stop
.\scripts\elm327_simulator.ps1 Stop

# Status
.\scripts\elm327_simulator.ps1 Status
```

**Windows (CMD):**
```cmd
scripts\elm327_simulator.bat start
scripts\elm327_simulator.bat start overheating
scripts\elm327_simulator.bat stop
scripts\elm327_simulator.bat status
```

### Vehicle States

The simulator can emulate various fault conditions:

| State | Description | DTCs Generated | Fuel Trim Behavior |
|-------|-------------|----------------|-------------------|
| `normal` | Healthy vehicle | None | STFT/LTFT near 0% |
| `overheating` | Stuck thermostat | P0217 | Normal |
| `running_cold` | Thermostat open | P0128 | Slightly rich |
| `lean_both_banks` | Vacuum leak | P0171, P0174 | STFT/LTFT high positive |
| `lean_bank1` | Bank 1 lean | P0171 | Bank 1 high positive |
| `rich_both_banks` | Over-fueling | P0172, P0175 | STFT/LTFT negative |
| `misfire_cyl3` | Cylinder 3 misfire | P0303 | Slightly unstable |
| `random_misfire` | Multiple cylinders | P0300 | Unstable |
| `cat_degraded` | Catalytic converter | P0420 | O2 sensors cycling |
| `o2_sensor_lazy` | Slow O2 response | P0133 | Delayed trim response |
| `maf_dirty` | MAF contamination | P0101 | Incorrect load calc |

### Simulated PID Values

The simulator generates realistic, state-dependent values:

| PID | Normal Value | Affected States |
|-----|--------------|-----------------|
| RPM | 750 rpm (idle) | All |
| COOLANT_TEMP | 195°F | overheating→240°F, running_cold→140°F |
| STFT_B1 | 0-2% | lean→+15%, rich→-10% |
| LTFT_B1 | 1-3% | lean→+12%, rich→-8% |
| MAF | 4.5 g/s (idle) | maf_dirty→incorrect |
| O2_B1S1 | 0.1-0.9V cycling | o2_sensor_lazy→slow |

### Direct Simulator Testing

Connect directly with netcat:

```bash
nc localhost 35000
```

Then send ELM327 commands:
```
ATZ          # Reset - returns "ELM327 v2.1 (Simulated)"
ATE0         # Echo off
03           # Read DTCs (Mode $03)
010C         # Read RPM (PID $0C)
0105         # Read coolant temp (PID $05)
```

---

## Real Hardware

### Supported Connection Types

#### WiFi Adapters (Recommended)

Most reliable for development. Common adapters create a WiFi network.

```python
# Connection
await elm.connect('wifi', '192.168.0.10:35000')
```

**Setup:**
1. Connect phone/laptop to adapter's WiFi network (usually "WiFi_OBD")
2. Note the IP address (commonly 192.168.0.10)
3. Default port is usually 35000

#### Bluetooth Adapters

Good for mobile use, requires pairing first.

```python
# Linux (after pairing and binding to rfcomm)
await elm.connect('bluetooth', '/dev/rfcomm0')

# Or direct address (requires bleak)
await elm.connect('bluetooth', 'AA:BB:CC:DD:EE:FF')
```

**Linux Bluetooth Setup:**
```bash
# Pair the device
bluetoothctl
> scan on
> pair XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> quit

# Bind to serial port
sudo rfcomm bind 0 XX:XX:XX:XX:XX:XX

# Now connect to /dev/rfcomm0
```

#### USB Adapters

Direct connection, no wireless setup needed.

```python
# Linux
await elm.connect('usb', '/dev/ttyUSB0')

# Windows
await elm.connect('usb', 'COM3')
```

### Recommended Hardware

| Adapter | Type | Price | Notes |
|---------|------|-------|-------|
| OBDLink MX+ | BT/WiFi | $100 | Best reliability, fast |
| Veepeak OBDCheck | WiFi | $25 | Good budget option |
| BAFX Products | Bluetooth | $22 | Android compatible |
| Generic ELM327 | WiFi/BT | $10-15 | Hit or miss quality |

**Warning:** Very cheap adapters may have compatibility issues with certain vehicles or drop connections.

### iPhone/iOS Support

iOS apps can use:
1. **WiFi adapters** - Direct TCP connection
2. **Bonjour/mDNS discovery** - Automatic adapter finding (requires zeroconf)

```bash
# Install for auto-discovery
pip install zeroconf
```

---

## Gateway Server

The gateway provides a REST API layer between Open WebUI and the ELM327 service.

### Starting the Gateway

```bash
# Default (port 8327)
python -m addons.scan_tool.gateway.server

# Custom port
python -m addons.scan_tool.gateway.server --port 8000

# With verbose logging
python -m addons.scan_tool.gateway.server --verbose
```

### API Endpoints

#### Connection Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/connect` | Connect to adapter |
| POST | `/disconnect` | Disconnect |
| GET | `/` | Get status |

**Connect Request:**
```json
POST /connect
{
  "connection_type": "wifi",
  "address": "192.168.0.10:35000"
}
```

**Connect Response:**
```json
{
  "status": "connected",
  "vin": "1HGCM82633A004352",
  "supported_pids": 45,
  "address": "192.168.0.10:35000"
}
```

#### Diagnostic Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dtcs` | Read all DTCs |
| POST | `/clear-dtcs` | Clear DTCs |
| GET | `/vin` | Read VIN |
| GET | `/fuel_trims` | Read fuel trims |
| POST | `/pids` | Read specific PIDs |
| POST | `/monitor` | Monitor PIDs over time |

**Read DTCs Response:**
```json
{
  "stored": [
    {"code": "P0171", "description": "System Too Lean (Bank 1)", "severity": "moderate"},
    {"code": "P0174", "description": "System Too Lean (Bank 2)", "severity": "moderate"}
  ],
  "pending": [],
  "permanent": []
}
```

**Read PIDs Request:**
```json
POST /pids
{
  "pids": "RPM,COOLANT_TEMP,STFT1,LTFT1"
}
```

**Read PIDs Response:**
```json
{
  "pids": {
    "RPM": {"value": 750, "unit": "rpm"},
    "COOLANT_TEMP": {"value": 195, "unit": "°F"},
    "STFT1": {"value": 2.3, "unit": "%"},
    "LTFT1": {"value": 12.5, "unit": "%"}
  },
  "timestamp": "2026-01-30T17:45:00"
}
```

#### Monitoring

**Monitor PIDs Request:**
```json
POST /monitor
{
  "pids": "RPM,STFT1,STFT2",
  "duration": 30,
  "interval": 1.0
}
```

**Monitor Response:**
```json
{
  "samples": [...],
  "stats": {
    "RPM": {"min": 720, "max": 780, "avg": 752, "samples": 30},
    "STFT1": {"min": 1.2, "max": 4.5, "avg": 2.8, "samples": 30}
  },
  "duration": 30
}
```

---

## Open WebUI Integration

### Tool Registration

1. Go to **Workspace → Tools → + Add Tool**
2. Paste the contents of `openwebui_tool_standalone.py`
3. Click **Save**

### Configuration (Valves)

| Setting | Default | Description |
|---------|---------|-------------|
| `gateway_url` | `http://localhost:8327` | Gateway server URL |
| `elm327_address` | `localhost:35000` | Default adapter address |
| `connection_type` | `wifi` | Default connection type |

### Available Functions

| Function | Description |
|----------|-------------|
| `elm327_connect()` | Connect to adapter |
| `elm327_disconnect()` | Disconnect |
| `elm327_status()` | Check connection |
| `elm327_read_dtcs()` | Read trouble codes |
| `elm327_clear_dtcs()` | Clear codes (with warning) |
| `elm327_read_pids(pids)` | Read sensor data |
| `elm327_read_fuel_trims()` | Read fuel trim values |
| `elm327_read_vin()` | Read VIN |
| `elm327_monitor(pids, duration)` | Monitor over time |
| `scan_tool_help()` | Show help |

### Example Conversations

**Basic DTC Read:**
```
User: Check my car for codes

AI: I'll connect to your scan tool and read the diagnostic codes.

[Calls elm327_connect()]
✅ Connected to ELM327 via wifi
📋 VIN: 1HGCM82633A004352

[Calls elm327_read_dtcs()]
🔴 Stored DTCs (Check Engine Light):
  • P0171: System Too Lean (Bank 1)
  • P0174: System Too Lean (Bank 2)

Both banks showing lean indicates a common cause affecting the entire 
engine. Most likely causes:
1. Vacuum leak
2. Dirty/faulty MAF sensor  
3. Low fuel pressure

Would you like me to check the fuel trims to help narrow it down?
```

**Fuel Trim Analysis:**
```
User: Yes, check fuel trims

AI: [Calls elm327_read_fuel_trims()]
⛽ Fuel Trims:
  STFT1: +2.3% (✓ normal)
  LTFT1: +12.5% (⚠️ HIGH - adding fuel)
  STFT2: +17.2% (⚠️ HIGH - adding fuel)
  LTFT2: +9.4% (✓ normal)

💡 Both banks positive: Check for vacuum leak or MAF issue

The Long Term Fuel Trims being high means the ECU has learned to 
compensate for a lean condition. This points to:

1. **Vacuum Leak** - Most likely. The intake manifold gasket or 
   vacuum hoses are common failure points.
   
2. **MAF Sensor** - Can report incorrect airflow causing lean.

To test: I can monitor fuel trims while you spray brake cleaner 
around vacuum connections. If trims drop when you hit the leak, 
we've found it.
```

---

## API Reference

### Common PIDs

| Code | Name | Description | Unit | Range |
|------|------|-------------|------|-------|
| 0x04 | LOAD | Calculated engine load | % | 0-100 |
| 0x05 | COOLANT_TEMP | Engine coolant temperature | °C | -40 to 215 |
| 0x06 | STFT1 | Short term fuel trim bank 1 | % | -100 to 99.2 |
| 0x07 | LTFT1 | Long term fuel trim bank 1 | % | -100 to 99.2 |
| 0x08 | STFT2 | Short term fuel trim bank 2 | % | -100 to 99.2 |
| 0x09 | LTFT2 | Long term fuel trim bank 2 | % | -100 to 99.2 |
| 0x0B | MAP | Intake manifold pressure | kPa | 0-255 |
| 0x0C | RPM | Engine RPM | rpm | 0-16,383 |
| 0x0D | SPEED | Vehicle speed | km/h | 0-255 |
| 0x0E | TIMING_ADV | Timing advance | degrees | -64 to 63.5 |
| 0x0F | IAT | Intake air temperature | °C | -40 to 215 |
| 0x10 | MAF | Mass air flow rate | g/s | 0-655.35 |
| 0x11 | THROTTLE_POS | Throttle position | % | 0-100 |
| 0x42 | VOLTAGE | Control module voltage | V | 0-65.535 |

### DTC Format

DTCs follow SAE J2012 format:

```
P0171
│││││
││││└─ Specific fault (00-99)
│││└── Subsystem (0-9)
││└─── Category (0-3)
│└──── 0=SAE, 1=Manufacturer
└───── P=Powertrain, B=Body, C=Chassis, U=Network
```

### Fuel Trim Interpretation

| STFT + LTFT | Condition | Likely Causes |
|-------------|-----------|---------------|
| Both positive >10% | Lean | Vacuum leak, MAF, low fuel pressure |
| Both negative >10% | Rich | Leaking injector, high fuel pressure |
| Bank 1 only positive | Bank 1 lean | Bank 1 injector, O2 sensor |
| Fluctuating wildly | Unstable | Exhaust leak, bad O2 sensor |
| STFT high, LTFT normal | Recent change | New problem, adapting |
| STFT normal, LTFT high | Long-standing | Established compensation |

---

## Troubleshooting

### Simulator Issues

**Port already in use:**
```bash
# Find and kill existing process
./elm327_simulator.sh stop

# Or manually
pkill -f "addons.scan_tool.simulator"
```

**No response from simulator:**
```bash
# Check if running
./elm327_simulator.sh status

# Test with netcat
echo -e "ATZ\r" | nc -q1 localhost 35000
```

### Gateway Issues

**Cannot connect to gateway:**
```bash
# Check if running
curl http://localhost:8327/

# Start if not running
python -m addons.scan_tool.gateway.server --port 8327
```

**Gateway can't connect to simulator:**
- Ensure simulator is running first
- Check address in connect request matches simulator port

### Real Hardware Issues

**WiFi adapter not responding:**
1. Verify connected to adapter's WiFi network
2. Check IP address (usually 192.168.0.10)
3. Try default port 35000
4. Power cycle the adapter

**Bluetooth pairing issues (Linux):**
```bash
# Remove and re-pair
bluetoothctl
> remove XX:XX:XX:XX:XX:XX
> scan on
> pair XX:XX:XX:XX:XX:XX
```

**No data from vehicle:**
1. Ensure ignition is ON (not just ACC)
2. Some PIDs only work with engine running
3. Try reading supported PIDs first
4. Vehicle may not support all PIDs

### Open WebUI Tool Issues

**"Cannot connect to gateway" error:**
- Gateway must be running
- Check gateway URL in tool valves/settings
- Default is `http://localhost:8327`

**Import errors when adding tool:**
- Use `openwebui_tool_standalone.py` (HTTP-based)
- NOT `openwebui_tool.py` (uses relative imports)

---

## File Reference

```
addons/scan_tool/
├── __init__.py                    # Package exports
├── connection.py                  # Connection handlers (WiFi/BT/USB)
├── protocol.py                    # OBD-II protocol implementation
├── pids.py                        # PID definitions and decoders
├── service.py                     # High-level ELM327Service class
├── simulator.py                   # ELM327 simulator
├── openwebui_tool.py              # Original tool (relative imports)
├── openwebui_tool_standalone.py   # Standalone tool (HTTP-based) ← Use this
├── README.md                      # This documentation
├── gateway/
│   ├── __init__.py
│   └── server.py                  # FastAPI gateway server
└── scripts/
    ├── elm327_simulator.sh        # Linux service script
    ├── elm327_simulator.bat       # Windows batch script
    ├── elm327_simulator.ps1       # Windows PowerShell script
    ├── elm327-simulator.service   # Systemd service file
    └── README.md                  # Scripts documentation
```

---

## Safety Warnings

⚠️ **DO NOT use while driving** - Pull over safely before using diagnostics.

⚠️ **Clearing DTCs** - Only clear codes after repairs. The light will return if 
the problem isn't fixed, and you'll lose valuable diagnostic data.

⚠️ **Bidirectional control** - Actuator tests can cause physical effects (fans, 
solenoids). Ensure the vehicle is safe before commanding actuators.

⚠️ **Data accuracy** - Cheap adapters may give inaccurate readings. When in doubt, 
verify with professional equipment.
