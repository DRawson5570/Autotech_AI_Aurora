# ML Physics-Based Diagnostic Engine

## Vision

Train a neural network to **learn automotive physics** from first principles, enabling it to reason about failures the way the system itself behaves. Unlike lookup tables or pattern matching, this model understands *why* symptoms occur.

> "Diagnosis becomes natural because the AI thinks like the system itself." - Grok

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ML PHYSICS DIAGNOSTIC ENGINE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Physics         │    │ Synthetic Data  │    │ Neural Network  │         │
│  │ Simulators      │───►│ Generator       │───►│ Training        │         │
│  │ (cooling, fuel, │    │ (millions of    │    │ (learns causal  │         │
│  │  ignition...)   │    │  scenarios)     │    │  relationships) │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                                         │                   │
│                                                         ▼                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ Real Vehicle    │    │ Inference       │    │ Trained Model   │         │
│  │ Data (PIDs,     │───►│ Engine          │◄───│ (LoRA adapter   │         │
│  │  DTCs, symptoms)│    │                 │    │  or standalone) │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
│                                │                                            │
│                                ▼                                            │
│                    ┌─────────────────────────┐                             │
│                    │ Diagnostic Output       │                             │
│                    │ - Root cause + conf.    │                             │
│                    │ - Physics explanation   │                             │
│                    │ - Discriminating tests  │                             │
│                    └─────────────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Why ML Instead of Pure Physics Simulation?

| Aspect | Physics Simulator | ML Physics Model |
|--------|-------------------|------------------|
| **Development** | Must encode each system manually | Learns from simulation data |
| **Novel failures** | Only handles encoded faults | May generalize to unseen combinations |
| **Multiple systems** | Independent simulators | Single model learns cross-system interactions |
| **Real-world noise** | Assumes perfect sensors | Can learn sensor noise patterns |
| **Speed** | Fast (direct calculation) | Very fast (forward pass) |
| **Explainability** | Perfect (equations visible) | Requires attention/attribution analysis |
| **Training data** | None needed | Generated from physics simulators |

## Key Insight: Synthetic Training Data

We don't need millions of real failure cases. We **generate training data from physics simulators**:

```
For each vehicle type:
    For each operating condition (RPM, load, ambient, speed):
        For each fault combination:
            Run physics simulation → Get sensor readings
            Create training sample: (inputs, fault_label, physics_trace)
```

This gives us:
- **Millions of labeled examples** without real vehicle data
- **Rare fault combinations** that would take years to collect naturally
- **Ground truth labels** (we know exactly what fault was injected)
- **Physics traces** for explainability training

## Model Architecture Options

### Option 1: LoRA Adapter on Foundation Model

Fine-tune a pre-trained LLM (e.g., Llama 3.1 8B) with automotive physics knowledge.

```
┌─────────────────────────────────────────────────────────┐
│  Llama 3.1 8B (frozen weights)                          │
│  ├── General language understanding                     │
│  ├── Reasoning capabilities                             │
│  └── World knowledge                                    │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  LoRA Adapter (~100M params)                    │   │
│  │  ├── Automotive physics relationships           │   │
│  │  ├── Failure mode signatures                    │   │
│  │  ├── Diagnostic reasoning patterns              │   │
│  │  └── Technical vocabulary mapping               │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Leverages LLM reasoning capabilities
- Natural language input/output
- Can incorporate text from TSBs, repair manuals
- Smaller training footprint

**Cons:**
- May hallucinate physics relationships
- Harder to verify correctness
- Slower inference than specialized model

### Option 2: Custom Physics-Informed Neural Network

Purpose-built architecture that encodes physics constraints.

```
┌─────────────────────────────────────────────────────────┐
│  Input Layer                                            │
│  ├── Sensor values (normalized)                         │
│  ├── Operating conditions                               │
│  └── Vehicle parameters                                 │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Physics-Constrained Hidden Layers              │   │
│  │  ├── Conservation of energy enforced            │   │
│  │  ├── Mass flow continuity                       │   │
│  │  ├── Thermodynamic bounds                       │   │
│  │  └── Monotonicity constraints                   │   │
│  └─────────────────────────────────────────────────┘   │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Fault Hypothesis Heads                         │   │
│  │  ├── Per-component fault probability            │   │
│  │  ├── Severity estimation                        │   │
│  │  └── Confidence calibration                     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Physics constraints prevent impossible predictions
- Faster inference
- More predictable behavior
- Easier to verify

