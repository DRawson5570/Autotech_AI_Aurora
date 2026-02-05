# Scan Tool Integration

## Overview

Direct OBD2 integration via Bluetooth ELM327 adapters. Tech connects adapter, clicks "Diagnose", AI sees everything.

**The Vision:** No typing. No describing symptoms. AI sees raw vehicle data and diagnoses.

## User Flow

```
1. Tech pairs ELM327 Bluetooth adapter (one-time setup)
2. Tech opens Autotech AI on phone/tablet
3. Clicks "Connect to Vehicle"
4. App reads: DTCs, freeze frame, live PIDs
5. AI automatically analyzes and presents diagnosis
```

## Hardware Support

### Primary Target: ELM327 Bluetooth
- $15-30 on Amazon
- Works with 95% of 1996+ vehicles
- Protocols: CAN, ISO 9141, KWP2000, J1850

### Future: Professional Grade
- Bluetooth OBD2 Pro adapters
- J2534 passthru devices
- Direct CAN integration

## Data We Can Read

### Diagnostic Trouble Codes (DTCs)
- Current codes
- Pending codes
- Permanent codes
- Freeze frame data (conditions when code set)

### Live PIDs (Mode 01)
| PID | Description | Diagnostic Value |
|-----|-------------|------------------|
| 04 | Calculated Load | Engine demand |
| 05 | Coolant Temp | Thermostat, overheat |
| 06-09 | Fuel Trims (ST/LT Bank 1/2) | **KEY** - lean/rich diagnosis |
| 0B | Intake Manifold Pressure | Vacuum leaks, turbo |
| 0C | Engine RPM | Idle issues |
| 0D | Vehicle Speed | Speed sensor |
| 0E | Timing Advance | Knock, timing issues |
| 0F | Intake Air Temp | IAT sensor |
| 10 | MAF Air Flow | MAF sensor, air leaks |
| 11 | Throttle Position | TPS, throttle body |
| 13-1B | O2 Sensors | Fuel system, cat efficiency |
| 1F | Run Time | How long running |
| 2F | Fuel Level | Fuel sender |
| 31 | Distance Since Codes Cleared | Readiness |
| 42 | Control Module Voltage | Charging system |

### Readiness Monitors
- Catalyst
- Heated Catalyst
- Evaporative System
- Secondary Air
- A/C Refrigerant
- Oxygen Sensor
- Oxygen Sensor Heater
- EGR System

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Mobile App     │     │  Autotech AI     │     │  AI Diagnostic  │
│  (PWA/Native)   │     │  Server          │     │  Model          │
│                 │     │                  │     │                 │
│  ELM327 BT  ────┼────►│  /api/scan/      │────►│  Analyze PIDs   │
│  Adapter        │     │    diagnose      │     │  + DTCs         │
│                 │◄────┼──────────────────┼◄────│                 │
│  Show Results   │     │                  │     │  Return Diag    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Implementation Phases

### Phase 1: Web Serial API (Desktop Chrome)
- Use Web Serial API to connect to USB ELM327
- Proof of concept, internal testing
- No app store approval needed

### Phase 2: React Native App
- Bluetooth Classic support for ELM327
- iOS + Android
- Package with Autotech AI branding

### Phase 3: PWA with Web Bluetooth
- Progressive Web App
- Web Bluetooth API (limited device support)
- Works on Android Chrome, not iOS Safari

## API Design

### POST /api/scan/diagnose

Request:
```json
{
  "vehicle": {
    "year": 2018,
    "make": "Ford",
    "model": "F-150",
    "engine": "5.0L"
  },
  "dtcs": [
    {"code": "P0300", "status": "current"},
    {"code": "P0171", "status": "pending"}
  ],
  "freeze_frame": {
    "coolant_temp": 195,
    "engine_rpm": 750,
    "vehicle_speed": 0,
    "load": 32,
    "stft1": 12.5,
    "ltft1": 8.2
  },
  "live_pids": {
    "stft1": 14.8,
    "ltft1": 9.1,
    "stft2": 2.3,
    "ltft2": 1.1,
    "maf": 4.2,
    "map": 12.5,
    "coolant_temp": 198,
    "intake_temp": 85,
    "rpm": 780,
    "load": 28,
    "throttle": 15.2,
    "timing": 12,
    "o2_b1s1": 0.45,
    "o2_b1s2": 0.72
  },
  "monitors": {
    "catalyst": "complete",
    "evap": "incomplete",
    "o2_sensor": "complete",
    "egr": "not_supported"
  }
}
```

Response:
```json
{
  "diagnosis": {
    "summary": "Bank 1 vacuum leak indicated",
    "confidence": "high",
    "reasoning": "STFT1 +14.8%, LTFT1 +9.1% (total +24%) while Bank 2 trims normal. P0300 random misfire + P0171 lean Bank 1 confirms unmetered air entering Bank 1 intake.",
    "likely_causes": [
      {"cause": "Intake manifold gasket - Bank 1 side", "probability": "high"},
      {"cause": "Cracked vacuum line - Bank 1", "probability": "medium"},
      {"cause": "PCV valve/hose", "probability": "medium"}
    ],
    "recommended_tests": [
      "Smoke test intake manifold",
      "Propane enrichment test Bank 1 runners",
      "Inspect PCV valve and hoses"
    ],
    "safety_notes": [
      "Running lean can cause catalyst damage if driven extensively"
    ]
  }
}
```

## Competitive Advantage

1. **Friction Removal** - No typing PIDs, no describing symptoms
2. **Accuracy** - AI sees actual data, not tech's interpretation
3. **Speed** - Diagnosis in seconds after connection
4. **Learning** - We collect anonymized data on successful diagnoses
5. **Lock-in** - Once they're used to this workflow, hard to go back

## Risks

1. **Bluetooth pairing pain** - ELM327 pairing can be finicky
2. **Vehicle coverage** - Some vehicles don't report all PIDs
3. **App store approval** - Automotive diagnostic claims may get scrutiny
4. **Adapter quality** - Cheap ELM327 clones can be unreliable

## Cost

- ELM327 adapter: $15-30 (user provides)
- App development: ~40-80 hours for MVP
- Ongoing: Minimal - it's a thin client

## Success Metrics

- Connection success rate > 90%
- Time from connect to diagnosis < 30 seconds
- User retention (users with scan tool vs without)
- "That fixed it" confirmation rate
