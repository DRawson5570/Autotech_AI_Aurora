# Predictive Diagnostics System - Technical Specification

**Version:** 5.0  
**Date:** January 29, 2026  
**Status:** Production Ready (Phase 1) + ELM327 Integration + **PyChrono Simulation (NEW!)**

---

## 📊 Current Implementation Status

### ✅ Phase 1: Expert System (COMPLETE - Production Ready)
- **78 failure modes** across 13 systems (cooling, fuel, ignition, charging, transmission, brakes, engine, steering, suspension, hvac, emissions, turbo, starting)
- **296 DTC mappings** with evidence types
- **Bayesian reasoning** with hand-coded likelihood tables
- **Discriminating tests** for each failure mode
- **Repair estimates** with labor/parts costs
- **99.7% accuracy** on synthetic test data

This is a **lookup-table expert system** with Bayesian probability updates.
It works well for common diagnostic scenarios.

### 🔨 Phase 2: ELM327 Live Diagnostics (IN PROGRESS)
- Real-time PID monitoring via Bluetooth/WiFi OBD-II adapters
- AI-directed diagnostic procedures ("rev to 2500 RPM")
- Live data interpretation with causal reasoning
- Bidirectional control where vehicle supports it

### � Phase 2.5: PyChrono Physics Simulation (NEW - January 2026)
**BREAKTHROUGH:** Integrated Project Chrono open-source physics engine for synthetic data generation.

**What we have working:**
- Full vehicle simulation (BMW E90, HMMWV, Sedan, etc.)
- Real powertrain physics (engine, transmission, drivetrain)
- OBD-II style data export (RPM, speed, torque, gear, throttle)
- Tire/suspension/terrain physics
- **Fault injection capability** (the key to training data!)

**Location:** `chrono_simulator/` subdirectory

**Why this matters:**
- Generate 1000s of labeled failure scenarios in hours (not months of real data collection)
- Physics-accurate sensor readings under fault conditions
- Cover rare failure modes that real data lacks
- Bridge sim-to-real with 10% real + 90% synthetic recipe

**See:** `chrono_simulator/demo_vehicle_obd.py` for working example.

### �🔮 Phase 3: First-Principles ML (FUTURE)
The vision below describes Phase 3 - true physics-based ML that can:
- Discover failure modes not explicitly programmed
- Learn causal relationships from physics simulation
- Transfer knowledge between vehicle types
- Handle novel compound failures

**This is PhD-level work and will be tackled after Phase 2.**

---

## 🎯 Vision (Phase 3)

Build an ML system that **learns automotive physics** - not memorizes lookup tables.

Given symptoms (PIDs, DTCs, observations), the system reasons backward through 
causal chains to identify root cause. It works because it understands HOW things fail,
not just THAT they fail.

**Key Distinction:**
- ❌ Current (Phase 1): "High coolant temp + P0217 → thermostat" (pattern matching)
- ✅ Goal (Phase 3): "What prevents heat dissipation? What causes that? What causes THAT?" (causal reasoning)

---

## Core Insight

**Failures are physics, not patterns.**

A coolant leak WILL cause overheating. That's not learned from data - it's derived 
from understanding: "coolant carries heat away → less coolant → less heat transfer → 
temperature rises."