**Cons:**
- Requires careful architecture design
- Less flexible for new failure modes
- No natural language interface

### Option 3: Hybrid Approach (Recommended)

Combine physics simulation with ML for best of both worlds.

```
┌─────────────────────────────────────────────────────────┐
│  Stage 1: Physics Simulation                            │
│  ├── Run deterministic physics model                    │
│  ├── Generate expected sensor values                    │
│  └── Compute residuals (actual - expected)              │
│           │                                             │
│           ▼                                             │
│  Stage 2: ML Fault Classifier                           │
│  ├── Input: residuals + operating conditions            │
│  ├── Trained on synthetic fault data                    │
│  └── Output: fault probabilities                        │
│           │                                             │
│           ▼                                             │
│  Stage 3: LLM Explanation Generator                     │
│  ├── Input: fault hypothesis + physics trace            │
│  ├── LoRA-tuned for automotive explanations             │
│  └── Output: Natural language diagnosis + next steps    │
└─────────────────────────────────────────────────────────┘
```

**Pros:**
- Physics grounds the predictions
- ML handles noise and edge cases
- LLM provides natural explanations
- Each component is verifiable

## Training Data Generation

### Phase 1: Physics Simulator Coverage

Build simulators for major automotive systems:

| System | Parameters | Faults | Priority |
|--------|------------|--------|----------|
| **Cooling** | Coolant temp, flow, fan, thermostat | 15+ | ✅ Done |
| **Fuel** | Pressure, trim, injector timing | 20+ | High |
| **Ignition** | Timing, coil output, spark quality | 15+ | High |
| **Charging** | Voltage, current, duty cycle | 10+ | High |
| **Emission** | O2 sensors, cat efficiency, EGR | 25+ | High |
| **Transmission** | Line pressure, slip, solenoids | 30+ | Medium |
| **Braking** | Pressure, ABS activity, pad wear | 15+ | Medium |
| **Steering** | Assist pressure, alignment angles | 10+ | Medium |
| **HVAC** | Pressures, temps, blend door | 20+ | Low |
| **Suspension** | Ride height, damping, alignment | 15+ | Low |

### Phase 2: Scenario Generation

For each system, generate scenarios covering:

```python
scenarios = []
for vehicle in VEHICLE_DATABASE:  # ~500 common vehicles
    for ambient_temp in range(-20, 45, 5):  # Temperature range
        for altitude in [0, 1500, 3000]:  # Altitude effects
            for load_profile in LOAD_PROFILES:  # Idle, city, highway, towing
                for fault_combo in FAULT_COMBINATIONS:  # Single and multiple faults
                    for severity in [0.25, 0.5, 0.75, 1.0]:  # Fault severity
                        scenario = generate_scenario(
                            vehicle, ambient_temp, altitude, 
                            load_profile, fault_combo, severity
                        )
                        scenarios.append(scenario)

# Estimated: 500 × 13 × 3 × 5 × 100 × 4 = 39,000,000 scenarios
```

### Phase 3: Training Sample Format

