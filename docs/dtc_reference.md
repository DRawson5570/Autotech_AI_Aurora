# OBD-II Diagnostic Trouble Code Reference

## Code Structure
```
P 0 1 7 1
│ │ │ └┴── Specific fault number
│ │ └───── Subsystem (0-9)
│ └─────── 0=Generic (SAE), 1-3=Manufacturer specific
└───────── P=Powertrain, B=Body, C=Chassis, U=Network
```

---

## POWERTRAIN CODES (P0xxx - P3xxx)

### Fuel & Air Metering (P0100-P0199)

| Code | Description |
|------|-------------|
| P0100 | Mass Air Flow (MAF) Circuit Malfunction |
| P0101 | MAF Sensor Range/Performance |
| P0102 | MAF Sensor Low Input |
| P0103 | MAF Sensor High Input |
| P0104 | MAF Circuit Intermittent |
| P0105 | Manifold Absolute Pressure (MAP) Circuit Malfunction |
| P0106 | MAP Sensor Range/Performance |
| P0107 | MAP Sensor Low Input |
| P0108 | MAP Sensor High Input |
| P0110 | Intake Air Temperature (IAT) Circuit Malfunction |
| P0111 | IAT Sensor Range/Performance |
| P0112 | IAT Sensor Low Input |
| P0113 | IAT Sensor High Input |
| P0115 | Engine Coolant Temperature (ECT) Circuit Malfunction |
| P0116 | ECT Sensor Range/Performance |
| P0117 | ECT Sensor Low Input |
| P0118 | ECT Sensor High Input |
| P0119 | ECT Circuit Intermittent |
| P0120 | Throttle Position Sensor (TPS) Circuit Malfunction |
| P0121 | TPS Range/Performance |
| P0122 | TPS Low Input |
| P0123 | TPS High Input |
| P0125 | Insufficient Coolant Temperature for Closed Loop |
| P0128 | Coolant Thermostat Below Regulating Temperature |
| P0130 | O2 Sensor Circuit Malfunction (Bank 1 Sensor 1) |
| P0131 | O2 Sensor Low Voltage (B1S1) |
| P0132 | O2 Sensor High Voltage (B1S1) |
| P0133 | O2 Sensor Slow Response (B1S1) |
| P0134 | O2 Sensor No Activity Detected (B1S1) |
| P0135 | O2 Sensor Heater Circuit Malfunction (B1S1) |
| P0136 | O2 Sensor Circuit Malfunction (B1S2) |
| P0137 | O2 Sensor Low Voltage (B1S2) |
| P0138 | O2 Sensor High Voltage (B1S2) |
| P0139 | O2 Sensor Slow Response (B1S2) |
| P0140 | O2 Sensor No Activity Detected (B1S2) |
| P0141 | O2 Sensor Heater Circuit Malfunction (B1S2) |
| P0150 | O2 Sensor Circuit Malfunction (B2S1) |
| P0151 | O2 Sensor Low Voltage (B2S1) |
| P0152 | O2 Sensor High Voltage (B2S1) |
| P0153 | O2 Sensor Slow Response (B2S1) |
| P0154 | O2 Sensor No Activity Detected (B2S1) |
| P0155 | O2 Sensor Heater Circuit Malfunction (B2S1) |
| P0156 | O2 Sensor Circuit Malfunction (B2S2) |
| P0157 | O2 Sensor Low Voltage (B2S2) |
| P0158 | O2 Sensor High Voltage (B2S2) |
| P0170 | Fuel Trim Malfunction (Bank 1) |
| P0171 | System Too Lean (Bank 1) |
| P0172 | System Too Rich (Bank 1) |
| P0173 | Fuel Trim Malfunction (Bank 2) |
| P0174 | System Too Lean (Bank 2) |
| P0175 | System Too Rich (Bank 2) |
| P0190 | Fuel Rail Pressure Sensor Circuit Malfunction |
| P0191 | Fuel Rail Pressure Sensor Range/Performance |
| P0192 | Fuel Rail Pressure Sensor Low Input |
| P0193 | Fuel Rail Pressure Sensor High Input |

### Fuel & Air Metering (P0200-P0299)