The ML model's job is to **internalize this causal structure** so it can:
1. Reason forward: "If X fails, what symptoms appear?"
2. Reason backward: "Given these symptoms, what failed?"
3. Handle novel combinations it wasn't explicitly trained on

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           KNOWLEDGE ENCODING                                │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │   System Models     │  │  Component Models   │  │  Failure Taxonomy   │ │
│  │                     │  │                     │  │                     │ │
│  │  • Cooling system   │  │  • Thermostat       │  │  • Stuck open       │ │
│  │  • Fuel system      │  │  • Water pump       │  │  • Stuck closed     │ │
│  │  • Ignition         │  │  • Sensors          │  │  • Leaking          │ │
│  │  • Charging         │  │  • Actuators        │  │  • Degraded         │ │
│  │  • etc.             │  │  • etc.             │  │  • etc.             │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CAUSAL GRAPH GENERATION                              │
│                                                                             │
│  For each system × component × failure mode:                                │
│    "If {component} fails in {mode}, what happens to {observable}?"          │
│                                                                             │
│  Example:                                                                   │
│    System: Cooling                                                          │
│    Component: Thermostat                                                    │
│    Failure: Stuck open                                                      │
│    Effect chain:                                                            │
│      → Coolant flows through radiator constantly                            │
│      → Engine never reaches operating temp                                  │
│      → Coolant temp stays low (~160°F instead of 195°F)                     │
│      → ECU sees cold engine, runs rich                                      │
│      → Poor fuel economy, possible P0128                                    │
│                                                                             │
│  This generates a CAUSAL GRAPH, not a pattern table.                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHYSICS SIMULATION                                  │
│                                                                             │
│  Use causal models to SIMULATE failure progression:                         │
│                                                                             │
│  thermostat_stuck_open.simulate(duration=300sec) →                          │
│    t=0:    coolant_temp=70°F, stft=0%                                       │
│    t=60:   coolant_temp=120°F, stft=+3%  (warming slow)                     │
│    t=120:  coolant_temp=150°F, stft=+5%  (still not at operating)           │
│    t=180:  coolant_temp=162°F, stft=+6%  (plateaus below normal)            │
│    t=240:  coolant_temp=165°F, stft=+7%  (ECU compensating)                 │
│    t=300:  coolant_temp=163°F, stft=+8%  (steady state, never hit 195°F)    │
│                                                                             │
│  This generates TIME-SERIES training data showing HOW failures manifest.    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ML MODEL TRAINING                                   │
│                                                                             │
│  Train on simulated data to learn the CAUSAL STRUCTURE:                     │
│                                                                             │
│  Input: Observable state (PIDs, DTCs, symptoms)                             │
│  Output: Probability distribution over failure modes                        │
│                                                                             │
│  Model learns:                                                              │
│  • Which observations are CAUSED BY which failures                          │
│  • Temporal patterns (how failures evolve over time)                        │
│  • Compound failures (multiple things wrong)                                │
│  • Discriminating features (what separates similar failures)                │
│                                                                             │
│  Key: Model doesn't memorize "low temp = stuck open thermostat"             │
│       Model learns "this PATTERN of temperature behavior indicates..."      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RUNTIME INFERENCE                                   │
│                                                                             │
│  User provides: PIDs + DTCs + symptoms                                      │
│                                                                             │
│  System does:                                                               │
│  1. RECOGNIZE: "This looks like a cooling system issue" (fast)              │
│  2. REASON: "Given cooling issue, which specific failure?" (causal)         │
│  3. DISCRIMINATE: "Tests to distinguish between candidates"                 │
│  4. ITERATE: As user provides test results, update probabilities            │
│                                                                             │
│  Output: Ranked failures + discriminating tests + repair recommendations    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Structures

### 1. System Model

Represents an automotive system (cooling, fuel, ignition, etc.)

```python
@dataclass
class SystemModel:
    """A vehicle system with its physics and components."""
    
    id: str                          # "cooling", "fuel", "ignition"
    name: str                        # "Engine Cooling System"
    
    # Physics equations
    state_variables: List[str]       # ["coolant_temp", "coolant_flow", "fan_state"]
    physics_equations: Dict          # How state variables relate
    
    # Components in this system
    components: List[ComponentModel]
    
    # Observable outputs (PIDs we can read)
    observables: List[str]           # ["coolant_temp", "ect_voltage"]
    
    # Normal operating ranges
    normal_state: Dict[str, Tuple[float, float]]  # {"coolant_temp": (195, 220)}
    
    def simulate(self, failure: str, duration: float) -> TimeSeries:
        """Simulate system behavior with given failure mode."""
        pass
```

### 2. Component Model

Represents a component that can fail.

```python
@dataclass
class ComponentModel:
    """A component with its failure modes and effects."""
    
    id: str                          # "thermostat"
    name: str                        # "Engine Thermostat"
    component_type: ComponentType    # VALVE
    
    # What this component does (physics)
    function: str                    # "Controls coolant flow to radiator"
    inputs: List[str]                # ["coolant_temp"]
    outputs: List[str]               # ["coolant_flow_to_radiator"]
    
    # How it can fail
    failure_modes: List[FailureMode]
    
    # Effects of each failure on system state
    failure_effects: Dict[str, Callable]  # failure_mode -> effect function
```

### 3. Failure Mode

Represents one way a component can fail.

```python
@dataclass
class FailureMode:
    """A specific failure mode with its causal effects."""
    
    id: str                          # "stuck_open"
    name: str                        # "Thermostat Stuck Open"
    
    # Causal chain
    immediate_effect: str            # "Coolant flows through radiator constantly"
    cascade_effects: List[str]       # ["Engine stays cold", "Rich fuel mixture"]
    
    # Observable symptoms
    pid_effects: Dict[str, str]      # {"coolant_temp": "low", "stft": "positive"}
    expected_dtcs: List[str]         # ["P0128"]
    symptoms: List[str]              # ["slow warmup", "poor fuel economy"]
    
    # Diagnostic
    discriminating_test: str         # "Compare coolant temp to IR reading"
    repair_action: str               # "Replace thermostat"
```