```json
{
    "id": "scenario_12345678",
    "vehicle": {
        "year": 2019,
        "make": "Toyota",
        "model": "Camry",
        "engine": "2.5L 4-cyl"
    },
    "operating_conditions": {
        "rpm": 2500,
        "load_fraction": 0.45,
        "ambient_temp_c": 32,
        "vehicle_speed_kph": 80,
        "altitude_m": 500,
        "ac_on": true
    },
    "sensor_readings": {
        "coolant_temp_c": 118.5,
        "oil_temp_c": 125.2,
        "intake_air_temp_c": 45.3,
        "fuel_pressure_kpa": 350,
        "map_kpa": 85,
        "maf_gs": 22.5,
        "short_term_fuel_trim": 8.5,
        "long_term_fuel_trim": 12.3,
        "o2_bank1_mv": 450,
        "timing_advance_deg": 18
    },
    "dtcs_present": ["P0128", "P0171"],
    "symptoms_reported": [
        "slow_warmup",
        "rough_idle_cold",
        "poor_fuel_economy"
    ],
    "ground_truth": {
        "faults": [
            {"id": "thermostat_stuck_open", "severity": 0.8},
            {"id": "maf_sensor_contaminated", "severity": 0.3}
        ],
        "root_cause": "thermostat_stuck_open",
        "contributing_factors": ["maf_sensor_contaminated"]
    },
    "physics_trace": {
        "cooling_system": {
            "expected_temp_c": 90,
            "actual_temp_c": 72,
            "heat_generated_kw": 25.3,
            "heat_rejected_kw": 31.2,
            "thermostat_position": 1.0,
            "explanation": "Thermostat fully open at 72°C indicates stuck open condition"
        },
        "fuel_system": {
            "expected_fuel_trim": 0,
            "actual_fuel_trim": 10.4,
            "explanation": "Positive trim indicates lean condition, consistent with MAF underreading"
        }
    }
}
```

## Model Training

### LoRA Fine-Tuning Configuration

```python
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM

# Base model
base_model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-8B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

# LoRA configuration
lora_config = LoraConfig(
    r=64,                          # Rank
    lora_alpha=128,                # Scaling
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# Apply LoRA
model = get_peft_model(base_model, lora_config)
print(f"Trainable params: {model.print_trainable_parameters()}")
# Expected: ~100M trainable out of 8B total
```

### Training Prompt Format

```
<|system|>
You are an automotive diagnostic AI trained on physics-based vehicle models.
Given sensor readings and symptoms, identify the root cause by reasoning
through the physics of each system.

<|user|>
Vehicle: 2019 Toyota Camry 2.5L
Operating: 2500 RPM, 45% load, 32°C ambient, highway driving

Sensor Readings:
- Coolant temp: 118.5°C (expected: 90°C) ⚠️ HIGH
- Fuel trim (LTFT): +12.3% (expected: ±5%) ⚠️ LEAN
- MAP: 85 kPa (expected: 82 kPa) ✓ NORMAL
- O2 Bank 1: 450mV (expected: 450mV) ✓ NORMAL

DTCs: P0128 (Coolant Thermostat Below Threshold), P0171 (System Too Lean Bank 1)
Symptoms: Slow warmup, rough idle when cold, poor fuel economy

Diagnose the root cause.

<|assistant|>
## Physics Analysis

**Cooling System:**
The coolant temperature of 118.5°C is significantly elevated. However, DTC P0128 
indicates "thermostat below threshold" - this code sets when the engine doesn't 
reach operating temperature quickly enough, suggesting the thermostat was stuck 
OPEN during warmup, causing P0128 to set. The current high temperature suggests
a different issue may be developing, or the system is now overcompensating.

Wait - let me reconsider. P0128 sets during warmup when temp doesn't rise fast 
enough. Current elevated temp with P0128 history suggests:
1. Thermostat stuck open → slow warmup → P0128
2. Now thermostat may be intermittent or engine is heat-soaked

**Fuel System:**
LTFT of +12.3% indicates the engine is running lean. Combined with:
- Normal MAP reading (rules out vacuum leak)
- Normal O2 reading (closed-loop working)
- Elevated LTFT persisting

This pattern suggests the MAF sensor is under-reading airflow, causing the ECU
to add fuel via positive trim.

## Root Cause Diagnosis

**Primary: Thermostat stuck open (80% confidence)**
- Explains P0128 directly
- Causes extended warmup time
- Contributes to poor fuel economy (engine runs rich when cold longer)
- Explains rough cold idle (fuel maps optimized for faster warmup)

**Contributing: MAF sensor contamination (60% confidence)**
- Explains P0171 and elevated fuel trims
- Contaminated hot wire reads low → ECU adds fuel
- Worsens fuel economy

## Confirming Tests

1. **Thermostat:** With cold engine, start and monitor warmup curve. Should reach 
   90°C within 5-7 minutes of driving. If takes >15 minutes, thermostat is stuck open.

2. **MAF:** Compare calculated load vs actual load. If MAF is contaminated, 
   calculated load will be lower than expected for given throttle position.

## Repair Priority

1. Replace thermostat (~$25 part, 1 hour labor)
2. Clean or replace MAF sensor (~$15 cleaner or $100 sensor)
3. Clear codes and verify repair
```

