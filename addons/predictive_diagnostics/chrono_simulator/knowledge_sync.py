"""
Knowledge Sync Layer

Bridges the gap between:
- knowledge/ FailureMode definitions (200+ failures with PID effects)
- chrono_simulator/ FailureSimulation mappings (physics simulation)

This module:
1. Maps knowledge IDs to simulator IDs
2. Auto-generates FailureSimulations from knowledge PIDEffects
3. Validates simulated data matches knowledge expectations
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.failures import get_all_failure_modes
from knowledge.registry import get_failure_by_id
from knowledge.base import FailureMode, PIDEffect


# =============================================================================
# ID MAPPING: knowledge ID <-> simulator ID
# =============================================================================

# Knowledge uses: "fuel_pump_weak", "thermostat_stuck_closed"
# Simulator uses: "fuel.weak_fuel_pump", "cooling.thermostat_stuck_closed"

def knowledge_to_sim_id(knowledge_id: str) -> str:
    """Convert knowledge ID to simulator ID format."""
    # Map common patterns
    mappings = {
        # Fuel system
        "fuel_pump_weak": "fuel.weak_fuel_pump",
        "fuel_injector_clogged": "fuel.clogged_injector",
        "vacuum_leak": "fuel.vacuum_leak",
        "fuel_pressure_regulator_stuck": "fuel.pressure_regulator_stuck",
        "fuel_filter_clogged": "fuel.filter_clogged",
        
        # Cooling system
        "thermostat_stuck_open": "cooling.thermostat_stuck_open",
        "thermostat_stuck_closed": "cooling.thermostat_stuck_closed",
        "water_pump_failure": "cooling.water_pump_failure",
        "coolant_leak": "cooling.coolant_leak",
        "radiator_blocked_internal": "cooling.radiator_blocked",
        
        # Ignition system
        "spark_plug_fouled": "ignition.weak_spark",
        "ignition_coil_weak": "ignition.weak_spark",
        "misfire_cylinder": "ignition.misfire_cylinder",
        
        # Tires
        "tire_low_pressure": "tires.low_pressure",
        "tire_worn": "tires.worn_tires",
        
        # Brakes
        "brake_pad_worn": "brakes.brake_fade",
        "brake_fluid_low": "brakes.brake_fade",
        
        # Transmission
        "transmission_slipping": "transmission.slipping",
        "torque_converter_shudder": "transmission.slipping",
    }
    
    if knowledge_id in mappings:
        return mappings[knowledge_id]
    
    # Try to auto-generate: "fuel_pump_weak" -> "fuel.pump_weak"
    # Split on first underscore as system
    parts = knowledge_id.split("_", 1)
    if len(parts) == 2:
        system = parts[0]
        rest = parts[1]
        return f"{system}.{rest}"
    
    return knowledge_id


def sim_to_knowledge_id(sim_id: str) -> str:
    """Convert simulator ID to knowledge ID format."""
    # Reverse mapping
    reverse_mappings = {v: k for k, v in {
        "fuel_pump_weak": "fuel.weak_fuel_pump",
        "fuel_injector_clogged": "fuel.clogged_injector",
        "vacuum_leak": "fuel.vacuum_leak",
        "thermostat_stuck_open": "cooling.thermostat_stuck_open",
        "thermostat_stuck_closed": "cooling.thermostat_stuck_closed",
        "spark_plug_fouled": "ignition.weak_spark",
        "misfire_cylinder": "ignition.misfire_cylinder",
        "tire_low_pressure": "tires.low_pressure",
        "tire_worn": "tires.worn_tires",
        "brake_pad_worn": "brakes.brake_fade",
        "transmission_slipping": "transmission.slipping",
    }.items()}
    
    if sim_id in reverse_mappings:
        return reverse_mappings[sim_id]
    
    # Auto-convert: "fuel.weak_fuel_pump" -> "fuel_weak_fuel_pump"
    return sim_id.replace(".", "_")


# =============================================================================
# PID EFFECT PARSING
# =============================================================================

@dataclass
class ParsedPIDEffect:
    """Parsed PID effect with numeric values."""
    pid_name: str
    effect: str  # "high", "low", "erratic", "positive", "negative"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    unit: str = ""


def parse_pid_effect(effect: PIDEffect) -> ParsedPIDEffect:
    """Parse PIDEffect into numeric ranges for simulation."""
    parsed = ParsedPIDEffect(
        pid_name=normalize_pid_name(effect.pid_name),
        effect=effect.effect.lower(),
    )
    
    if not effect.typical_value:
        return parsed
    
    # Parse typical_value patterns:
    # "+10 to +25%"  -> positive 10-25
    # "<35 psi"      -> low, max=35
    # ">220°F"       -> high, min=220
    # "0-5%"         -> 0-5
    
    val = effect.typical_value
    
    # Range pattern: "+10 to +25%" or "10-25%"
    range_match = re.search(r'([+-]?\d+\.?\d*)\s*(?:to|-)\s*([+-]?\d+\.?\d*)', val)
    if range_match:
        parsed.min_value = float(range_match.group(1).replace('+', ''))
        parsed.max_value = float(range_match.group(2).replace('+', ''))
        return parsed
    
    # Less than: "<35"
    lt_match = re.search(r'<\s*(\d+\.?\d*)', val)
    if lt_match:
        parsed.max_value = float(lt_match.group(1))
        return parsed
    
    # Greater than: ">220"
    gt_match = re.search(r'>\s*(\d+\.?\d*)', val)
    if gt_match:
        parsed.min_value = float(gt_match.group(1))
        return parsed
    
    # Single value with sign: "+15%"
    single_match = re.search(r'([+-]?\d+\.?\d*)', val)
    if single_match:
        v = float(single_match.group(1).replace('+', ''))
        parsed.min_value = v * 0.8  # 20% tolerance
        parsed.max_value = v * 1.2
        return parsed
    
    return parsed


def normalize_pid_name(name: str) -> str:
    """Normalize PID name to match simulator field names."""
    mappings = {
        "fuel_pressure": "fuel_pressure",
        "ltft": "ltft_b1",
        "stft": "stft_b1",
        "coolant_temp": "coolant_temp",
        "engine_coolant_temp": "coolant_temp",
        "rpm": "rpm",
        "engine_rpm": "rpm",
        "map": "map",
        "maf": "maf",
        "throttle": "throttle_pct",
        "engine_load": "engine_load",
        "misfire_count": "misfire_count",
    }
    
    normalized = name.lower().replace(" ", "_")
    return mappings.get(normalized, normalized)


# =============================================================================
# AUTO-GENERATE SIMULATOR CONFIGS FROM KNOWLEDGE
# =============================================================================

def generate_sensor_biases(failure: FailureMode) -> Dict[str, float]:
    """Generate sensor_biases dict from knowledge PIDEffects."""
    biases = {}
    
    for pid_effect in failure.pid_effects:
        parsed = parse_pid_effect(pid_effect)
        
        # Skip if we couldn't parse numeric values
        if parsed.min_value is None and parsed.max_value is None:
            continue
        
        # Calculate bias based on effect type
        if parsed.effect in ("high", "positive"):
            # Use midpoint of range, or min if only min given
            if parsed.min_value and parsed.max_value:
                biases[parsed.pid_name] = (parsed.min_value + parsed.max_value) / 2
            elif parsed.min_value:
                biases[parsed.pid_name] = parsed.min_value
        
        elif parsed.effect in ("low", "negative"):
            # Negative bias
            if parsed.min_value and parsed.max_value:
                biases[parsed.pid_name] = -(parsed.min_value + parsed.max_value) / 2
            elif parsed.max_value:
                biases[parsed.pid_name] = -parsed.max_value
    
    return biases


def get_knowledge_failures_with_pid_effects() -> List[FailureMode]:
    """Get all knowledge failures that have defined PID effects."""
    all_failures = get_all_failure_modes()
    return [f for f in all_failures if f.pid_effects]


# =============================================================================
# VALIDATION: Check simulated data matches knowledge
# =============================================================================

@dataclass
class ValidationResult:
    """Result of validating simulated data against knowledge."""
    failure_id: str
    pid_name: str
    expected: str
    actual: float
    matches: bool
    message: str


def validate_simulation_against_knowledge(
    sim_failure_id: str, 
    simulated_data: Dict[str, float]
) -> List[ValidationResult]:
    """
    Check if simulated PID values match knowledge base expectations.
    
    Args:
        sim_failure_id: Simulator failure ID (e.g., "fuel.vacuum_leak")
        simulated_data: Dict of PID name -> average value from simulation
    
    Returns:
        List of validation results for each PID effect
    """
    results = []
    
    # Get knowledge failure
    knowledge_id = sim_to_knowledge_id(sim_failure_id)
    try:
        failure = get_failure_by_id(knowledge_id)
    except (KeyError, ValueError):
        return [ValidationResult(
            failure_id=sim_failure_id,
            pid_name="",
            expected="",
            actual=0,
            matches=False,
            message=f"No knowledge mapping for {sim_failure_id}"
        )]
    
    if not failure:
        return results
    
    # Check each PID effect
    for pid_effect in failure.pid_effects:
        parsed = parse_pid_effect(pid_effect)
        sim_value = simulated_data.get(parsed.pid_name)
        
        if sim_value is None:
            results.append(ValidationResult(
                failure_id=sim_failure_id,
                pid_name=parsed.pid_name,
                expected=pid_effect.typical_value or pid_effect.effect,
                actual=0,
                matches=False,
                message=f"PID {parsed.pid_name} not in simulated data"
            ))
            continue
        
        # Check if value matches expectation
        matches = True
        
        if parsed.min_value is not None and sim_value < parsed.min_value * 0.8:
            matches = False
        if parsed.max_value is not None and sim_value > parsed.max_value * 1.2:
            matches = False
        
        results.append(ValidationResult(
            failure_id=sim_failure_id,
            pid_name=parsed.pid_name,
            expected=pid_effect.typical_value or pid_effect.effect,
            actual=sim_value,
            matches=matches,
            message="OK" if matches else f"Value {sim_value} outside expected range"
        ))
    
    return results


# =============================================================================
# COVERAGE REPORT
# =============================================================================

def coverage_report():
    """Show which knowledge failures have simulator mappings."""
    from fault_injector import FAILURE_SIMULATIONS
    
    knowledge_failures = get_all_failure_modes()
    sim_ids = set(FAILURE_SIMULATIONS.keys())
    
    print("=" * 70)
    print("KNOWLEDGE -> SIMULATOR COVERAGE REPORT")
    print("=" * 70)
    
    covered = []
    missing = []
    
    for failure in knowledge_failures:
        sim_id = knowledge_to_sim_id(failure.id)
        if sim_id in sim_ids:
            covered.append((failure.id, sim_id))
        else:
            missing.append(failure.id)
    
    print(f"\n✅ COVERED ({len(covered)} failures):")
    for k_id, s_id in covered[:20]:
        print(f"  {k_id} -> {s_id}")
    if len(covered) > 20:
        print(f"  ... and {len(covered) - 20} more")
    
    print(f"\n❌ MISSING SIMULATOR ({len(missing)} failures):")
    for k_id in missing[:30]:
        print(f"  {k_id}")
    if len(missing) > 30:
        print(f"  ... and {len(missing) - 30} more")
    
    print(f"\n" + "=" * 70)
    print(f"SUMMARY: {len(covered)}/{len(knowledge_failures)} failures covered "
          f"({100*len(covered)/len(knowledge_failures):.1f}%)")
    print("=" * 70)
    
    # Show knowledge failures with good PID effects (candidates for simulation)
    print("\n🎯 HIGH-VALUE CANDIDATES (have PID effects defined):")
    candidates = [f for f in knowledge_failures 
                  if f.pid_effects and f.id in missing]
    for failure in candidates[:15]:
        pids = [p.pid_name for p in failure.pid_effects]
        print(f"  {failure.id}: {', '.join(pids)}")
    if len(candidates) > 15:
        print(f"  ... and {len(candidates) - 15} more")


# =============================================================================
# AUTO-GENERATE FAILURE SIMULATIONS FROM KNOWLEDGE
# =============================================================================

def generate_failure_simulation_code(failure: FailureMode) -> str:
    """Generate Python code for a FailureSimulation from knowledge FailureMode."""
    sim_id = knowledge_to_sim_id(failure.id)
    biases = generate_sensor_biases(failure)
    
    # Build sensor_biases dict
    biases_str = ""
    if biases:
        biases_items = [f'        "{k}": {v},' for k, v in biases.items()]
        biases_str = "sensor_biases={\n" + "\n".join(biases_items) + "\n    },"
    
    code = f'''
register_simulation(FailureSimulation(
    failure_mode_id="{sim_id}",
    failure_mode_name="{failure.name}",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    {biases_str}
    expected_patterns={{
        # From knowledge: {[p.pid_name + "=" + p.effect for p in failure.pid_effects]}
    }},
    severity_range=(0.1, 0.9),
    n_variations=50,
))
'''
    return code.strip()


def generate_all_missing_simulations():
    """Generate code for all knowledge failures missing simulations."""
    from fault_injector import FAILURE_SIMULATIONS
    
    knowledge_failures = get_all_failure_modes()
    sim_ids = set(FAILURE_SIMULATIONS.keys())
    
    # Get failures with PID effects that are missing simulations
    candidates = [
        f for f in knowledge_failures 
        if f.pid_effects and knowledge_to_sim_id(f.id) not in sim_ids
    ]
    
    print(f"# Auto-generated FailureSimulations from knowledge base")
    print(f"# {len(candidates)} failures with PID effects need simulations\n")
    
    for failure in candidates:
        print(generate_failure_simulation_code(failure))
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--generate":
        generate_all_missing_simulations()
    else:
        coverage_report()
