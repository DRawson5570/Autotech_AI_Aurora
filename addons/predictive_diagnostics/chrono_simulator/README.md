# PyChrono Vehicle Simulation for Diagnostic Training Data

**Status:** ✅ Working (January 29, 2026)

This module uses [Project Chrono](https://projectchrono.org/) to generate synthetic
vehicle diagnostic data for ML training. Instead of collecting millions of real OBD-II
captures (expensive, time-consuming, privacy concerns), we simulate vehicles with
injected faults and export the resulting sensor data.

## Quick Start

```bash
# Create dedicated environment
conda create -n chrono_test python=3.10 -y
conda activate chrono_test
conda install -c projectchrono -c conda-forge pychrono=8.0.0 -y

# Run demo
python demo_vehicle_obd.py
```

## What's Working

- ✅ Full vehicle physics (BMW E90, HMMWV, Sedan, etc.)
- ✅ Engine/transmission simulation with torque curves
- ✅ OBD-II style data extraction (RPM, speed, torque, gear)
- ✅ Tire/suspension dynamics
- ✅ Terrain interaction

## Available Vehicle Templates

| Vehicle | Type | Mass (kg) | Wheelbase (m) |
|---------|------|-----------|---------------|
| BMW_E90 | Sedan | ~1,500 | 2.776 |
| HMMWV | Military truck | 2,573 | 3.378 |
| Sedan | Generic | ~1,400 | ~2.7 |
| CityBus | Bus | ~12,000 | ~6.0 |
| Gator | Utility | ~600 | ~1.5 |
| MAN_5t/7t/10t | Commercial truck | varies | varies |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Vehicle       │────▶│   Fault         │────▶│   OBD-II        │
│   Physics       │     │   Injection     │     │   Export        │
│   (Chrono)      │     │   Layer         │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
  Engine torque           Modify inputs/          JSON time-series
  Transmission            outputs to              with ground truth
  Tires/suspension        simulate faults         failure labels
```

## Fault Injection Approach

Since Chrono simulates vehicle dynamics (not internal engine combustion), we inject
faults by modifying:

1. **Engine torque output** - Reduce for misfire, increase resistance
2. **Throttle response** - Stuck, delayed, partial
3. **Tire friction** - Worn tires, wet conditions
4. **Brake torque** - Reduced for fade/wear
5. **Post-processing** - Add sensor drift, noise, bias to readings

### Example Fault Mappings

| Diagnostic Failure | Chrono Simulation |
|-------------------|-------------------|
| `vacuum_leak` | Reduce engine torque 5-15%, add +5-15% to STFT |
| `misfire_cylinder_1` | Drop torque to 0 every 4th cycle |
| `worn_tires` | `tire.SetFriction(0.5)` instead of 0.9 |
| `stuck_throttle` | `throttle = max(driver_throttle, 0.3)` |
| `brake_fade` | Reduce brake torque under sustained use |
| `transmission_slip` | Reduce torque transmission efficiency |
| `sensor_drift` | Add bias to post-processed readings |

## Output Format

Each simulation produces a JSON file:

```json
{
  "failure_mode": "vacuum_leak",
  "failure_mode_id": "fuel.vacuum_leak",
  "vehicle": "bmw_e90",
  "severity": 0.3,
  "conditions": {
    "ambient_temp": 70,
    "road_surface": "asphalt",
    "initial_state": "cold_start"
  },
  "time_series": [
    {"t": 0.0, "rpm": 750, "speed_kmh": 0, "stft_b1": 0, "coolant_temp": 70, ...},
    {"t": 0.1, "rpm": 755, "speed_kmh": 0, "stft_b1": 2, "coolant_temp": 72, ...},
    ...
  ],
  "metadata": {
    "simulator": "pychrono",
    "version": "8.0.0",
    "generated": "2026-01-29T12:00:00Z"
  }
}
```

## Integration with Knowledge Base

The `failure_mode_id` maps directly to entries in `knowledge/failures_*.py`:

```python
# From knowledge/failures_fuel.py
VACUUM_LEAK = FailureMode(
    id="fuel.vacuum_leak",
    name="Vacuum Leak",
    ...
)

# Chrono generates training data labeled with "fuel.vacuum_leak"
# ML model learns to predict this from sensor patterns
```

## Files

| File | Purpose |
|------|---------|
| `demo_vehicle_obd.py` | Working demo - run this first |
| `test_vehicle_sim.py` | Basic component tests |
| `fault_injector.py` | Fault injection layer (TODO) |
| `obd_exporter.py` | Export to training format (TODO) |
| `batch_generator.py` | Generate 1000s of scenarios (TODO) |

## Why This Matters

1. **Scale:** Generate 10,000+ labeled failure scenarios in hours
2. **Coverage:** Include rare failures that real data lacks
3. **Ground truth:** Know exactly what's wrong (we created the fault)
4. **Variations:** Test across severity levels, conditions, vehicles
5. **No privacy:** Synthetic data has no PII concerns

## References

- [Project Chrono](https://projectchrono.org/)
- [PyChrono Python API](https://api.projectchrono.org/pychrono_introduction.html)
- [Chrono::Vehicle Module](https://api.projectchrono.org/manual_vehicle.html)
- [Grok's recommendations](../../../docs/grok_automotive_physics_engines.pdf)