| Code | Description |
|------|-------------|
| P0201 | Injector Circuit Malfunction - Cylinder 1 |
| P0202 | Injector Circuit Malfunction - Cylinder 2 |
| P0203 | Injector Circuit Malfunction - Cylinder 3 |
| P0204 | Injector Circuit Malfunction - Cylinder 4 |
| P0205 | Injector Circuit Malfunction - Cylinder 5 |
| P0206 | Injector Circuit Malfunction - Cylinder 6 |
| P0207 | Injector Circuit Malfunction - Cylinder 7 |
| P0208 | Injector Circuit Malfunction - Cylinder 8 |
| P0217 | Engine Overtemperature Condition |
| P0220 | Throttle Position Sensor B Circuit Malfunction |
| P0221 | TPS B Range/Performance |
| P0222 | TPS B Low Input |
| P0223 | TPS B High Input |
| P0230 | Fuel Pump Primary Circuit Malfunction |
| P0231 | Fuel Pump Secondary Circuit Low |
| P0232 | Fuel Pump Secondary Circuit High |
| P0234 | Turbo/Supercharger Overboost Condition |
| P0261 | Cylinder 1 Injector Circuit Low |
| P0264 | Cylinder 2 Injector Circuit Low |
| P0267 | Cylinder 3 Injector Circuit Low |
| P0270 | Cylinder 4 Injector Circuit Low |
| P0299 | Turbo/Supercharger Underboost Condition |

### Ignition System (P0300-P0399)

| Code | Description |
|------|-------------|
| P0300 | Random/Multiple Cylinder Misfire Detected |
| P0301 | Cylinder 1 Misfire Detected |
| P0302 | Cylinder 2 Misfire Detected |
| P0303 | Cylinder 3 Misfire Detected |
| P0304 | Cylinder 4 Misfire Detected |
| P0305 | Cylinder 5 Misfire Detected |
| P0306 | Cylinder 6 Misfire Detected |
| P0307 | Cylinder 7 Misfire Detected |
| P0308 | Cylinder 8 Misfire Detected |
| P0325 | Knock Sensor 1 Circuit Malfunction |
| P0326 | Knock Sensor 1 Range/Performance |
| P0327 | Knock Sensor 1 Low Input |
| P0328 | Knock Sensor 1 High Input |
| P0330 | Knock Sensor 2 Circuit Malfunction |
| P0335 | Crankshaft Position Sensor A Circuit Malfunction |
| P0336 | Crankshaft Position Sensor A Range/Performance |
| P0337 | Crankshaft Position Sensor A Low Input |
| P0338 | Crankshaft Position Sensor A High Input |
| P0340 | Camshaft Position Sensor Circuit Malfunction (Bank 1) |
| P0341 | Camshaft Position Sensor Range/Performance |
| P0345 | Camshaft Position Sensor Circuit Malfunction (Bank 2) |
| P0351 | Ignition Coil A Primary/Secondary Circuit Malfunction |
| P0352 | Ignition Coil B Primary/Secondary Circuit Malfunction |
| P0353 | Ignition Coil C Primary/Secondary Circuit Malfunction |
| P0354 | Ignition Coil D Primary/Secondary Circuit Malfunction |
| P0355 | Ignition Coil E Primary/Secondary Circuit Malfunction |
| P0356 | Ignition Coil F Primary/Secondary Circuit Malfunction |
| P0357 | Ignition Coil G Primary/Secondary Circuit Malfunction |
| P0358 | Ignition Coil H Primary/Secondary Circuit Malfunction |

### Emissions Controls (P0400-P0499)

