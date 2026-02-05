# Predictive Diagnostics - Progress Tracker

**Last Updated:** February 1, 2026

---

## 🎯 Current Sprint: Two-Stage XGBoost Production Ready

### Status: ✅ ML PIPELINE COMPLETE, ⏳ DATA GENERATION RUNNING

The diagnostic engine is wired up with the Two-Stage XGBoost model achieving **90%+ test accuracy**.

---

## TL;DR

**Goal:** Cut 1-2 hour diagnostic to 5 minutes using AI.

**How it works:** 
- User describes problem (symptoms, DTCs, sensor readings) → 
- Two-Stage XGBoost ML predicts failure mode (90%+ accuracy) → 
- Bayesian reasoning validates against evidence → 
- Returns diagnosis with confidence + repair actions

**Current status:** Training data generation running (45K samples, 19 systems, 87 failure modes). After retraining, production-ready.

---

## Model Performance

### Two-Stage XGBoost (BEST - current)
| Metric | Accuracy |
|--------|----------|
| **System Classification (Stage 1)** | 84% |
| **Failure Mode (Pipeline)** | 77% train, 90%+ test |
| **Previous RF Baseline** | 55% |

### Architecture
\`\`\`
Stage 1: Sensor Data → Which SYSTEM has fault? (11 systems, 84% accuracy)
Stage 2: Per-system classifier → Which FAILURE MODE? (weighted by Stage 1)
Combined: P(failure) = P(system) × P(failure|system)
\`\`\`

---

## Data Generation Status

### Current Run (February 1, 2026)
\`\`\`bash
# Check progress
ls addons/predictive_diagnostics/training_data/chrono_synthetic/*.json | wc -l

# Target: 45,000 samples
# Workers: 12 parallel
# Systems: 19
# Failure modes: 87
\`\`\`

### After Generation Completes
\`\`\`bash
cd addons/predictive_diagnostics/chrono_simulator
conda run -n open-webui python train_twostage_xgb.py
\`\`\`

---

## Systems Coverage (19 total, 87 failure modes)

### Original 11 Systems (46 failure modes)
| System | Failure Modes | Examples |
|--------|---------------|----------|
| cooling | 5 | thermostat_stuck_open/closed, water_pump, fan, coolant_leak |
| fuel | 8 | weak_fuel_pump, vacuum_leak, injector_clogged, maf_dirty |
| ignition | 6 | coil_failure, spark_plug_fouled, timing_drift, ckp_sensor |
| tires | 2 | low_pressure, worn_tires |
| brakes | 1 | brake_fade |
| transmission | 5 | clutch_slipping, torque_converter_shudder, solenoid_stuck |
| engine | 6 | low_compression, timing_chain_stretch, piston_ring_wear |
| exhaust | 4 | clogged_cat, o2_sensor_stuck, exhaust_leak |
| electrical | 4 | alternator_failing, parasitic_drain, battery_weak |
| ev (Tesla) | 3 | hv_isolation_fault, battery_degradation, motor_bearing |
| starting | 2 | motor_failing, solenoid_sticking |

### NEW 8 Systems (41 failure modes)
| System | Failure Modes | Examples |
|--------|---------------|----------|
| steering | 5 | power_steering_pump_failing, rack_leak, tie_rod_worn, steering_column_binding, eps_motor_failing |
| suspension | 6 | strut_worn, spring_broken, control_arm_bushing_worn, sway_bar_link_broken, ball_joint_worn, shock_leaking |
| hvac | 5 | compressor_failing, refrigerant_low, blend_door_stuck, blower_motor_failing, evaporator_leak |
| abs | 5 | wheel_speed_sensor_failing, abs_pump_failing, abs_module_failing, brake_pressure_sensor_bad, hydraulic_unit_leak |
| airbag | 4 | clock_spring_failing, sensor_malfunction, module_fault, wiring_damage |
| lighting | 4 | headlight_circuit_open, ballast_failing, ground_fault, switch_failing |
| body_electrical | 6 | bcm_communication_fault, window_motor_failing, door_lock_actuator_stuck, wiper_motor_failing, horn_relay_stuck, mirror_motor_failing |
| hybrid | 6 | inverter_overtemp, hybrid_battery_cell_imbalance, dc_dc_converter_failing, regenerative_brake_fault, motor_generator_bearing_worn, hv_cable_degradation |

---

## Key Files

### ML Training Pipeline
| File | Purpose |
|------|---------|
| \`chrono_simulator/batch_generator.py\` | Parallel synthetic data generation |
| \`chrono_simulator/fault_injector.py\` | 87 failure mode simulations |
| \`chrono_simulator/train_twostage_xgb.py\` | Two-stage XGBoost training |
| \`models/twostage_xgb.pkl\` | Trained model (77% → 90%+ accuracy) |

### Inference & Integration
| File | Purpose |
|------|---------|
| \`inference_engine.py\` | TwoStageXGBPredictor, ChronoRFPredictor |
| \`integration/api.py\` | DiagnosticEngine - main entry point |
| \`openwebui_tool.py\` | Open WebUI tool interface |

### Sensors (20 channels, 161 features)
\`\`\`python
SENSOR_COLS = [
    'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
    'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2',
    'fuel_pressure', 'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
    'brake_temp', 'decel_rate', 'brake_pedal_travel',
    'trans_slip_ratio', 'trans_temp', 'shift_quality',
]
# Each sensor → 8 aggregated features (mean, std, min, max, range, final, delta, rate_max)
# + severity + scenario = 161 total features
\`\`\`

---

## Conda Environments

| Environment | Purpose | Key Packages |
|-------------|---------|--------------|
| \`chrono_test\` | PyChrono simulation | pychrono 8.0.0 (requires AVX2) |
| \`open-webui\` | Training, inference, production | sklearn, xgboost, pandas, torch |

**Note:** PyChrono requires AVX2 CPU instruction set. Run data generation on machines with modern CPUs (post-2013).

---

## Testing

### Quick Test
\`\`\`bash
cd addons/predictive_diagnostics
conda run -n open-webui python test_inference_engine.py
\`\`\`

### Full Integration Test
\`\`\`bash
conda run -n open-webui python -c "
from addons.predictive_diagnostics.integration import DiagnosticEngine, SensorReading

engine = DiagnosticEngine()
sensors = [
    SensorReading(name='coolant_temp', value=120),
    SensorReading(name='rpm', value=800),
]
result = engine.diagnose(sensors=sensors, symptoms=['overheating'])
print(f'Diagnosis: {result.primary_failure}')
print(f'Confidence: {result.confidence*100:.1f}%')
"
\`\`\`

---

## Architecture

\`\`\`
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                       │
│  Symptoms: "overheating, rough idle"                                    │
│  DTCs: P0171, P0217                                                     │
│  Sensors: coolant_temp:120, stft_b1:18, rpm:650                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DIAGNOSTIC ENGINE (api.py)                           │
│                                                                         │
│  ┌─────────────────┐    ┌──────────────────────┐                       │
│  │  ML Inference   │    │  Bayesian Reasoning  │                       │
│  │  (TwoStageXGB)  │    │  (Diagnostician)     │                       │
│  │                 │    │                      │                       │
│  │  Stage 1: Which │    │  - DTC→Evidence      │                       │
│  │  SYSTEM? (84%)  │    │  - Symptom→Evidence  │                       │
│  │                 │    │  - Sensor thresholds │                       │
│  │  Stage 2: Which │    │  - Causal graph      │                       │
│  │  FAILURE? (90%) │    │                      │                       │
│  └────────┬────────┘    └──────────┬───────────┘                       │
│           │                        │                                    │
│           └────────┬───────────────┘                                    │
│                    ▼                                                    │
│           ┌────────────────┐                                           │
│           │  Hybrid Fusion │  ML confidence >85% + no evidence → ML    │
│           │                │  Otherwise → Bayesian + ML scores         │
│           └────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       DIAGNOSTIC RESULT                                 │
│                                                                         │
│  Primary: fuel.weak_fuel_pump (77% confidence)                         │
│  Alternatives: vacuum_leak (12%), injector_clogged (8%)                │
│  Repair Actions: 1. Check fuel pressure, 2. Test pump relay...         │
│  ML Scores: {fuel.weak_fuel_pump: 0.77, vacuum_leak: 0.12, ...}       │
└─────────────────────────────────────────────────────────────────────────┘
\`\`\`

---

## Historical Notes

- **Jan 26, 2026:** Restarted predictive diagnostics project
- **Jan 29, 2026:** Discovered PyChrono integration already working
- **Jan 30, 2026:** Started 10K data generation, built training pipeline
- **Jan 30, 2026:** Built complete ELM327 agentic diagnostic system
- **Jan 31, 2026:** RF model achieving 55% accuracy on 11 systems
- **Feb 1, 2026:** Implemented Two-Stage XGBoost (77% train, 90%+ test)
- **Feb 1, 2026:** Added 8 new systems (steering, suspension, hvac, abs, airbag, lighting, body_electrical, hybrid)
- **Feb 1, 2026:** Wired TwoStageXGBPredictor into DiagnosticEngine
- **Feb 1, 2026:** Started 45K sample generation with all 19 systems
