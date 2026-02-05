# Predictive Diagnostics System Spec

## Vision
Transform reactive "what broke?" diagnostics into proactive "what's about to break?" predictions by mining known failure patterns from Mitchell TSBs and generating physics-informed synthetic training scenarios.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐           │
│  │  Mitchell TSBs  │   │ Wiring Diagrams │   │   DTC Index     │           │
│  │  (per vehicle)  │   │  (topology)     │   │  (symptom→code) │           │
│  └────────┬────────┘   └────────┬────────┘   └────────┬────────┘           │
│           │                     │                     │                     │
│           └─────────────────────┼─────────────────────┘                     │
│                                 ▼                                           │
│                    ┌────────────────────────┐                               │
│                    │  Failure Mode Extractor │                              │
│                    │  (LLM + structured     │                               │
│                    │   extraction)          │                               │
│                    └────────────┬───────────┘                               │
│                                 │                                           │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FAILURE MODE KNOWLEDGE BASE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  {                                                                          │
│    "failure_id": "TSB-20-NA-123",                                           │
│    "vehicle": {"year_range": [2019, 2022], "make": "Chevrolet",             │
│                "model": "Bolt EV", "systems": ["propulsion"]},              │
│    "root_cause": "Battery coolant pump motor failure",                      │
│    "component_chain": ["coolant_pump", "inverter", "battery_pack"],         │
│    "symptoms": ["reduced_propulsion_power", "thermal_derate"],              │
│    "dtc_codes": ["P0A9A", "P0A08"],                                         │
│    "signal_signatures": {                                                   │
│      "coolant_temp": {"trend": "rising", "threshold": 75},                  │
│      "pump_motor_current": {"trend": "dropping", "threshold": 0.5},         │
│      "inverter_status": {"contains": "THERMAL_DERATE"}                      │
│    },                                                                       │
│    "precursor_window_minutes": 15,                                          │
│    "diagnostic_tests": ["pump_current_draw", "coolant_flow_rate"],          │
│    "repair_action": "Replace coolant pump assembly",                        │
│    "source_tsb": "TSB 20-NA-123 (Dec 2020)"                                 │
│  }                                                                          │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYNTHETIC SCENARIO GENERATOR                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  For each failure mode in knowledge base:                                   │
│                                                                             │
│  1. Load vehicle-specific baseline parameters                               │
│     - Motor specs (torque constant, rated current)                          │
│     - Thermal limits (from Mitchell specs)                                  │
│     - Normal operating ranges                                               │
│                                                                             │
│  2. Generate baseline time-series (healthy vehicle)                         │
│     - Drive cycle: urban, highway, aggressive                               │
│     - Duration: 10-60 minutes                                               │
│     - Sample rate: 1-10 Hz                                                  │
│                                                                             │
│  3. Inject failure signature at random onset time                           │
│     - Progressive degradation (pump wearing out)                            │
│     - Sudden failure (FET short)                                            │
│     - Intermittent (CAN glitches)                                           │
│                                                                             │
│  4. Add realistic noise and sensor dropouts                                 │
│                                                                             │
│  5. Label with ground truth + precursor markers                             │
│     - "At t=180s, pump current began dropping"                              │
│     - "At t=240s, thermal derate triggered"                                 │
│                                                                             │
│  Output: scenario.json + timeseries.csv + labels.json                       │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MODEL TRAINING PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Training Objectives:                                                       │
│                                                                             │
│  1. CLASSIFICATION: Given signals, predict failure mode (multi-label)       │
│     - Input: last N minutes of telemetry                                    │
│     - Output: P(failure_mode_i) for each known failure mode                 │
│                                                                             │
│  2. PRECURSOR DETECTION: Predict time-to-failure                            │
│     - "Pump failure likely within 10-20 minutes"                            │
│     - Enables proactive alerts before breakdown                             │
│                                                                             │
│  3. DIAGNOSTIC REASONING (LLM fine-tune or RAG):                            │
│     - Given symptoms + vehicle + TSB context                                │
│     - Generate diagnostic plan with confidence                              │
│                                                                             │
│  Model Options:                                                             │
│  - Lightweight: XGBoost/Random Forest on engineered features                │
│  - Medium: 1D CNN or LSTM on raw signals                                    │
│  - Heavy: Fine-tuned LLM with time-series embedding                         │
│                                                                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INFERENCE / DEPLOYMENT                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Shop Scenario:                                                             │
│                                                                             │
│  1. Tech connects OBD-II scanner to 2020 Chevy Bolt                         │
│  2. System identifies vehicle → loads relevant failure modes                │
│  3. Streams live CAN data (coolant_temp, voltages, currents)                │
│  4. Model scores against known failure signatures                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  🚨 ALERT: High probability of coolant pump failure (78%)       │        │
│  │                                                                 │        │
│  │  Evidence:                                                      │        │
│  │  • Coolant temp rising (62°C → 71°C in 5 min)                   │        │
│  │  • Pump motor current low (0.3A vs expected 2.0A)               │        │
│  │  • Matches TSB 20-NA-123 pattern                                │        │
│  │                                                                 │        │
│  │  Recommended:                                                   │        │
│  │  1. Verify pump operation (listen/flow test)                    │        │
│  │  2. Check connector at pump motor                               │        │
│  │  3. If confirmed, replace pump (Part# 12345678)                 │        │
│  │                                                                 │        │
│  │  ⏱️ Estimated time to thermal derate: 8-12 minutes              │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 0: Systematic Fault Tree Generation (First Principles)

### The Core Insight

A master technician doesn't need a TSB to diagnose a new failure. They understand:
1. How components work
2. How components fail
3. How failures propagate through connected systems

We encode this knowledge systematically so the AI can reason about ANY failure mode — even ones that have never been documented.

### Component Failure Taxonomy

Every electrical/mechanical component has predictable failure modes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UNIVERSAL COMPONENT FAILURE MODES                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ELECTRICAL COMPONENTS                                                      │
│  ─────────────────────                                                      │
│  Wire/Harness:     open, short_to_ground, short_to_power, high_resistance,  │
│                    chafe, corrosion, thermal_damage, vibration_fatigue      │
│                                                                             │
│  Connector:        backed_out_pin, corroded_terminals, water_intrusion,     │
│                    heat_damage, wrong_terminal_tension, contamination       │
│                                                                             │
│  Relay:            coil_open, coil_shorted, contacts_welded_closed,         │
│                    contacts_pitted, intermittent, slow_response             │
│                                                                             │
│  Fuse:             blown, high_resistance, wrong_rating_installed           │
│                                                                             │
│  Sensor:           drift, stuck_high, stuck_low, noisy_output, dead,        │
│                    slow_response, contaminated, miscalibrated               │
│                                                                             │
│  Actuator/Motor:   open_winding, shorted_winding, seized_mechanical,        │
│                    weak_output, brushes_worn, bearing_failure               │
│                                                                             │
│  ECU/Module:       power_supply_fault, ground_fault, internal_short,        │
│                    software_glitch, memory_corruption, output_driver_dead   │
│                                                                             │
│  MECHANICAL COMPONENTS                                                      │
│  ─────────────────────                                                      │
│  Pump:             impeller_damage, seal_leak, cavitation, motor_failure,   │
│                    clogged_inlet, air_lock                                  │
│                                                                             │
│  Valve:            stuck_open, stuck_closed, leaking, slow_response,        │
│                    contamination, spring_fatigue                            │
│                                                                             │
│  Bearing:          wear, contamination, lack_of_lubrication, overload,      │
│                    misalignment, fatigue_spalling                           │
│                                                                             │
│  Seal/Gasket:      leak, hardening, extrusion, improper_seating             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fault Tree Generation Algorithm

```
INPUT:  System wiring diagram + component list
OUTPUT: Complete fault tree with signal signatures

FOR each component C in system:
    FOR each failure_mode F in FAILURE_TAXONOMY[C.type]:
        
        1. DETERMINE immediate effects:
           - What signals change at C's terminals?
           - Does C stop functioning? Partially function? Malfunction?
        
        2. TRACE propagation paths:
           - What downstream components depend on C?
           - What upstream components feed C?
           - Walk the circuit graph for cascading effects
        
        3. GENERATE signal signatures:
           - Primary: direct measurement at C (if accessible)
           - Secondary: downstream symptoms (derates, faults, DTCs)
           - Tertiary: customer-observable (noise, smell, behavior)
        
        4. IDENTIFY diagnostic approach:
           - What test confirms this failure?
           - What test rules it out?
           - Minimum measurements needed for 90% confidence
        
        5. STORE in fault tree:
           {
             component: C,
             failure_mode: F,
             probability_prior: estimate from component type/age,
             signal_signatures: [...],
             cascading_effects: [...],
             diagnostic_tests: [...],
             repair_action: standard repair for this failure type
           }
```

### Example: Cooling System Fault Tree (Auto-Generated)

```
System: EV Battery Cooling Circuit
Components: [Pump, Relay, Fuse, Temp_Sensor, ECU_Output, Coolant_Lines]

Generated Fault Tree:
─────────────────────

PUMP_001: pump.motor_open_winding
├── Immediate: pump_current = 0A, pump_flow = 0
├── Propagation: coolant_temp rises → inverter_temp rises → thermal_derate
├── Signatures:
│   ├── pump_motor_current: drops to 0 (was ~2A)
│   ├── coolant_temp: rising trend (+3°C/min under load)
│   └── inverter_status: THERMAL_DERATE after ~15min
├── Diagnostic: measure pump current, verify 12V at pump connector
└── Repair: replace pump assembly

PUMP_002: pump.seized_mechanical
├── Immediate: pump_current = HIGH (stall current ~8A), pump_flow = 0
├── Propagation: same as PUMP_001, but may blow fuse F15
├── Signatures:
│   ├── pump_motor_current: spike then drop (if fuse blows)
│   ├── fuse_F15_status: may be open
│   └── coolant_temp: rising
├── Diagnostic: check fuse F15, listen for pump noise, measure stall current
└── Repair: replace pump assembly

RELAY_001: relay_R12.coil_open
├── Immediate: pump never activates, pump_current = 0
├── Propagation: same thermal cascade as pump failure
├── Signatures:
│   ├── pump_motor_current: always 0 (pump never commanded)
│   ├── relay_R12_coil_voltage: 12V present but no click
│   └── coolant_temp: rising
├── Diagnostic: apply 12V directly to pump (bypassing relay) - if pump runs, relay bad
└── Repair: replace relay R12

RELAY_002: relay_R12.contacts_welded_closed  
├── Immediate: pump runs continuously, even with key off
├── Propagation: 
│   ├── battery drain (parasitic draw)
│   ├── overcooling in cold weather
│   └── pump motor premature wear
├── Signatures:
│   ├── pump_motor_current: always ~2A (even key off)
│   ├── coolant_temp: may be LOW in winter
│   └── battery_voltage: drops overnight (parasitic)
├── Diagnostic: pull relay - pump should stop. If pump still runs, wiring issue.
└── Repair: replace relay R12

SENSOR_001: temp_sensor.stuck_low
├── Immediate: ECU reads coolant_temp = low (e.g., 20°C constant)
├── Propagation: 
│   ├── ECU may not command pump (thinks coolant is cold)
│   ├── actual coolant_temp rises uncontrolled
│   └── thermal derate with "normal" indicated temp
├── Signatures:
│   ├── coolant_temp_indicated: stuck at one value
│   ├── coolant_temp_actual: rising (compare to IR thermometer)
│   ├── inverter_status: THERMAL_DERATE despite "normal" coolant reading
│   └── DTC: likely P0117 or similar (temp sensor low)
├── Diagnostic: compare indicated vs actual with IR gun
└── Repair: replace coolant temp sensor

CONNECTOR_001: pump_connector.corroded_terminals
├── Immediate: high resistance in pump circuit
├── Propagation:
│   ├── pump runs slow (reduced voltage)
│   ├── intermittent pump operation
│   └── gradual thermal issues
├── Signatures:
│   ├── pump_motor_current: lower than normal (1.2A vs 2A)
│   ├── pump_connector_voltage: lower than battery (9V vs 12V)
│   └── symptoms may be intermittent / weather-dependent
├── Diagnostic: voltage drop test across connector (should be <0.5V)
└── Repair: clean or replace connector terminals

... [continues for every component × every failure mode]
```

### Cascading Effect Analysis

The real power is understanding how failures cascade:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     CASCADE PROPAGATION MATRIX                             │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Root Failure          │ 1st Order Effect    │ 2nd Order Effect           │
│  ─────────────────────────────────────────────────────────────────────────│
│  Pump fails            │ No coolant flow     │ Battery overheats          │
│                        │                     │ Inverter derates           │
│                        │                     │ Reduced propulsion         │
│  ─────────────────────────────────────────────────────────────────────────│
│  Temp sensor stuck low │ ECU thinks cool     │ Pump may not run           │
│                        │                     │ Actual temp rises          │
│                        │                     │ Thermal damage possible    │
│  ─────────────────────────────────────────────────────────────────────────│
│  ECU output shorted    │ Pump relay stuck    │ Same as relay welded       │
│                        │                     │ Plus: ECU may set DTC      │
│  ─────────────────────────────────────────────────────────────────────────│
│  HV interlock open     │ HV system disables  │ No propulsion              │
│                        │                     │ May strand vehicle         │
│                        │                     │ Tow mode only              │
│  ─────────────────────────────────────────────────────────────────────────│
│                                                                            │
│  Key Insight: Same SYMPTOM can have multiple ROOT CAUSES                   │
│  "Reduced power" ← pump fail OR sensor fail OR relay fail OR ...           │
│  The fault tree enumerates ALL paths to each symptom                       │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Differential Diagnosis from First Principles

When the AI sees symptoms, it doesn't just pattern-match — it reasons:

```
SYMPTOM: Inverter thermal derate, coolant_temp rising

AI REASONING:
┌─────────────────────────────────────────────────────────────────┐
│ Which fault tree nodes produce these symptoms?                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ✓ PUMP_001 (motor open)      → pump_current = 0A               │
│ ✓ PUMP_002 (seized)          → pump_current = high then 0      │
│ ✓ RELAY_001 (coil open)      → pump never commanded            │
│ ✓ FUSE_001 (blown)           → no power to pump circuit        │
│ ✓ CONNECTOR_001 (corroded)   → pump runs weak                  │
│ ✗ SENSOR_001 (stuck low)     → wouldn't see high temp reading  │
│ ✓ SENSOR_002 (stuck high)    → false alarm? Check actual temp  │
│ ✗ RELAY_002 (welded closed)  → pump would run, no overheating  │
│                                                                 │
│ DISCRIMINATING TEST: Measure pump_motor_current                 │
│ • If 0A → pump not running → check relay, fuse, wiring         │
│ • If ~2A → pump running → low flow? Check for blockage         │
│ • If 1A → pump weak → check connector voltage drop             │
│                                                                 │
│ NEXT: Request pump_motor_current measurement                    │
└─────────────────────────────────────────────────────────────────┘
```

### Wiring Diagram → Component Graph Extraction

To generate fault trees automatically, we need to parse wiring diagrams:

```python
class ComponentGraph:
    """Graph representation of vehicle electrical system"""
    
    def __init__(self):
        self.components = {}  # id → Component
        self.connections = []  # list of (comp_a, pin_a, comp_b, pin_b, wire_id)
    
    @classmethod
    def from_wiring_diagram(cls, diagram_data):
        """
        Parse Mitchell wiring diagram into component graph.
        
        Input: Structured wiring data (extracted from SVG/PDF)
        Output: ComponentGraph with all nodes and edges
        """
        graph = cls()
        
        # Extract components (pumps, relays, sensors, ECUs, connectors)
        for comp in diagram_data['components']:
            graph.add_component(
                id=comp['id'],
                type=comp['type'],  # pump, relay, sensor, ecu, connector, fuse
                location=comp['location'],
                specs=comp.get('specs', {})
            )
        
        # Extract connections (wires between pins)
        for wire in diagram_data['wires']:
            graph.add_connection(
                comp_a=wire['from_component'],
                pin_a=wire['from_pin'],
                comp_b=wire['to_component'],
                pin_b=wire['to_pin'],
                wire_id=wire['id'],
                wire_gauge=wire.get('gauge'),
                wire_color=wire.get('color')
            )
        
        return graph
    
    def trace_power_path(self, from_comp, to_comp):
        """Trace power flow from source to load"""
        # BFS/DFS to find path through graph
        pass
    
    def find_upstream(self, component_id):
        """Find all components that feed this one"""
        pass
    
    def find_downstream(self, component_id):
        """Find all components that depend on this one"""
        pass
    
    def generate_fault_tree(self):
        """Generate complete fault tree for this system"""
        fault_tree = []
        
        for comp_id, comp in self.components.items():
            failure_modes = FAILURE_TAXONOMY[comp.type]
            
            for failure_mode in failure_modes:
                fault = self.analyze_failure(comp, failure_mode)
                fault_tree.append(fault)
        
        return fault_tree
```

### Training Data: Synthetic Scenarios for EVERY Fault

The fault tree becomes our scenario generator:

```python
def generate_all_fault_scenarios(fault_tree, vehicle_params):
    """
    For each fault in the tree, generate synthetic telemetry scenario.
    
    This gives us training data for failure modes that may NEVER
    have been observed in the wild yet.
    """
    scenarios = []
    
    for fault in fault_tree:
        # Generate baseline healthy scenario
        baseline = generate_baseline_telemetry(vehicle_params)
        
        # Inject this specific fault's signature
        faulty = inject_fault_signature(
            baseline, 
            fault.signal_signatures,
            onset_time=random_onset(),
            severity=random_severity()
        )
        
        # Create labeled scenario
        scenario = {
            'id': f"{vehicle_params['id']}_{fault.component}_{fault.failure_mode}",
            'telemetry': faulty,
            'labels': {
                'root_cause': fault.failure_mode,
                'component': fault.component,
                'cascading_effects': fault.cascading_effects,
                'diagnostic_tests': fault.diagnostic_tests
            },
            'source': 'first_principles_generation'  # Not from TSB!
        }
        scenarios.append(scenario)
    
    return scenarios
```

### The Ultimate Capability

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   NEW 2027 MODEL YEAR VEHICLE RELEASED                                      │
│   └─► Zero TSBs (brand new)                                                 │
│   └─► Zero field failures (just launched)                                   │
│                                                                             │
│   AUTOTECH AI CAPABILITY:                                                   │
│   1. Ingest wiring diagram for cooling system                               │
│   2. Auto-generate component graph                                          │
│   3. Apply failure taxonomy → complete fault tree                           │
│   4. Generate synthetic training scenarios                                  │
│   5. AI is IMMEDIATELY ready to diagnose ANY failure                        │
│                                                                             │
│   Day 1 diagnostic capability. No waiting for TSBs.                         │
│   No waiting for "nature to take its course."                               │
│                                                                             │
│   THE AI ALREADY KNOWS EVERY WAY THIS SYSTEM CAN FAIL.                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: TSB Failure Mode Extraction

### Input
Raw TSB text from Mitchell, e.g.:
```
TECHNICAL SERVICE BULLETIN 20-NA-123

SUBJECT: Reduced Propulsion Power Message Displayed

MODELS: 2019-2022 Chevrolet Bolt EV

CONDITION: Customer may report reduced propulsion power or 
"Propulsion Power is Reduced" message. DTCs P0A9A (Hybrid/EV 
Battery Pack Coolant Pump Motor Performance) or P0A08 may be stored.

CAUSE: Battery coolant pump motor may fail, causing inadequate 
cooling of the high-voltage battery pack and power electronics.

CORRECTION: Replace the battery coolant pump assembly.
```

### Extraction Prompt (for LLM)
```
Extract structured failure mode data from this TSB:

{tsb_text}

Return JSON:
{
  "failure_id": "TSB-{number}",
  "vehicle_years": [start, end],
  "vehicle_make": "string",
  "vehicle_model": "string",
  "root_cause": "concise technical description",
  "affected_components": ["list", "of", "components"],
  "symptoms_customer_reported": ["list"],
  "symptoms_technical": ["list"],
  "dtc_codes": ["P0xxx", ...],
  "signal_signatures": {
    "signal_name": {"pattern": "rising|falling|spike|intermittent", "notes": "..."}
  },
  "repair_action": "string",
  "parts_mentioned": ["part numbers if any"]
}
```

### Output: Failure Mode Database
SQLite or JSON collection indexed by:
- Vehicle (year/make/model)
- Component
- DTC code
- Symptom keywords

---

## Phase 2: Signal Signature Library

Map failure modes to observable signal patterns:

| Failure Mode | Primary Signal | Pattern | Secondary Signals |
|--------------|----------------|---------|-------------------|
| Coolant pump failure | pump_motor_current | drops to <0.5A | coolant_temp rises, inverter derates |
| Phase FET short | phase_current (Ia/Ib/Ic) | spike >5x baseline | Vdc drops, overcurrent fault |
| BMS cell imbalance | cell_voltage_n | one cell drops faster | pack Vdc sags under load |
| Inverter IGBT degradation | gate_drive_voltage | reduced swing | switching losses increase, efficiency drops |
| HV contactor welding | contactor_state | stuck closed | precharge fails, inrush current |
| Motor bearing wear | vibration_accel | increasing amplitude | audible noise, current ripple |

### Signal Injection Functions

```python
def inject_pump_failure(df, onset_idx, severity=1.0):
    """Progressive pump degradation → failure"""
    # Pump current drops exponentially
    df.loc[onset_idx:, 'pump_motor_current'] *= np.exp(-0.01 * severity * np.arange(len(df) - onset_idx))
    # Coolant temp rises as a consequence
    for i in range(onset_idx, len(df)):
        dt = i - onset_idx
        df.loc[i, 'coolant_temp'] += 0.05 * severity * dt  # ~3°C/min rise
    # Inverter derates when coolant_temp > threshold
    derate_idx = df[df['coolant_temp'] > 75].index.min()
    if pd.notna(derate_idx):
        df.loc[derate_idx:, 'inverter_status'] = 'THERMAL_DERATE'
        df.loc[derate_idx:, 'measured_torque'] *= 0.6
    return df
```

---

## Phase 3: Vehicle-Specific Parameters

Pull from Mitchell or spec sheets:

```python
VEHICLE_PARAMS = {
    "2020_Chevrolet_Bolt_EV": {
        "motor": {
            "type": "permanent_magnet_AC",
            "peak_power_kw": 150,
            "peak_torque_nm": 360,
            "base_speed_rpm": 3500,
        },
        "battery": {
            "capacity_kwh": 66,
            "voltage_nominal": 350,
            "cells_series": 96,
            "cooling": "liquid",
        },
        "thermal": {
            "coolant_temp_nominal_c": 25,
            "coolant_temp_warn_c": 65,
            "coolant_temp_derate_c": 75,
            "coolant_temp_shutdown_c": 85,
        },
        "signals_available": [
            "coolant_temp", "pump_motor_current", "Vdc", 
            "Ia", "Ib", "Ic", "motor_rpm", "motor_torque",
            "cell_voltage_1..96", "BMS_status", "inverter_status"
        ]
    }
}
```

---

## Phase 4: Training Data Generation

### Scenario Mix
For each vehicle with known TSBs:
- 30% healthy baseline (no faults)
- 50% single fault scenarios (one TSB failure mode)
- 20% multi-fault or cascading failures

### Labeling
Each scenario includes:
```json
{
  "scenario_id": "BOLT_2020_PUMP_001",
  "vehicle": "2020_Chevrolet_Bolt_EV",
  "labels": {
    "failure_modes": ["coolant_pump_failure"],
    "onset_timestamp": "2026-01-25T10:15:30Z",
    "precursor_start_timestamp": "2026-01-25T10:10:00Z",
    "severity": "progressive",
    "related_tsbs": ["TSB-20-NA-123"]
  },
  "ground_truth_diagnosis": {
    "root_cause": "Battery coolant pump motor failure",
    "confidence": 0.95,
    "diagnostic_steps": ["Measure pump current", "Check coolant flow"],
    "repair": "Replace coolant pump assembly"
  }
}
```

---

## Phase 5: Integration with Autotech AI

### New Tool: `predict_failure_mode`

```python
async def predict_failure_mode(
    vehicle: VehicleInfo,
    telemetry: dict,  # Recent signal readings
    dtcs: list[str] = None,
    customer_complaint: str = None
) -> ToolResult:
    """
    Given vehicle info and live/recent telemetry, predict likely failure modes.
    
    Returns:
    - Top failure mode predictions with confidence
    - Matching TSBs
    - Recommended diagnostic steps
    - Precursor warnings if applicable
    """
```

### User Flow
```
User: "2020 Chevy Bolt, customer says reduced power, coolant temp is at 72°C"

Autotech AI:
┌─────────────────────────────────────────────────────────────────┐
│ 🔍 Failure Mode Analysis                                        │
│                                                                 │
│ HIGH PROBABILITY: Coolant Pump Failure (82%)                    │
│ └─ Matches TSB 20-NA-123 pattern                                │
│ └─ Elevated coolant temp (72°C) approaching derate threshold    │
│ └─ Customer symptom "reduced power" consistent                  │
│                                                                 │
│ DIAGNOSTIC STEPS:                                               │
│ 1. Check pump motor current (expect ~2A, failure <0.5A)         │
│ 2. Verify coolant flow at reservoir                             │
│ 3. Scan for DTCs P0A9A, P0A08                                   │
│                                                                 │
│ ⚠️ WARNING: If pump has failed, thermal derate imminent         │
│    Recommend: Do not drive until verified                       │
│                                                                 │
│ Related TSBs:                                                   │
│ • TSB 20-NA-123: Reduced Propulsion Power (Dec 2020)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Pipeline Summary

```
Mitchell TSBs ──┬──► LLM Extraction ──► Failure Mode DB
                │                              │
Wiring Diagrams ┴──► Topology Graph            │
                                               ▼
                              Scenario Generator (physics-based)
                                               │
                                               ▼
                              Synthetic Dataset (CSV + labels)
                                               │
                              ┌────────────────┴────────────────┐
                              ▼                                 ▼
                    Classical ML Model              LLM Fine-tune/RAG
                    (XGBoost on features)          (reasoning + context)
                              │                                 │
                              └────────────────┬────────────────┘
                                               ▼
                                    Autotech AI Inference
                                    (live shop telemetry)
```

---

## Success Metrics

1. **Extraction Accuracy**: % of TSBs correctly parsed into structured failure modes
2. **Scenario Fidelity**: Subject matter expert review of generated scenarios
3. **Prediction Accuracy**: 
   - Top-1 accuracy on held-out synthetic scenarios
   - Top-3 accuracy (diagnostic relevance)
4. **Precursor Detection**: Time-to-failure prediction error (minutes)
5. **Real-World Validation**: Correlation with actual shop diagnoses (when data available)

---

## Next Steps

1. **TSB Scraper**: Pull all TSBs for a target vehicle (e.g., Chevy Bolt EV)
2. **Extraction Pipeline**: LLM-based structured extraction with validation
3. **Signal Library**: Map extracted failure modes to injectable patterns
4. **Generator V2**: Extend `generate_scenarios.py` to use failure mode DB
5. **Baseline Model**: Train XGBoost on engineered features
6. **Autotech Integration**: New tool + RAG augmentation with TSB context

---

## Appendix: Sample TSB Categories to Target

**High-Value EV/Hybrid Failure Modes:**
- Battery thermal management (pumps, fans, coolant)
- Inverter/motor controller faults
- High-voltage contactor issues
- BMS cell balancing problems
- Charging system faults
- Regenerative braking anomalies

**High-Value ICE Failure Modes:**
- Fuel system (injectors, pumps, pressure)
- Ignition system (coils, timing)
- Emissions (catalytic converter, EGR, O2 sensors)
- Transmission (solenoids, clutch packs, torque converter)
- Cooling system (thermostat, water pump, fans)

---

*Spec Version: 1.0*
*Date: January 25, 2026*
*Author: Autotech AI Team*