| Code | Description |
|------|-------------|
| P0400 | Exhaust Gas Recirculation (EGR) Flow Malfunction |
| P0401 | EGR Insufficient Flow Detected |
| P0402 | EGR Excessive Flow Detected |
| P0403 | EGR Circuit Malfunction |
| P0404 | EGR Range/Performance |
| P0405 | EGR Sensor A Low |
| P0406 | EGR Sensor A High |
| P0420 | Catalyst System Efficiency Below Threshold (Bank 1) |
| P0421 | Warm Up Catalyst Efficiency Below Threshold (Bank 1) |
| P0430 | Catalyst System Efficiency Below Threshold (Bank 2) |
| P0431 | Warm Up Catalyst Efficiency Below Threshold (Bank 2) |
| P0440 | Evaporative Emission (EVAP) System Malfunction |
| P0441 | EVAP System Incorrect Purge Flow |
| P0442 | EVAP System Small Leak Detected |
| P0443 | EVAP Purge Control Valve Circuit Malfunction |
| P0444 | EVAP Purge Control Valve Circuit Open |
| P0445 | EVAP Purge Control Valve Circuit Shorted |
| P0446 | EVAP Vent Control Circuit Malfunction |
| P0447 | EVAP Vent Control Circuit Open |
| P0448 | EVAP Vent Control Circuit Shorted |
| P0449 | EVAP Vent Valve/Solenoid Circuit Malfunction |
| P0450 | EVAP Pressure Sensor Malfunction |
| P0451 | EVAP Pressure Sensor Range/Performance |
| P0452 | EVAP Pressure Sensor Low Input |
| P0453 | EVAP Pressure Sensor High Input |
| P0455 | EVAP System Large Leak Detected |
| P0456 | EVAP System Very Small Leak Detected |
| P0457 | EVAP System Leak Detected (Fuel Cap Loose/Off) |
| P0480 | Cooling Fan 1 Control Circuit Malfunction |
| P0481 | Cooling Fan 2 Control Circuit Malfunction |

### Vehicle Speed & Idle Control (P0500-P0599)

| Code | Description |
|------|-------------|
| P0505 | Idle Air Control System Malfunction |
| P0506 | Idle Control System RPM Lower Than Expected |
| P0507 | Idle Control System RPM Higher Than Expected |
| P0508 | Idle Air Control Low |
| P0509 | Idle Air Control High |
| P0560 | System Voltage Malfunction |
| P0561 | System Voltage Unstable |
| P0562 | System Voltage Low |
| P0563 | System Voltage High |

### Transmission (P0700-P0899)

| Code | Description |
|------|-------------|
| P0700 | Transmission Control System Malfunction |
| P0705 | Transmission Range Sensor Circuit Malfunction |
| P0706 | Transmission Range Sensor Range/Performance |
| P0710 | Transmission Fluid Temperature Sensor Circuit Malfunction |
| P0711 | Trans Fluid Temp Sensor Range/Performance |
| P0715 | Input/Turbine Speed Sensor Circuit Malfunction |
| P0716 | Input Speed Sensor Range/Performance |
| P0717 | Input Speed Sensor No Signal |
| P0720 | Output Speed Sensor Circuit Malfunction |
| P0721 | Output Speed Sensor Range/Performance |
| P0722 | Output Speed Sensor No Signal |
| P0725 | Engine Speed Input Circuit Malfunction |
| P0730 | Incorrect Gear Ratio |
| P0731 | Gear 1 Incorrect Ratio |
| P0732 | Gear 2 Incorrect Ratio |
| P0733 | Gear 3 Incorrect Ratio |
| P0734 | Gear 4 Incorrect Ratio |
| P0735 | Gear 5 Incorrect Ratio |
| P0740 | Torque Converter Clutch Circuit Malfunction |
| P0741 | Torque Converter Clutch Stuck Off |
| P0742 | Torque Converter Clutch Stuck On |
| P0743 | Torque Converter Clutch Circuit Electrical |
| P0744 | Torque Converter Clutch Circuit Intermittent |
| P0750 | Shift Solenoid A Malfunction |
| P0751 | Shift Solenoid A Performance/Stuck Off |
| P0752 | Shift Solenoid A Stuck On |
| P0753 | Shift Solenoid A Electrical |
| P0755 | Shift Solenoid B Malfunction |
| P0756 | Shift Solenoid B Performance/Stuck Off |
| P0757 | Shift Solenoid B Stuck On |
| P0758 | Shift Solenoid B Electrical |
| P0760 | Shift Solenoid C Malfunction |
| P0765 | Shift Solenoid D Malfunction |
| P0770 | Shift Solenoid E Malfunction |
| P0780 | Shift Malfunction |
| P0781 | 1-2 Shift Malfunction |
| P0782 | 2-3 Shift Malfunction |
| P0783 | 3-4 Shift Malfunction |
| P0784 | 4-5 Shift Malfunction |

### Variable Valve Timing (P0010-P0025)