### 4. Causal Graph

The compiled knowledge of all failure → symptom relationships.

```python
@dataclass
class CausalGraph:
    """Graph connecting failures to observable symptoms."""
    
    # Nodes
    failure_nodes: List[str]         # All possible failures
    symptom_nodes: List[str]         # All observable symptoms
    
    # Edges (failure → symptom with strength)
    edges: Dict[Tuple[str, str], float]  # (failure, symptom) → probability
    
    # Temporal patterns
    temporal_signatures: Dict[str, TimeSeries]  # failure → how it evolves
    
    def get_failures_for_symptoms(self, symptoms: List[str]) -> List[Tuple[str, float]]:
        """Given symptoms, return probable failures with probabilities."""
        pass
    
    def get_discriminating_test(self, candidates: List[str]) -> str:
        """Return test that best distinguishes between candidate failures."""
        pass
```

---

## Module Structure

```
addons/predictive_diagnostics/
├── SPEC.md                      # This document
├── __init__.py
│
├── knowledge/                   # Domain knowledge encoding
│   ├── __init__.py
│   ├── systems.py               # System models (cooling, fuel, etc.)
│   ├── components.py            # Component models (thermostat, pump, etc.)
│   ├── failures.py              # Failure taxonomy (stuck_open, leaking, etc.)
│   └── causal_graph.py          # Compiled causal relationships
│
├── simulation/                  # Physics-based simulation
│   ├── __init__.py
│   ├── engine.py                # Simulation engine
│   ├── thermal.py               # Thermal physics
│   ├── fluid.py                 # Fluid dynamics
│   ├── electrical.py            # Electrical physics
│   └── data_generator.py        # Generate training data from simulations
│
├── ml/                          # Machine learning
│   ├── __init__.py
│   ├── model.py                 # Neural network architecture
│   ├── trainer.py               # Training loop
│   ├── inference.py             # Runtime inference
│   └── embeddings.py            # Embed symptoms/failures in vector space
│
├── reasoning/                   # Diagnostic reasoning
│   ├── __init__.py
│   ├── bayesian.py              # Bayesian probability updates
│   ├── discriminator.py         # Find discriminating tests
│   └── session.py               # Multi-turn diagnostic session
│
├── integration/                 # External integrations
│   ├── __init__.py
│   ├── mitchell.py              # Query Mitchell for vehicle-specific data
│   └── openwebui_tool.py        # Open WebUI interface
│
└── models/                      # Trained model files
    └── diagnostic_model.pt
```

---

## Implementation Phases

### Phase 1: Knowledge Encoding (Week 1)

**Goal:** Encode automotive physics as computable models.

**Deliverables:**
1. `knowledge/systems.py` - Models for major systems:
   - Cooling system
   - Fuel system
   - Ignition system
   - Charging system
   - Intake/exhaust

2. `knowledge/components.py` - Models for components:
   - Thermostats, pumps, fans (cooling)
   - Fuel pump, injectors, regulator (fuel)
   - Coils, plugs, sensors (ignition)
   - Alternator, battery (charging)

3. `knowledge/failures.py` - Failure modes per component type:
   - Sensors: stuck_high, stuck_low, drift, slow_response
   - Actuators: stuck, weak, erratic
   - Valves: stuck_open, stuck_closed, leaking
   - Electrical: open, short, high_resistance
   - OEM-specific modules: Support for manufacturer-specific failure sets like Tesla (`failures_tesla.py`) has been added, covering battery isolation, PTC heater issues, drive unit noise, 12V auxiliary failures, and charge port faults.
   - EV / PHEV: Added dedicated EV and PHEV failure modules covering battery, powertrain, charging, and thermal systems. New systems/components registered: `ev_battery`, `ev_powertrain`, `ev_charging`, `ev_thermal`, `phev_hybrid`, `phev_battery`, `phev_thermal`, `phev_powertrain` (see `knowledge/failures_ev.py` and `knowledge/failures_phev.py`).

4. `knowledge/causal_graph.py` - Compile into causal graph

**Validation:** Can we trace "thermostat stuck open" → "coolant temp low" → "P0128"?


### Phase 2: Physics Simulation (Week 2)

