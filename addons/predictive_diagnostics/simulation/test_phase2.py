#!/usr/bin/env python3
"""
Phase 2 Validation: Physics Simulation

Tests that the simulation module correctly generates time-series
data showing how failures evolve over time.

Expected behavior for thermostat_stuck_open:
- Coolant temp stays low (~70°C vs normal ~90°C)
- STFT goes positive (rich mixture compensation)
- P0128 triggers after warmup period
"""

import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.simulation import (
    SimulationEngine,
    SimulationConfig,
    CoolingSystemSimulator,
    ThermalModel,
    visualize_simulation,
)
from addons.predictive_diagnostics.simulation.engine import OperatingCondition


def test_thermostat_stuck_open():
    """Verify thermostat stuck open produces expected behavior."""
    print("\n" + "="*60)
    print("TEST: Thermostat Stuck Open")
    print("="*60)
    
    # Create simulation engine
    engine = SimulationEngine()
    engine.register_simulator("cooling", CoolingSystemSimulator())
    
    # Configure for thermostat stuck open
    # Use highway driving on a cold day - this is where stuck open matters most
    config = SimulationConfig(
        duration_seconds=300.0,  # 5 minutes
        time_step=1.0,
        operating_condition=OperatingCondition.HIGHWAY,  # High airflow
        ambient_temp_c=5.0,  # Cold day
        add_noise=False,  # Clean signal for validation
        failure_id="thermostat_stuck_open",
        failure_severity=1.0,
        failure_onset_time=0.0,
    )
    
    result = engine.run("cooling", config)
    
    # Visualize
    print(visualize_simulation(result))
    
    # Check results
    temps = result.get_variable_series("coolant_temp")
    final_temp = temps[-1]
    max_temp = max(temps)
    
    print(f"\nResults:")
    print(f"  Final coolant temp: {final_temp:.1f}°C")
    print(f"  Max coolant temp: {max_temp:.1f}°C")
    print(f"  DTCs triggered: {result.triggered_dtcs}")
    
    # Validate physics
    # With stuck open thermostat on highway in cold weather, equilibrium should be
    # significantly lower than normal operating temp (90°C)
    assert max_temp < 85, f"Temp should be lower than normal with open thermostat, got {max_temp}°C"
    assert "P0128" in result.triggered_dtcs, "Should trigger P0128 (coolant temp below threshold)"
    
    print("\n✓ Thermostat stuck open simulation PASSED")


def test_normal_operation():
    """Verify normal operation reaches proper operating temperature."""
    print("\n" + "="*60)
    print("TEST: Normal Operation")
    print("="*60)
    
    engine = SimulationEngine()
    engine.register_simulator("cooling", CoolingSystemSimulator())
    
    config = SimulationConfig(
        duration_seconds=300.0,
        time_step=1.0,
        operating_condition=OperatingCondition.CITY_DRIVING,
        ambient_temp_c=20.0,
        add_noise=False,
        failure_id=None,  # No failure
    )
    
    result = engine.run("cooling", config)
    
    print(visualize_simulation(result))
    
    temps = result.get_variable_series("coolant_temp")
    final_temp = temps[-1]
    
    print(f"\nResults:")
    print(f"  Final coolant temp: {final_temp:.1f}°C")
    print(f"  DTCs triggered: {result.triggered_dtcs or 'None'}")
    
    # Should reach and maintain ~90°C
    assert 85 < final_temp < 100, f"Normal temp should be 85-100°C, got {final_temp}°C"
    assert not result.triggered_dtcs, f"Should have no DTCs, got {result.triggered_dtcs}"
    
    print("\n✓ Normal operation simulation PASSED")


def test_radiator_blocked():
    """Verify blocked radiator causes overheating."""
    print("\n" + "="*60)
    print("TEST: Radiator Blocked")
    print("="*60)
    
    engine = SimulationEngine()
    engine.register_simulator("cooling", CoolingSystemSimulator())
    
    config = SimulationConfig(
        duration_seconds=600.0,  # 10 minutes - longer to reach overheat
        time_step=1.0,
        operating_condition=OperatingCondition.HEAVY_LOAD,  # Maximum heat generation
        ambient_temp_c=35.0,  # Hot day
        add_noise=False,
        failure_id="radiator_blocked",
        failure_severity=0.9,  # 90% blocked
    )
    
    result = engine.run("cooling", config)
    
    print(visualize_simulation(result))
    
    temps = result.get_variable_series("coolant_temp")
    max_temp = max(temps)
    
    print(f"\nResults:")
    print(f"  Max coolant temp: {max_temp:.1f}°C")
    print(f"  DTCs triggered: {result.triggered_dtcs}")
    
    # Should overheat
    assert max_temp > 110, f"Should overheat with blocked radiator, got {max_temp}°C"
    assert "P0217" in result.triggered_dtcs, "Should trigger P0217 (engine overheat)"
    
    print("\n✓ Radiator blocked simulation PASSED")


def test_data_generation():
    """Test training data generation."""
    print("\n" + "="*60)
    print("TEST: Training Data Generation")
    print("="*60)
    
    from addons.predictive_diagnostics.simulation import (
        TrainingDataGenerator,
        DataGeneratorConfig,
    )
    
    config = DataGeneratorConfig(
        samples_per_failure=2,  # Small for testing
        normal_samples=2,
    )
    
    generator = TrainingDataGenerator(config)
    samples = generator.generate_dataset_for_system("cooling")
    
    print(f"\nGenerated {len(samples)} training samples")
    
    # Check sample structure
    sample = samples[0]
    required_keys = ["time_series", "label", "is_failure", "operating_condition", "ambient_temp"]
    for key in required_keys:
        assert key in sample, f"Missing key: {key}"
    
    print(f"Sample keys: {list(sample.keys())}")
    print(f"Time series length: {len(sample['time_series'])}")
    print(f"Label: {sample['label']}")
    
    # Check we have both failures and normal
    labels = set(s["label"] for s in samples)
    print(f"Labels in dataset: {labels}")
    
    assert "normal" in labels, "Should have normal samples"
    assert len(labels) > 1, "Should have multiple failure types"
    
    print("\n✓ Training data generation PASSED")


def main():
    """Run all Phase 2 validation tests."""
    print("\n" + "#"*60)
    print("# PHASE 2 VALIDATION: Physics Simulation")
    print("#"*60)
    
    try:
        test_normal_operation()
        test_thermostat_stuck_open()
        test_radiator_blocked()
        test_data_generation()
        
        print("\n" + "="*60)
        print("ALL PHASE 2 TESTS PASSED!")
        print("="*60)
        print("\nPhase 2 is complete. Ready for Phase 3: ML Model")
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
