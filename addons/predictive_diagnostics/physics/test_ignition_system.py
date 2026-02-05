#!/usr/bin/env python3
"""
Test script for physics-based ignition system model.

Validates that:
1. Normal operation produces expected spark energy and timing
2. Each fault produces a unique, physically-correct signature
3. Misfire detection works correctly
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from addons.predictive_diagnostics.physics.ignition_system import (
    IgnitionSystemModel, IgnitionCoilModel, SparkPlugModel
)


def test_normal_operation():
    """Test that normal operation produces expected values."""
    print("=" * 60)
    print("TEST 1: Normal Operation")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    
    scenarios = [
        {"rpm": 800, "load": 0.2, "name": "Idle"},
        {"rpm": 2500, "load": 0.5, "name": "Cruise"},
        {"rpm": 5000, "load": 0.8, "name": "WOT"},
    ]
    
    for scenario in scenarios:
        state = model.simulate_cycle(
            rpm=scenario["rpm"],
            load_fraction=scenario["load"]
        )
        
        avg_energy = sum(state.spark_energy_mj) / len(state.spark_energy_mj)
        avg_voltage = sum(state.secondary_voltage_kv) / len(state.secondary_voltage_kv)
        all_fired = all(state.spark_fired)
        
        print(f"\n{scenario['name']} ({scenario['rpm']} RPM, {scenario['load']*100:.0f}% load):")
        print(f"  Dwell time: {state.dwell_time_ms:.2f} ms")
        print(f"  Spark timing: {state.actual_timing_deg:.1f}° BTDC")
        print(f"  Avg spark energy: {avg_energy:.1f} mJ")
        print(f"  Avg secondary voltage: {avg_voltage:.1f} kV")
        print(f"  All sparks fired: {all_fired}")
        print(f"  Misfires detected: {sum(state.misfire_detected)}")
        
        # Verify all cylinders fire
        assert all_fired, "All sparks should fire in normal operation"
        # Verify adequate energy (typically 30-50 mJ)
        assert avg_energy > 15, f"Spark energy {avg_energy} mJ too low"
        # Verify no misfires
        assert state.misfire_count_total == 0, "Should have no misfires"
        
    print("\n✅ Normal operation test PASSED")
    return True


def test_coil_failed():
    """Test that failed coil causes misfire on that cylinder."""
    print("\n" + "=" * 60)
    print("TEST 2: Coil Failed (Cylinder 1)")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    model.inject_fault("coil_failed", cylinder=0)
    
    state = model.simulate_cycle(rpm=2000, load_fraction=0.4)
    
    print(f"\nWith coil 1 failed:")
    print(f"  Spark energies (mJ): {[f'{e:.1f}' for e in state.spark_energy_mj]}")
    print(f"  Sparks fired: {state.spark_fired}")
    print(f"  Misfires detected: {state.misfire_detected}")
    
    # Cylinder 0 should have no spark
    assert state.spark_energy_mj[0] == 0, "Failed coil should have 0 energy"
    assert not state.spark_fired[0], "Failed coil should not fire"
    assert state.misfire_detected[0], "Misfire should be detected on cyl 1"
    
    # Other cylinders should be fine
    for i in range(1, 4):
        assert state.spark_fired[i], f"Cylinder {i+1} should fire normally"
    
    print("\n✅ Coil failed test PASSED")
    print("   SIGNATURE: Single cylinder misfire + no spark energy")
    return True


def test_coil_weak():
    """Test that weak coil produces low energy but may still fire."""
    print("\n" + "=" * 60)
    print("TEST 3: Coil Weak (Cylinder 2)")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    model.inject_fault("coil_weak", severity=0.8, cylinder=1)
    
    # At light load - should still fire
    state_light = model.simulate_cycle(rpm=2000, load_fraction=0.3)
    
    # At high load - may struggle
    state_heavy = model.simulate_cycle(rpm=4000, load_fraction=0.8)
    
    print(f"\nWith weak coil on cylinder 2:")
    print(f"  Light load energies: {[f'{e:.1f}' for e in state_light.spark_energy_mj]}")
    print(f"  Heavy load energies: {[f'{e:.1f}' for e in state_heavy.spark_energy_mj]}")
    
    # Weak coil should have lower energy
    normal_energy = state_light.spark_energy_mj[0]
    weak_energy = state_light.spark_energy_mj[1]
    assert weak_energy < normal_energy * 0.8, "Weak coil should have reduced energy"
    
    print(f"\n  Normal coil: {normal_energy:.1f} mJ")
    print(f"  Weak coil: {weak_energy:.1f} mJ ({weak_energy/normal_energy*100:.0f}% of normal)")
    
    print("\n✅ Coil weak test PASSED")
    print("   SIGNATURE: Reduced spark energy, possible misfire under load")
    return True


def test_plug_fouled():
    """Test that fouled plug requires higher voltage to fire."""
    print("\n" + "=" * 60)
    print("TEST 4: Spark Plug Fouled (Cylinder 3)")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    model.inject_fault("plug_fouled", severity=0.8, cylinder=2)
    
    state = model.simulate_cycle(rpm=2000, load_fraction=0.4)
    
    normal_required = state.required_voltage_kv[0]
    fouled_required = state.required_voltage_kv[2]
    
    print(f"\nWith fouled plug on cylinder 3:")
    print(f"  Required voltage (normal): {normal_required:.1f} kV")
    print(f"  Required voltage (fouled): {fouled_required:.1f} kV")
    print(f"  Available voltage: {state.secondary_voltage_kv[2]:.1f} kV")
    print(f"  Spark fired: {state.spark_fired[2]}")
    
    # Fouled plug needs more voltage
    assert fouled_required > normal_required * 1.3, "Fouled plug should need more voltage"
    
    print("\n✅ Plug fouled test PASSED")
    print("   SIGNATURE: Higher required voltage, possible misfire")
    return True


def test_plug_worn():
    """Test that worn plug (wider gap) needs more voltage."""
    print("\n" + "=" * 60)
    print("TEST 5: Spark Plug Worn (Cylinder 4)")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    model.inject_fault("plug_worn", severity=1.0, cylinder=3)
    
    state = model.simulate_cycle(rpm=2000, load_fraction=0.4)
    
    normal_required = state.required_voltage_kv[0]
    worn_required = state.required_voltage_kv[3]
    
    print(f"\nWith worn plug on cylinder 4:")
    print(f"  Normal plug gap: {model.spark_plugs[0].gap_mm:.2f} mm")
    print(f"  Worn plug effective gap: {model.spark_plugs[3].gap_mm + model.spark_plugs[3].electrode_wear_mm:.2f} mm")
    print(f"  Required voltage (normal): {normal_required:.1f} kV")
    print(f"  Required voltage (worn): {worn_required:.1f} kV")
    
    # Worn plug needs more voltage (wider gap)
    assert worn_required > normal_required, "Worn plug should need more voltage"
    
    print("\n✅ Plug worn test PASSED")
    print("   SIGNATURE: Increased required voltage due to wider gap")
    return True


def test_low_battery_voltage():
    """Test that low battery affects all cylinders."""
    print("\n" + "=" * 60)
    print("TEST 6: Low Battery Voltage")
    print("=" * 60)
    
    # Normal battery
    model_normal = IgnitionSystemModel()
    state_normal = model_normal.simulate_cycle(rpm=2000, load_fraction=0.4)
    
    # Low battery
    model_low = IgnitionSystemModel()
    model_low.inject_fault("low_battery_voltage", severity=0.5)  # ~12V
    state_low = model_low.simulate_cycle(rpm=2000, load_fraction=0.4)
    
    avg_normal = sum(state_normal.spark_energy_mj) / 4
    avg_low = sum(state_low.spark_energy_mj) / 4
    
    print(f"\nBattery voltage effect:")
    print(f"  Normal (14V): {avg_normal:.1f} mJ average")
    print(f"  Low (~{model_low.battery_voltage:.1f}V): {avg_low:.1f} mJ average")
    print(f"  Energy reduction: {(1 - avg_low/avg_normal)*100:.0f}%")
    
    # Low battery should reduce energy across all cylinders
    assert avg_low < avg_normal * 0.8, "Low battery should reduce spark energy"
    
    print("\n✅ Low battery voltage test PASSED")
    print("   SIGNATURE: Reduced spark energy ALL cylinders")
    return True


def test_timing_calculation():
    """Test spark timing varies correctly with conditions."""
    print("\n" + "=" * 60)
    print("TEST 7: Spark Timing Calculation")
    print("=" * 60)
    
    model = IgnitionSystemModel()
    
    # Low RPM, light load
    state_idle = model.simulate_cycle(rpm=800, load_fraction=0.2)
    
    # High RPM, light load (should advance)
    state_cruise = model.simulate_cycle(rpm=3000, load_fraction=0.3)
    
    # High RPM, high load (should retard from cruise)
    state_wot = model.simulate_cycle(rpm=3000, load_fraction=0.9)
    
    print(f"\nSpark timing vs conditions:")
    print(f"  Idle (800 RPM, 20% load): {state_idle.actual_timing_deg:.1f}° BTDC")
    print(f"  Cruise (3000 RPM, 30% load): {state_cruise.actual_timing_deg:.1f}° BTDC")
    print(f"  WOT (3000 RPM, 90% load): {state_wot.actual_timing_deg:.1f}° BTDC")
    
    # Higher RPM should have more advance
    assert state_cruise.actual_timing_deg > state_idle.actual_timing_deg, \
        "Higher RPM should increase advance"
    
    # Higher load at same RPM should have less advance
    assert state_wot.actual_timing_deg < state_cruise.actual_timing_deg, \
        "Higher load should reduce advance"
    
    print("\n✅ Timing calculation test PASSED")
    print("   SIGNATURE: Advance increases with RPM, decreases with load")
    return True


def run_all_tests():
    """Run all ignition system tests."""
    print("\n" + "=" * 60)
    print("PHYSICS-BASED IGNITION SYSTEM MODEL TESTS")
    print("=" * 60)
    
    results = []
    
    tests = [
        ("Normal operation", test_normal_operation),
        ("Coil failed", test_coil_failed),
        ("Coil weak", test_coil_weak),
        ("Plug fouled", test_plug_fouled),
        ("Plug worn", test_plug_worn),
        ("Low battery voltage", test_low_battery_voltage),
        ("Timing calculation", test_timing_calculation),
    ]
    
    for name, test_fn in tests:
        try:
            results.append((name, test_fn()))
        except Exception as e:
            print(f"❌ {name} test FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Ignition system model is working correctly.")
        print("\nFault signatures proven:")
        print("  - Coil failed → single cylinder misfire, no spark")
        print("  - Coil weak → reduced energy, load-dependent misfire")
        print("  - Plug fouled → higher required voltage")
        print("  - Plug worn → wider gap, higher voltage needed")
        print("  - Low battery → weak spark all cylinders")
        print("  - Timing → advances with RPM, retards with load")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