**Goal:** Generate realistic failure progressions.

**Deliverables:**
1. `simulation/engine.py` - Core simulation loop
2. `simulation/thermal.py` - Heat transfer, temperature dynamics
3. `simulation/fluid.py` - Flow, pressure, leaks
4. `simulation/electrical.py` - Voltage, current, resistance
5. `simulation/data_generator.py` - Generate training datasets

**Key Features:**
- Time-series output (not just snapshots)
- Multiple operating conditions (idle, cruise, load)
- Compound failures (multiple things wrong)
- Realistic noise and variation

**Validation:** Simulated "water pump failure" shows:
- Coolant temp rising over time
- Eventually overheats
- Matches real-world behavior

### Phase 3: ML Model (Week 3)

**Goal:** Train model to recognize failure patterns.

**Deliverables:**
1. `ml/model.py` - Network architecture
   - Input: PID values + DTCs + symptoms (embedded)
   - Output: Probability distribution over failures
   - Consider: Transformer for temporal patterns, or GNN for causal structure

2. `ml/trainer.py` - Training pipeline
   - Train on simulated data
   - Validate on held-out simulations
   - Test on (eventually) real cases

3. `ml/inference.py` - Runtime inference
   - Fast forward pass
   - Uncertainty estimation
   - Top-k failures with probabilities

**Validation:** 
- Given simulated "vacuum leak" data, model predicts "vacuum_leak" with high confidence
- Model generalizes to unseen failure combinations

### Phase 4: Diagnostic Reasoning (Week 4)

**Goal:** Build interactive diagnostic system.

**Deliverables:**
1. `reasoning/bayesian.py` - Update probabilities as evidence comes in
2. `reasoning/discriminator.py` - Find tests that distinguish candidates
3. `reasoning/session.py` - Multi-turn conversation state

**Features:**
- Initial diagnosis from symptoms
- Suggest discriminating test
- User reports result
- Update probabilities
- Repeat until confident

**Validation:** 
- System correctly narrows from "cooling issue" to "stuck thermostat" through 2-3 tests

### Phase 5: Integration (Week 5)

**Goal:** Deploy as Open WebUI tool.

**Deliverables:**
1. `integration/openwebui_tool.py` - Tool interface
2. `integration/mitchell.py` - Vehicle-specific data lookup

**Features:**
- Accept vehicle + symptoms
- Query Mitchell for vehicle-specific info (optional, enhances accuracy)
- Return diagnosis + recommended tests
- Support follow-up conversation

---

## Key Technical Decisions

### Why Physics Simulation (not real data)?

1. **Coverage:** Can generate data for ANY failure, including rare ones
2. **Labels:** Know ground truth (we created the failure)
3. **Combinations:** Can simulate compound failures
4. **Control:** Can vary operating conditions systematically
5. **No privacy issues:** Synthetic data

Real data is valuable for VALIDATION, not training.

---

## 🆕 PyChrono Integration (January 2026)

### What is Project Chrono?