### Physics-Informed Loss Function

Standard cross-entropy loss plus physics consistency penalties:

```python
def physics_informed_loss(predictions, targets, physics_constraints):
    """
    Loss function that penalizes physically impossible predictions.
    """
    # Standard classification loss
    ce_loss = F.cross_entropy(predictions['fault_probs'], targets['fault_labels'])
    
    # Physics consistency penalties
    physics_loss = 0.0
    
    # Energy conservation: heat_in ≈ heat_out at steady state
    energy_balance = predictions['heat_generated'] - predictions['heat_rejected']
    physics_loss += F.mse_loss(energy_balance, torch.zeros_like(energy_balance))
    
    # Temperature bounds: coolant can't exceed 150°C before boiling over
    temp_violation = F.relu(predictions['coolant_temp'] - 150)
    physics_loss += temp_violation.mean()
    
    # Monotonicity: higher load → higher heat generation
    if 'load_sequence' in physics_constraints:
        heat_diff = predictions['heat_generated'][1:] - predictions['heat_generated'][:-1]
        load_diff = physics_constraints['load_sequence'][1:] - physics_constraints['load_sequence'][:-1]
        monotonicity_violation = F.relu(-heat_diff * load_diff.sign())
        physics_loss += monotonicity_violation.mean()
    
    # Causality: fault must precede symptom
    # (encoded in training data structure)
    
    total_loss = ce_loss + 0.1 * physics_loss
    return total_loss
```

## Inference Pipeline

```python
class MLPhysicsDiagnostics:
    """
    ML-based diagnostic engine with physics grounding.
    """
    
    def __init__(self, model_path: str):
        self.physics_sim = CoolingSystemModel()  # Deterministic physics
        self.ml_model = load_lora_model(model_path)  # LoRA-tuned LLM
        self.tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B-Instruct")
    
    def diagnose(
        self,
        vehicle: VehicleInfo,
        sensor_readings: Dict[str, float],
        dtcs: List[str],
        symptoms: List[str]
    ) -> DiagnosticResult:
        """
        Run full diagnostic pipeline.
        """
        # Step 1: Physics simulation for expected values
        expected_state = self.physics_sim.simulate_steady_state(
            rpm=sensor_readings['rpm'],
            load_fraction=sensor_readings['load'],
            ambient_temp_c=sensor_readings['ambient_temp']
        )
        
        # Step 2: Compute residuals
        residuals = self._compute_residuals(sensor_readings, expected_state)
        
        # Step 3: Format prompt with physics context
        prompt = self._format_diagnostic_prompt(
            vehicle, sensor_readings, expected_state, residuals, dtcs, symptoms
        )
        
        # Step 4: Run ML inference
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.ml_model.generate(
            **inputs,
            max_new_tokens=1024,
            temperature=0.3,  # Low temperature for consistency
            do_sample=True
        )
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Step 5: Parse structured output
        result = self._parse_diagnostic_response(response)
        
        return result
    
    def _compute_residuals(self, actual: Dict, expected: CoolingSystemState) -> Dict:
        """Compute difference between actual and physics-predicted values."""
        return {
            'coolant_temp_residual': actual.get('coolant_temp', 0) - expected.coolant_temp_engine,
            'expected_coolant_temp': expected.coolant_temp_engine,
            'heat_balance': expected.heat_generated - expected.heat_rejected,
            'thermostat_position': expected.thermostat_flow_fraction,
        }
```

## Evaluation Metrics