| Code | Description |
|------|-------------|
| P0010 | Intake Camshaft Position Actuator Circuit (Bank 1) |
| P0011 | Intake Camshaft Position Timing Over-Advanced (Bank 1) |
| P0012 | Intake Camshaft Position Timing Over-Retarded (Bank 1) |
| P0013 | Exhaust Camshaft Position Actuator Circuit (Bank 1) |
| P0014 | Exhaust Camshaft Position Timing Over-Advanced (Bank 1) |
| P0015 | Exhaust Camshaft Position Timing Over-Retarded (Bank 1) |
| P0020 | Intake Camshaft Position Actuator Circuit (Bank 2) |
| P0021 | Intake Camshaft Position Timing Over-Advanced (Bank 2) |
| P0022 | Intake Camshaft Position Timing Over-Retarded (Bank 2) |
| P0023 | Exhaust Camshaft Position Actuator Circuit (Bank 2) |
| P0024 | Exhaust Camshaft Position Timing Over-Advanced (Bank 2) |
| P0025 | Exhaust Camshaft Position Timing Over-Retarded (Bank 2) |

### Fuel System (P0080-P0099)

| Code | Description |
|------|-------------|
| P0087 | Fuel Rail/System Pressure Too Low |
| P0088 | Fuel Rail/System Pressure Too High |
| P0089 | Fuel Pressure Regulator Performance |
| P0093 | Fuel System Large Leak Detected |

### Additional P2xxx Codes

| Code | Description |
|------|-------------|
| P2135 | Throttle/Pedal Position Sensor A/B Voltage Correlation |
| P2138 | Throttle/Pedal Position Sensor D/E Voltage Correlation |

---

## CHASSIS CODES (C0xxx)

### ABS/Traction Control

| Code | Description |
|------|-------------|
| C0035 | Left Front Wheel Speed Sensor Circuit |
| C0040 | Right Front Wheel Speed Sensor Circuit |
| C0045 | Left Rear Wheel Speed Sensor Circuit |
| C0050 | Right Rear Wheel Speed Sensor Circuit |
| C0055 | Rear Wheel Speed Sensor Circuit |
| C0060 | Left Front ABS Solenoid Circuit |
| C0065 | Right Front ABS Solenoid Circuit |
| C0070 | Left Rear ABS Solenoid Circuit |
| C0075 | Right Rear ABS Solenoid Circuit |
| C0080 | ABS Solenoid Circuit Malfunction |
| C0110 | ABS Pump Motor Circuit |
| C0121 | Traction Control Valve Circuit |
| C0161 | ABS/TCS Brake Switch Circuit |
| C0265 | EBCM Relay Circuit |

### Steering

| Code | Description |
|------|-------------|
| C0455 | Steering Wheel Position Sensor |
| C0460 | Steering Position Sensor Range/Performance |
| C0545 | Electric Power Steering Motor Circuit |
| C0550 | Electronic Power Steering Control Module |

---

## NETWORK CODES (U0xxx)

| Code | Description |
|------|-------------|
| U0100 | Lost Communication With ECM/PCM |
| U0101 | Lost Communication With TCM |
| U0121 | Lost Communication With ABS Module |
| U0140 | Lost Communication With BCM |
| U0155 | Lost Communication With Instrument Cluster |
| U0401 | Invalid Data Received From ECM/PCM |
| U0402 | Invalid Data Received From TCM |

---

## Common Diagnostic Patterns

### Lean Codes (P0171/P0174)
Common causes: Vacuum leak, MAF contamination, weak fuel pump, clogged injectors, intake gasket leak

### Rich Codes (P0172/P0175)
Common causes: Leaking injectors, faulty O2 sensor, stuck-open purge valve, high fuel pressure

### Random Misfire (P0300)
Common causes: Vacuum leak, fuel delivery issue, ignition problem, low compression

### Catalyst Efficiency (P0420/P0430)
Common causes: Failing catalytic converter, exhaust leak before O2 sensor, contaminated fuel

### EVAP Leak (P0442/P0455/P0456)
Common causes: Loose gas cap, cracked EVAP hose, faulty purge valve, charcoal canister damage

### Transmission Solenoid Codes (P0750-P0770)
Common causes: Low/contaminated trans fluid, internal wiring, solenoid failure, valve body issue

---

*Note: P1xxx codes are manufacturer-specific and vary by make. Consult manufacturer documentation for P1xxx definitions.*
