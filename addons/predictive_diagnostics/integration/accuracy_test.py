#!/usr/bin/env python3
"""
Accuracy Test - How well does the diagnostic engine identify failures?

Tests the engine against scenarios with known ground truth.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration import DiagnosticEngine, SensorReading


# Test scenarios: (name, inputs, expected_failure)
TEST_SCENARIOS = [
    # Thermostat stuck closed - overheating, high temp, no flow to radiator
    {
        "name": "Thermostat stuck closed",
        "expected": "thermostat_stuck_closed",
        "symptoms": ["overheating"],
        "dtcs": ["P0217"],
        "evidence": ["upper_hose_hot_no_flow", "fan_running"],
    },
    
    # Thermostat stuck open - runs cold, slow warm up
    {
        "name": "Thermostat stuck open", 
        "expected": "thermostat_stuck_open",
        "symptoms": ["running cold", "no heat"],
        "dtcs": ["P0128"],
        "evidence": ["upper_hose_cold"],
    },
    
    # Cooling fan not operating - overheating at idle/low speed
    {
        "name": "Cooling fan failure",
        "expected": "cooling_fan_not_operating",
        "symptoms": ["overheating"],
        "dtcs": ["P0480"],
        "evidence": ["fan_not_running_when_hot", "temp_rises_at_idle"],
    },
    
    # Water pump failure - overheating, no flow
    {
        "name": "Water pump failure",
        "expected": "water_pump_failure",
        "symptoms": ["overheating"],
        "evidence": ["upper_hose_hot_no_flow", "fan_running", "coolant_level_ok"],
    },
    
    # ECT sensor failed high - gauge reads high but engine cool
    {
        "name": "ECT sensor failed high",
        "expected": "ect_sensor_failed_high",
        "symptoms": ["temp gauge high"],
        "evidence": ["infrared_temp_differs_from_gauge", "fan_always_on"],
    },
    
    # ECT sensor failed low - gauge reads low but engine hot  
    {
        "name": "ECT sensor failed low",
        "expected": "ect_sensor_failed_low",
        "symptoms": ["no heat"],  # Fan never runs, engine runs rich
        "dtcs": ["P0128"],
        "evidence": ["infrared_temp_differs_from_gauge"],
    },
    
    # Radiator blocked - overheating, radiator cold spots
    {
        "name": "Radiator blocked",
        "expected": "radiator_blocked",
        "symptoms": ["overheating"],
        "evidence": ["upper_hose_hot_no_flow", "fan_running", "radiator_cold_spots"],
    },
    
    # Coolant leak - overheating with low coolant
    {
        "name": "Coolant leak",
        "expected": "coolant_leak",
        "symptoms": ["overheating", "coolant leak"],
        "evidence": ["coolant_level_low"],
    },
    
    # Normal system - no issues
    {
        "name": "Normal system",
        "expected": "normal",
        "symptoms": [],
        "evidence": ["infrared_temp_matches_gauge"],
    },
]


def run_accuracy_test():
    """Run accuracy test on all scenarios"""
    print("\n" + "="*60)
    print("  DIAGNOSTIC ENGINE ACCURACY TEST")
    print("="*60)
    
    engine = DiagnosticEngine()
    
    correct = 0
    top3_correct = 0
    total = len(TEST_SCENARIOS)
    
    results = []
    
    for scenario in TEST_SCENARIOS:
        name = scenario["name"]
        expected = scenario["expected"]
        symptoms = scenario.get("symptoms", [])
        dtcs = scenario.get("dtcs", [])
        evidence = scenario.get("evidence", [])
        
        # Run diagnosis
        result = engine.diagnose(
            symptoms=symptoms,
            dtcs=dtcs,
            additional_evidence=evidence
        )
        
        # Check if correct
        is_correct = result.primary_failure == expected
        is_top3 = expected in [result.primary_failure] + [a[0] for a in result.alternatives[:2]]
        
        if is_correct:
            correct += 1
        if is_top3:
            top3_correct += 1
        
        results.append({
            "name": name,
            "expected": expected,
            "predicted": result.primary_failure,
            "confidence": result.confidence,
            "correct": is_correct,
            "top3": is_top3,
            "alternatives": result.alternatives[:3],
        })
        
        # Print result
        status = "✅" if is_correct else ("⚠️" if is_top3 else "❌")
        print(f"\n{status} {name}")
        print(f"   Expected: {expected}")
        print(f"   Predicted: {result.primary_failure} ({result.confidence*100:.1f}%)")
        if not is_correct and result.alternatives:
            print(f"   Top 3: {[a[0] for a in result.alternatives[:2]]}")
    
    # Summary
    accuracy = correct / total * 100
    top3_accuracy = top3_correct / total * 100
    
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    print(f"\n  Top-1 Accuracy: {correct}/{total} = {accuracy:.1f}%")
    print(f"  Top-3 Accuracy: {top3_correct}/{total} = {top3_accuracy:.1f}%")
    
    print(f"\n  Interpretation:")
    if accuracy >= 70:
        print("  ✅ Good - Engine correctly identifies most failures")
    elif accuracy >= 50:
        print("  ⚠️ Moderate - Engine often correct but needs more evidence")
    else:
        print("  ❌ Needs improvement - Knowledge base may need expansion")
    
    if top3_accuracy >= 80:
        print("  ✅ Excellent top-3 - Correct answer usually in top candidates")
    
    return accuracy, top3_accuracy


if __name__ == "__main__":
    run_accuracy_test()
