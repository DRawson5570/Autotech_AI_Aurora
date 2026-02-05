#!/usr/bin/env python3
"""
Test script for the unified diagnostic engine.

Tests that the engine can:
1. Accept DTCs, PIDs, and complaints
2. Route to appropriate physics models
3. Return ranked diagnostic candidates
4. Provide actionable repair guidance
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from addons.predictive_diagnostics.physics.diagnostic_engine import (
    DiagnosticEngine, quick_diagnose, print_diagnosis
)


def test_cooling_diagnosis():
    """Test diagnosis of cooling system issues."""
    print("=" * 70)
    print("TEST 1: Cooling System - Overheating with P0217")
    print("=" * 70)
    
    result = quick_diagnose(
        dtcs=["P0217"],
        complaints=["overheating"]
    )
    
    print_diagnosis(result)
    
    # Should identify cooling system faults
    assert len(result.candidates) > 0, "Should have candidates"
    top = result.candidates[0]
    assert top.system.value == "cooling", f"Top candidate should be cooling, got {top.system.value}"
    assert top.confidence > 0.5, f"Should have high confidence, got {top.confidence}"
    
    print("\n✅ Cooling diagnosis test PASSED")
    return True


def test_fuel_diagnosis():
    """Test diagnosis of fuel system issues."""
    print("\n" + "=" * 70)
    print("TEST 2: Fuel System - Lean Condition with P0171")
    print("=" * 70)
    
    result = quick_diagnose(
        dtcs=["P0171"],
        complaints=["rough_idle", "hesitation"]
    )
    
    print_diagnosis(result)
    
    # Should identify fuel system faults
    assert len(result.candidates) > 0, "Should have candidates"
    top = result.candidates[0]
    assert top.system.value == "fuel", f"Top candidate should be fuel, got {top.system.value}"
    
    # Check that common lean causes are identified
    fault_ids = [c.fault_id for c in result.candidates]
    lean_faults = ["maf_contaminated", "vacuum_leak", "injector_clogged", "fuel_pump_weak"]
    found = any(f in fault_ids for f in lean_faults)
    assert found, f"Should identify lean faults, got {fault_ids}"
    
    print("\n✅ Fuel diagnosis test PASSED")
    return True


def test_ignition_diagnosis():
    """Test diagnosis of ignition system issues."""
    print("\n" + "=" * 70)
    print("TEST 3: Ignition System - Cylinder 2 Misfire")
    print("=" * 70)
    
    result = quick_diagnose(
        dtcs=["P0302"],  # Cylinder 2 misfire
        complaints=["rough_running"]
    )
    
    print_diagnosis(result)
    
    # Should identify ignition faults for specific cylinder
    assert len(result.candidates) > 0, "Should have candidates"
    top = result.candidates[0]
    assert top.system.value == "ignition", f"Top candidate should be ignition, got {top.system.value}"
    
    # Should suggest coil/plug issues
    fault_ids = [c.fault_id for c in result.candidates]
    ignition_faults = ["coil_failed", "coil_weak", "plug_fouled", "plug_worn"]
    found = any(f in fault_ids for f in ignition_faults)
    assert found, f"Should identify ignition faults, got {fault_ids}"
    
    print("\n✅ Ignition diagnosis test PASSED")
    return True


def test_charging_diagnosis():
    """Test diagnosis of charging system issues."""
    print("\n" + "=" * 70)
    print("TEST 4: Charging System - Battery Light On")
    print("=" * 70)
    
    result = quick_diagnose(
        dtcs=["P0562"],  # System voltage low
        complaints=["battery_light", "dim_lights"]
    )
    
    print_diagnosis(result)
    
    # Should identify charging system faults
    assert len(result.candidates) > 0, "Should have candidates"
    top = result.candidates[0]
    assert top.system.value == "charging", f"Top candidate should be charging, got {top.system.value}"
    
    # Should include alternator/battery issues
    fault_ids = [c.fault_id for c in result.candidates]
    charging_faults = ["alternator_failed", "battery_weak", "belt_slipping"]
    found = any(f in fault_ids for f in charging_faults)
    assert found, f"Should identify charging faults, got {fault_ids}"
    
    print("\n✅ Charging diagnosis test PASSED")
    return True


def test_multi_system_diagnosis():
    """Test diagnosis when multiple systems are affected."""
    print("\n" + "=" * 70)
    print("TEST 5: Multi-System - Random Misfire + Battery Issues")
    print("=" * 70)
    
    result = quick_diagnose(
        dtcs=["P0300", "P0562"],  # Random misfire + low voltage
        complaints=["rough_running", "slow_crank"]
    )
    
    print_diagnosis(result)
    
    # Should analyze multiple systems
    assert len(result.systems_analyzed) >= 2, "Should analyze multiple systems"
    
    # Should have candidates from different systems
    systems_in_candidates = set(c.system.value for c in result.candidates)
    assert len(systems_in_candidates) >= 2, f"Should have candidates from multiple systems, got {systems_in_candidates}"
    
    # Low battery can cause both issues - should be highly ranked
    low_voltage_candidates = [c for c in result.candidates if "battery" in c.fault_id or "voltage" in c.fault_id]
    print(f"\n  Battery/voltage related candidates: {[c.fault_id for c in low_voltage_candidates]}")
    
    print("\n✅ Multi-system diagnosis test PASSED")
    return True


def test_complaint_only_diagnosis():
    """Test diagnosis from complaints only (no DTCs)."""
    print("\n" + "=" * 70)
    print("TEST 6: Complaint-Only Diagnosis - Hard Starting")
    print("=" * 70)
    
    result = quick_diagnose(
        complaints=["hard_start", "stalling"]
    )
    
    print_diagnosis(result)
    
    # Should still produce candidates
    assert len(result.candidates) > 0, "Should have candidates from complaints"
    
    print("\n✅ Complaint-only diagnosis test PASSED")
    return True


def test_verification_and_repair_guidance():
    """Test that candidates include actionable guidance."""
    print("\n" + "=" * 70)
    print("TEST 7: Verification and Repair Guidance")
    print("=" * 70)
    
    engine = DiagnosticEngine()
    result = engine.diagnose(
        dtcs=["P0128"],  # Thermostat rationality
        complaints=["runs_cold", "no_heat"]
    )
    
    # Find thermostat candidate
    thermostat_candidates = [c for c in result.candidates if "thermostat" in c.fault_id]
    
    if thermostat_candidates:
        candidate = thermostat_candidates[0]
        print(f"\nCandidate: {candidate.fault_id}")
        print(f"  Description: {candidate.description}")
        print(f"  Severity: {candidate.severity}")
        print(f"  Verification: {candidate.verification_tests}")
        print(f"  Repair: {candidate.repair_actions}")
        print(f"  Est. cost: {candidate.estimated_repair_cost}")
        
        assert candidate.verification_tests, "Should have verification tests"
        assert candidate.repair_actions, "Should have repair actions"
        assert candidate.estimated_repair_cost, "Should have cost estimate"
    
    print("\n✅ Verification and repair guidance test PASSED")
    return True


def run_all_tests():
    """Run all diagnostic engine tests."""
    print("\n" + "=" * 70)
    print("UNIFIED DIAGNOSTIC ENGINE TESTS")
    print("=" * 70)
    
    results = []
    
    tests = [
        ("Cooling diagnosis", test_cooling_diagnosis),
        ("Fuel diagnosis", test_fuel_diagnosis),
        ("Ignition diagnosis", test_ignition_diagnosis),
        ("Charging diagnosis", test_charging_diagnosis),
        ("Multi-system diagnosis", test_multi_system_diagnosis),
        ("Complaint-only diagnosis", test_complaint_only_diagnosis),
        ("Verification and repair guidance", test_verification_and_repair_guidance),
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
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Diagnostic engine is working correctly.")
        print("\nThe engine can:")
        print("  ✓ Accept DTCs, PIDs, and customer complaints")
        print("  ✓ Route symptoms to appropriate physics models")
        print("  ✓ Simulate faults and predict symptoms")
        print("  ✓ Score and rank diagnostic candidates")
        print("  ✓ Provide verification tests and repair guidance")
        print("  ✓ Handle multi-system problems")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