[Project Chrono](https://projectchrono.org/) is an open-source, high-performance C++ library
for multiphysics simulation. It's used by Waymo, NIRA Dynamics, and academic research labs
for vehicle dynamics simulation.

**Key capabilities:**
- Multi-body vehicle dynamics (suspension, steering, drivetrain)
- Engine/transmission torque curves
- Tire physics (TM-Easy, PAC89, FTire)
- Terrain interaction
- Sensor simulation (we add our own OBD-II layer)

### Installation

```bash
# Create dedicated environment (don't pollute main env)
conda create -n chrono_test python=3.10 -y
conda activate chrono_test
conda install -c projectchrono -c conda-forge pychrono=8.0.0 -y
```

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SYNTHETIC DATA GENERATION PIPELINE                       │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │   PyChrono      │     │  Fault          │     │  OBD-II         │       │
│  │   Vehicle       │────▶│  Injection      │────▶│  Data Export    │       │
│  │   Physics       │     │  Layer          │     │                 │       │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘       │
│          │                       │                       │                 │
│          ▼                       ▼                       ▼                 │
│  - BMW E90, HMMWV,       - Engine misfire        - RPM, Speed              │
│    Sedan, CityBus        - Sensor drift          - Throttle position       │
│  - Full powertrain       - Stuck throttle        - Engine torque           │
│  - Tire/suspension       - Worn tires            - Transmission gear       │
│  - Terrain contact       - Brake fade            - Wheel speeds            │
│                          - Transmission slip     - Tire forces             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KNOWLEDGE BASE INTEGRATION                          │
│                                                                             │
│  For each FailureMode in knowledge/failures_*.py:                           │
│                                                                             │
│    1. Map to Chrono fault injection                                         │
│       - "vacuum_leak" → reduce engine torque, add positive STFT             │
│       - "worn_tires" → reduce tire friction coefficient                     │
│       - "misfire" → add torque fluctuation at engine                        │
│                                                                             │
│    2. Run N simulations with variations:                                    │
│       - Different severity levels (10%, 30%, 50% degradation)               │
│       - Different operating conditions (idle, cruise, WOT)                  │
│       - Different ambient conditions (temp, road surface)                   │
│                                                                             │
│    3. Export labeled OBD-II traces:                                         │
│       - Ground truth: failure_mode_id from FailureMode.id                   │
│       - Time series: PID values every 100ms                                 │
│       - Context: vehicle, conditions, severity                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ML TRAINING DATA                                    │
│                                                                             │
│  Output: training_data/chrono_synthetic/                                    │
│    ├── vacuum_leak_001.json                                                 │
│    ├── vacuum_leak_002.json                                                 │
│    ├── thermostat_stuck_open_001.json                                       │
│    ├── ...                                                                  │
│    └── manifest.csv  (label, file, vehicle, conditions)                     │
│                                                                             │
│  Each file contains:                                                        │
│    {                                                                        │
│      "failure_mode": "vacuum_leak",                                         │
│      "vehicle": "bmw_e90",                                                  │
│      "severity": 0.3,                                                       │
│      "conditions": {"ambient_temp": 70, "road": "flat"},                    │
│      "time_series": [                                                       │
│        {"t": 0.0, "rpm": 750, "speed": 0, "stft": 0, ...},                  │
│        {"t": 0.1, "rpm": 755, "speed": 0, "stft": 2, ...},                  │
│        ...                                                                  │
│      ]                                                                      │
│    }                                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fault Injection Methods

| Failure Mode | Chrono Injection Method |
|--------------|------------------------|
| **Vacuum leak** | Reduce effective engine torque, post-process STFT positive |
| **Misfire** | Add periodic torque dips (cylinder dropout pattern) |
| **Worn tires** | Reduce tire friction coefficient (SetFriction) |
| **Stuck throttle** | Clamp throttle input to fixed value |
| **Brake fade** | Reduce brake torque over time |
| **Trans slip** | Reduce torque transmission efficiency |
| **Sensor drift** | Add bias to post-processed sensor readings |
| **Low tire pressure** | Modify tire stiffness/damping |

### Available Vehicle Templates

From PyChrono 8.0.0:
- **BMW_E90** - Sedan (3-series equivalent)
- **HMMWV** - Heavy truck (military Humvee)
- **Sedan** - Generic sedan
- **Gator** - Utility vehicle
- **CityBus** - Bus
- **MAN_5t/7t/10t** - Commercial trucks
- **ARTcar** - Small EV

### File Structure

```
chrono_simulator/
├── demo_vehicle_obd.py      # Working demo (run this first!)
├── test_vehicle_sim.py      # Basic tests
├── fault_injector.py        # Fault injection layer (TODO)
├── obd_exporter.py          # Export to OBD-II format (TODO)
├── batch_generator.py       # Generate 1000s of scenarios (TODO)
└── README.md                # Setup instructions
```

### Next Steps

1. **Create fault_injector.py** - Map FailureMode → Chrono injection
2. **Create obd_exporter.py** - Export time-series in training format
3. **Create batch_generator.py** - Scale to 10k+ scenarios
4. **Sim-to-real validation** - Compare synthetic to real OBD captures

---
### Why Causal Graph (not just patterns)?

1. **Generalization:** Understands WHY, can handle new situations
2. **Explanation:** Can trace reasoning path for user
3. **Discrimination:** Knows what tests differentiate similar failures
4. **Compound failures:** Can reason about multiple causes

Pattern matching fails when:
- Symptoms don't exactly match training data
- Multiple failures present
- Need to explain reasoning


### What Model Architecture?

Options:
1. **Transformer:** Good for sequences, handles variable-length input
2. **GNN:** Natural for causal graphs, can do message passing
3. **Hybrid:** Transformer encoder + GNN reasoning

Start simple (MLP or small Transformer), add complexity if needed.


### How to Handle Vehicle Specifics?

Two approaches:
1. **Generic model + vehicle embedding:** Train one model, condition on vehicle
2. **Per-vehicle fine-tuning:** Generic base, fine-tune per platform

Start with generic (physics is universal), add vehicle conditioning later.

---

## Files to Keep

From existing code:
- `physics_simulator.py` - Good foundation, needs expansion
- `taxonomy.py` - Good failure mode definitions  
- `pid_specs.py` - PID definitions and ranges
- `rf_trainer.py` - Reference for training pipeline (will rewrite)

## Files to Delete/Replace

- `diagnostic_engine.py` - The 199 signatures lookup table (wrong approach)
- `combined_engine.py` - Wrapper around wrong approach
- `compound_fault_explorer.py` - GA explorer (not needed with proper model)
- `openwebui_tool.py` - Will rewrite with new architecture

---

## Success Criteria

### Minimum Viable Product

1. **Coverage:** Handles 5 major systems (cooling, fuel, ignition, charging, intake)
2. **Accuracy:** Top-3 accuracy > 80% on simulated test set
3. **Reasoning:** Can explain why it suggested each failure
4. **Discrimination:** Suggests useful follow-up tests

### "World's Best" Target

1. **Coverage:** All common failure modes (~500+)
2. **Accuracy:** Top-1 > 70%, Top-3 > 90% on REAL cases
3. **Speed:** Initial diagnosis in < 5 seconds
4. **Integration:** Pulls vehicle-specific data from Mitchell
5. **Learning:** Improves from user feedback on real cases

---

## Questions to Resolve

1. **Snapshot vs Time-Series:** Technicians often have single snapshots. 
   Can we still do good diagnosis? Or do we need to guide them to capture time-series?

2. **DTCs vs PIDs:** How much weight to put on DTC codes vs live data?
   Some DTCs are very specific, others are generic.

3. **Mitchell Integration:** When do we query Mitchell? 
   - At diagnosis time for vehicle-specific data?
   - Pre-build fault trees per vehicle platform?
   - Or trust that physics is universal enough?

4. **Compound Failures:** How to handle multiple simultaneous failures?
   Real cars often have cascading issues.

---

## Appendix: Example Failure Chains

### Cooling System

```
thermostat_stuck_open:
  cause: Thermostat fails in open position
  immediate: Coolant flows through radiator constantly
  cascade:
    - Engine takes long to warm up
    - ECU sees cold engine, enriches fuel
    - STFT goes positive (adding fuel)
    - If prolonged, LTFT adapts positive
    - Poor fuel economy
    - Possible P0128 (coolant temp below threshold)
  observables:
    coolant_temp: low (160-175°F instead of 195-220°F)
    warmup_time: long (>10 min)
    stft: positive (+5 to +15%)
    fuel_economy: poor
  dtcs: [P0128]
  discriminating_test: 
    "Block radiator airflow - temp should rise. If stays low, thermostat stuck open"

thermostat_stuck_closed:
  cause: Thermostat fails in closed position
  immediate: No coolant flow to radiator
  cascade:
    - Heat cannot dissipate
    - Temperature rises continuously
    - ECU may retard timing to protect engine
    - Eventually overheats
    - Possible head gasket damage if severe
  observables:
    coolant_temp: high, rising (>230°F)
    timing_advance: may retard
    engine_load: may increase (fighting timing retard)
  dtcs: [P0217, P0118]
  discriminating_test:
    "Feel radiator hoses - if inlet hot but outlet cold, no flow through radiator"

water_pump_failure:
  cause: Water pump impeller fails or shaft seizes
  immediate: No coolant circulation
  cascade:
    - Same as thermostat stuck closed (overheating)
    - But temperature rise is FASTER (no flow anywhere)
    - May hear noise from pump
  observables:
    coolant_temp: high, rising fast
    pump_noise: possible whine or grind
  discriminating_test:
    "With thermostat stuck closed, there's still some flow in the block.
     With pump failure, temp rises MUCH faster. Also check for pump noise/play."
```

### Fuel System

```
vacuum_leak:
  cause: Unmetered air entering intake
  immediate: Extra air not measured by MAF
  cascade:
    - Mixture goes lean
    - O2 sensor sees lean
    - ECU adds fuel (positive STFT)
    - If large leak, may not compensate enough
    - Rough idle (lean misfire)
    - Possible P0171/P0174
  observables:
    stft: positive (+10 to +25%)
    ltft: may adapt positive
    o2_b1s1: may show lean (low voltage)
    idle: rough, unstable
    rpm: may be erratic
  dtcs: [P0171, P0174, P0300]
  discriminating_test:
    "Spray carb cleaner around intake - RPM change indicates leak location"

fuel_pump_weak:
  cause: Fuel pump not producing enough pressure
  immediate: Low fuel rail pressure
  cascade:
    - Injectors can't deliver enough fuel
    - Goes lean under load
    - Fine at idle (low demand)
    - Stumble/hesitation on acceleration
    - May stall under load
  observables:
    fuel_pressure: low (especially under load)
    stft: positive under load
    performance: poor acceleration
    idle: may be normal
  discriminating_test:
    "Fuel pressure test - should maintain pressure under load (WOT)"
```

---

*Specification Version: 5.0*  
*Last Updated: January 29, 2026*

---

## 🔌 ELM327 Live Diagnostics Integration (Phase 2)

### Vision

AI-directed automotive diagnosis with live data:

```
User: "2012 Jeep Liberty Sport 3.7 - Diagnose with scan tool"

AI: [Connects to ELM327 via Bluetooth]
    [Reads VIN → confirms 2012 Jeep Liberty 3.7L V6]
    [Reads DTCs: P0171, P0174 (System Lean Bank 1 & 2)]
    [Reads freeze frame data]
    [Monitors live PIDs: STFT, LTFT, MAF, coolant temp]

AI: "I see lean codes on both banks. Let me check live data...
     STFT Bank 1: +18%, Bank 2: +16%
     LTFT Bank 1: +12%, Bank 2: +10%
     
     Both banks equally lean suggests a common cause - likely:
     1. Vacuum leak at intake manifold
     2. MAF sensor contaminated
     3. Low fuel pressure
     
     Let's narrow it down. Please:
     1. Start the engine and let it idle
     2. I'll watch the fuel trims while you spray brake cleaner around the intake"

User: "Ready"

AI: [Monitors STFT in real-time]
    "Spray around the throttle body gasket..."
    [STFT drops from +18% to +5%]
    "FOUND IT! When you sprayed the throttle body gasket area, fuel trim dropped
     significantly. You have a vacuum leak at the throttle body gasket.
     
     Repair: Replace throttle body gasket
     Parts: $15-30
     Labor: 0.5-1 hour"
```

### Bidirectional Control (Where Supported)

```
User: "The cooling fan isn't coming on"

AI: [Reads coolant temp: 210°F - fan should be commanded]
    [Checks fan command status via PID]
    
    "Coolant is at 210°F and the ECU IS commanding the fan on, but 
     I don't see RPM feedback. Let me try activating it directly..."
    
    [Sends Mode $08 actuator test command for fan relay]
    
    "Fan still not running with direct command. This rules out ECU/software.
     The problem is:
     - Fan relay (most common)
     - Fan motor
     - Wiring between relay and motor
     
     Quick test: Jumper the fan relay - if fan runs, replace relay."
```

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OPEN WEBUI                                        │
│                                                                             │
│   User: "diagnose with scan tool"                                           │
│                                 │                                           │
│                                 ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    DIAGNOSTIC TOOL                                   │  │
│   │                                                                      │  │
│   │   tools:                                                             │  │
│   │     - elm327_connect(device)                                         │  │
│   │     - elm327_read_dtcs()                                             │  │
│   │     - elm327_read_pids(pid_list)                                     │  │
│   │     - elm327_monitor_pids(pid_list, duration)                        │  │
│   │     - elm327_clear_dtcs()                                            │  │
│   │     - elm327_actuator_test(component)  # bidirectional               │  │
│   │     - diagnose(dtcs, pids, symptoms)   # existing tool               │  │
│   │                                                                      │  │
│   └───────────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────────────┼─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ELM327 SERVICE                                      │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  addons/elm327/                                                      │  │
│   │    ├── service.py          # Main service (runs on user's machine)  │  │
│   │    ├── connection.py       # Bluetooth/WiFi/USB connection          │  │
│   │    ├── protocol.py         # OBD-II protocol implementation         │  │
│   │    ├── pids.py             # PID definitions and decoders           │  │
│   │    └── bidirectional.py    # Mode $08 and UDS commands              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   Connects via:                                                             │
│     - Bluetooth: /dev/rfcomm0 or Windows COM port                          │
│     - WiFi: TCP to 192.168.0.10:35000 (typical ELM327 WiFi)                │
│     - USB: /dev/ttyUSB0 or Windows COM port                                │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │   ELM327        │
                          │   Adapter       │
                          │   (Bluetooth/   │
                          │    WiFi/USB)    │
                          └────────┬────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │   Vehicle       │
                          │   OBD-II Port   │
                          └─────────────────┘
```

### Supported Operations

#### Tier 1: Standard OBD-II (All Vehicles 1996+)

| Operation | Mode | Description |
|-----------|------|-------------|
| Read DTCs | 03 | Stored diagnostic trouble codes |
| Clear DTCs | 04 | Clear codes and freeze frame |
| Read Freeze Frame | 02 | Snapshot at time of DTC |
| Read PIDs | 01 | Live sensor data (200+ standard PIDs) |
| Read VIN | 09 | Vehicle identification number |
| Pending DTCs | 07 | DTCs from current drive cycle |
| Permanent DTCs | 0A | DTCs that survive clear |

#### Tier 2: Enhanced OBD-II (Many Vehicles)

| Operation | Mode | Description |
|-----------|------|-------------|
| Actuator Test | 08 | Command actuators (fan, EVAP, etc.) |
| Vehicle Info | 09 | ECU serial numbers, calibration IDs |

#### Tier 3: Manufacturer-Specific (Vehicle Dependent)

| Operation | Protocol | Description |
|-----------|----------|-------------|
| Full Bidirectional | UDS 0x2F | InputOutputControlByIdentifier |
| Extended PIDs | Various | Manufacturer-specific sensor data |
| Module Programming | UDS | Requires security access |

### AI-Directed Diagnostic Procedures

The AI can request user actions and monitor results:

```python
# Example: AI-directed vacuum leak test
async def vacuum_leak_test(elm: ELM327Connection):
    """AI monitors fuel trims while user sprays intake."""
    
    # Start monitoring
    baseline = await elm.read_pids(['STFT_B1', 'STFT_B2'])
    
    print("I'm monitoring fuel trims. Please spray brake cleaner around:")
    print("1. Throttle body gasket")
    await asyncio.sleep(5)
    reading1 = await elm.read_pids(['STFT_B1', 'STFT_B2'])
    if fuel_trim_dropped(baseline, reading1):
        return "FOUND: Vacuum leak at throttle body gasket"
    
    print("2. Intake manifold gasket")
    await asyncio.sleep(5)
    reading2 = await elm.read_pids(['STFT_B1', 'STFT_B2'])
    if fuel_trim_dropped(baseline, reading2):
        return "FOUND: Vacuum leak at intake manifold gasket"
    
    # ... continue testing other areas
```

### AI-Requested Engine States

```python
# Example: AI needs data at specific RPM
async def test_at_rpm(elm: ELM327Connection, target_rpm: int):
    """Request user bring engine to specific RPM, then capture data."""
    
    print(f"Please rev and hold the engine at {target_rpm} RPM")
    
    # Wait for target RPM
    while True:
        rpm = await elm.read_pid('RPM')
        if abs(rpm - target_rpm) < 200:
            break
        await asyncio.sleep(0.1)
    
    print("Perfect, hold it there...")
    
    # Capture data at target RPM
    data = await elm.capture_snapshot([
        'RPM', 'MAF', 'MAP', 'STFT_B1', 'STFT_B2', 
        'TIMING_ADV', 'COOLANT_TEMP', 'IAT'
    ], duration=5.0)
    
    return data
```

### Bidirectional Control Examples

Where vehicle supports it:

```python
# Fan control (Mode $08 TID $00 or manufacturer-specific)
await elm.actuator_test('cooling_fan', 'on')
await asyncio.sleep(10)
await elm.actuator_test('cooling_fan', 'off')

# EVAP purge test
await elm.actuator_test('evap_purge', 'on')

# Fuel pump prime
await elm.actuator_test('fuel_pump', 'prime')

# Injector balance test (manufacturer-specific)
await elm.injector_balance_test()
```

### Implementation Plan

1. **Core ELM327 library** (`addons/elm327/`)
   - Connection management (BT/WiFi/USB)
   - AT command interface
   - OBD-II protocol modes 01-0A
   - PID encoding/decoding

2. **Open WebUI Tool** (`addons/elm327/openwebui_tool.py`)
   - Tool definitions for AI to call
   - Async operations with status updates
   - Integration with diagnostic reasoning

3. **Diagnostic Procedures** (`addons/elm327/procedures/`)
   - Pre-built test sequences
   - AI can compose custom sequences
   - User interaction patterns

4. **Vehicle Database** (`addons/elm327/vehicles/`)
   - Supported PIDs per make/model/year
   - Bidirectional capability matrix
   - Known protocol quirks

---

*Specification Version: 5.0*  
*Last Updated: January 29, 2026*