### Accuracy Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Top-1 Accuracy** | >85% | Correct root cause in first prediction |
| **Top-3 Accuracy** | >95% | Correct root cause in top 3 predictions |
| **Severity RMSE** | <0.15 | Fault severity estimation error |
| **False Positive Rate** | <5% | Healthy system misdiagnosed |
| **Multiple Fault Detection** | >70% | Correctly identifies 2+ simultaneous faults |

### Physics Consistency Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Energy Balance Error** | <5% | Heat in ≈ heat out at steady state |
| **Temperature Bound Violations** | 0% | No impossible temperature predictions |
| **Causal Consistency** | >99% | Fault precedes symptom in explanation |

### Explainability Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| **Physics Trace Accuracy** | >90% | Correct equations cited |
| **Reasoning Chain Quality** | 4.5/5 | Human evaluation of explanation |
| **Actionability Score** | 4.5/5 | Are next steps clear and correct? |

## Implementation Phases

### Phase 1: Foundation (Weeks 1-4)

- [ ] Expand physics simulators to cover fuel, ignition, charging systems
- [ ] Build synthetic data generation pipeline
- [ ] Generate initial dataset (1M samples)
- [ ] Set up training infrastructure (GPU cluster or cloud)

### Phase 2: Model Training (Weeks 5-8)

- [ ] Fine-tune LoRA adapter on synthetic data
- [ ] Implement physics-informed loss function
- [ ] Train fault classifier head
- [ ] Evaluate on held-out test set

### Phase 3: Integration (Weeks 9-12)

- [ ] Build inference pipeline
- [ ] Integrate with Open WebUI tool
- [ ] Add real-time physics simulation
- [ ] Implement confidence calibration

### Phase 4: Validation (Weeks 13-16)

- [ ] Test on real vehicle data (if available)
- [ ] A/B test against deterministic physics model
- [ ] Collect technician feedback
- [ ] Iterate on failure cases

## Hardware Requirements

### Training

| Component | Specification |
|-----------|---------------|
| GPU | 4× NVIDIA A100 80GB or 8× RTX 4090 |
| RAM | 256GB+ |
| Storage | 2TB NVMe SSD |
| Training time | ~48 hours for full LoRA fine-tune |

### Inference

| Component | Specification |
|-----------|---------------|
| GPU | 1× RTX 4090 or A100 40GB |
| RAM | 32GB+ |
| Latency | <2 seconds for full diagnosis |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model hallucinates physics | High | Physics-informed loss + validation checks |
| Overfits to synthetic data | Medium | Diverse scenario generation + real data validation |
| Fails on novel fault combinations | Medium | Ensemble with deterministic physics model |
| Slow inference | Low | Quantization + optimized serving |
| Explainability insufficient | Medium | Require physics trace in every output |

## Success Criteria

The ML physics model is successful when it:

1. **Matches or exceeds** deterministic physics model accuracy on known faults
2. **Generalizes better** to unseen fault combinations
3. **Provides explanations** that technicians find helpful and accurate
4. **Runs fast enough** for real-time diagnostic use (<2 seconds)
5. **Fails gracefully** - knows when it doesn't know

## Comparison: Current vs ML Approach

| Aspect | Current (Deterministic) | ML Physics Model |
|--------|------------------------|------------------|
| Accuracy on known faults | High | High |
| Novel fault combinations | Limited | Better generalization |
| Multiple systems | Separate models | Unified model |
| Explanation quality | Perfect (equations) | Good (learned patterns) |
| Development effort | High per system | High upfront, low incremental |
| Maintenance | Manual updates | Retrain on new data |
| Confidence calibration | Hard | Natural with ML |

## Conclusion

The ML physics approach offers significant advantages for scaling to many vehicle systems and handling complex multi-fault scenarios. By training on physics-simulator-generated data, we get the best of both worlds:

- **Physics grounding** prevents impossible predictions
- **ML flexibility** handles noise and edge cases
- **Synthetic data** eliminates the cold-start problem
- **LoRA efficiency** enables deployment on reasonable hardware

The key insight remains: the model must **think like the system itself** - whether through explicit physics equations or learned physics relationships, the diagnostic reasoning must follow causal chains from root cause to observable symptoms.
