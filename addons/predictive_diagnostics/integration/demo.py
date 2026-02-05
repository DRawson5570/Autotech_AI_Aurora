#!/usr/bin/env python3
"""
Predictive Diagnostics Demo

Demonstrates the full diagnostic pipeline:
  Sensor Data → Evidence → Reasoning → Diagnosis

This shows how a 1-2 hour diagnostic process becomes 5 minutes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration import DiagnosticEngine, SensorReading


def print_header(text: str):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_result(result):
    """Pretty print a diagnostic result"""
    print(f"\n📋 DIAGNOSIS: {result.primary_failure.replace('_', ' ').title()}")
    print(f"   Confidence: {result.confidence*100:.1f}%")
    print(f"   Phase: {result.phase.value}")
    
    if result.alternatives:
        print(f"\n   Also consider:")
        for failure, conf in result.alternatives[:3]:
            print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    if result.repair_actions:
        print(f"\n   🔧 Recommended repairs:")
        for action in result.repair_actions:
            print(f"   - {action}")
    
    if result.recommended_test:
        print(f"\n   🔍 Recommended test: {result.recommended_test}")
        print(f"      {result.test_reason}")


def demo_quick_diagnosis():
    """Demo 1: Quick diagnosis from sensors and symptoms"""
    print_header("DEMO 1: Quick Diagnosis - Overheating Vehicle")
    
    print("\n📥 Customer complaint: 'Car is overheating, steam from hood'")
    print("   Sensor data: Coolant temp 118°C, Oil pressure 42 psi")
    print("   DTC codes: P0217 (Engine Overtemp)")
    
    engine = DiagnosticEngine()
    
    result = engine.diagnose(
        sensors=[
            SensorReading("coolant_temp", 118, "°C"),
            SensorReading("oil_pressure", 42, "psi"),
        ],
        dtcs=["P0217"],
        symptoms=["overheating", "steam from hood"]
    )
    
    print_result(result)
    print(f"\n   Evidence used: {result.evidence_used}")


def demo_interactive_session():
    """Demo 2: Interactive diagnostic session with test recommendations"""
    print_header("DEMO 2: Interactive Session - Systematic Diagnosis")
    
    engine = DiagnosticEngine()
    session = engine.start_session()
    
    # Step 1: Initial complaint
    print("\n📥 Step 1: Customer says 'car running cold, no heat'")
    session.add_symptom("no heat")
    session.add_symptom("running cold")
    
    suspects = session.get_top_suspects(3)
    print(f"   Initial suspects:")
    for failure, conf in suspects:
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    # Get recommended test
    test_rec = session.recommend_test()
    if test_rec:
        print(f"\n🔍 Recommended test: {test_rec[2]}")
        print(f"   Information gain: {test_rec[1]:.3f} bits")
    
    # Step 2: Perform test - check DTC
    print("\n📥 Step 2: Scan tool shows P0128 (Thermostat Below Temp)")
    session.add_dtc("P0128")
    
    suspects = session.get_top_suspects(3)
    print(f"   Updated suspects:")
    for failure, conf in suspects:
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    # Step 3: Physical check
    print("\n📥 Step 3: Check upper radiator hose - cold after 10 min idle")
    session.add_observation("upper_hose_cold")
    
    suspects = session.get_top_suspects(3)
    print(f"   Updated suspects:")
    for failure, conf in suspects:
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    # Get final diagnosis
    result = session.conclude()
    print_result(result)
    
    print(f"\n📊 Uncertainty reduced: {session.get_uncertainty():.2f} bits remaining")


def demo_differential_diagnosis():
    """Demo 3: Differential diagnosis - distinguishing similar failures"""
    print_header("DEMO 3: Differential Diagnosis - Fan vs Thermostat")
    
    print("\n📥 Situation: Overheating, but need to distinguish cause")
    print("   Could be: thermostat stuck closed, fan not operating, or blocked radiator")
    
    engine = DiagnosticEngine()
    session = engine.start_session()
    
    # Initial symptom
    session.add_symptom("overheating")
    
    print("\n   Initial beliefs (before testing):")
    for failure, conf in session.get_top_suspects(5):
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    # Test 1: Check if fan is running
    print("\n🔍 Test 1: Is the cooling fan running?")
    print("   Result: Fan IS running")
    session.add_observation("fan_running")
    
    print("\n   Updated beliefs:")
    for failure, conf in session.get_top_suspects(5):
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    # Test 2: Check hose temperatures
    print("\n🔍 Test 2: Feel upper radiator hose")
    print("   Result: Upper hose very hot, but no flow sensation")
    session.add_observation("upper_hose_hot_no_flow")
    
    print("\n   Updated beliefs:")
    for failure, conf in session.get_top_suspects(3):
        print(f"   - {failure.replace('_', ' ').title()}: {conf*100:.1f}%")
    
    result = session.conclude()
    print_result(result)


def demo_sensor_interpretation():
    """Demo 4: Show sensor threshold interpretation"""
    print_header("DEMO 4: Sensor Interpretation")
    
    engine = DiagnosticEngine()
    
    print("\n📊 Supported sensors and thresholds:")
    for sensor in engine.get_supported_sensors():
        thresholds = engine.SENSOR_THRESHOLDS[sensor]
        print(f"\n   {sensor}:")
        for condition, (threshold, evidence) in thresholds.items():
            if condition in ['high', 'low']:
                op = '>' if condition == 'high' else '<'
                print(f"     {op} {threshold} → {evidence}")
    
    print("\n📋 Example interpretations:")
    
    test_sensors = [
        SensorReading("coolant_temp", 115, "°C"),
        SensorReading("coolant_temp", 65, "°C"),
        SensorReading("coolant_temp", 92, "°C"),
        SensorReading("oil_pressure", 15, "psi"),
        SensorReading("battery_voltage", 11.5, "V"),
    ]
    
    for sensor in test_sensors:
        evidence = engine._sensor_to_evidence(sensor)
        status = evidence if evidence else "normal"
        print(f"   {sensor.name} = {sensor.value}{sensor.unit} → {status}")


def demo_api_output():
    """Demo 5: Show API output format"""
    print_header("DEMO 5: API Output Format")
    
    engine = DiagnosticEngine()
    
    result = engine.diagnose(
        sensors=[SensorReading("coolant_temp", 112, "°C")],
        dtcs=["P0217"],
        symptoms=["overheating"]
    )
    
    print("\n📤 API Response (JSON-ready):")
    import json
    print(json.dumps(result.to_dict(), indent=2))


def main():
    """Run all demos"""
    print("\n" + "🚗"*30)
    print("    PREDICTIVE DIAGNOSTICS ENGINE - DEMONSTRATION")
    print("    'Cut 1-2 hour diagnostic to 5 minutes'")
    print("🚗"*30)
    
    demo_quick_diagnosis()
    demo_interactive_session()
    demo_differential_diagnosis()
    demo_sensor_interpretation()
    demo_api_output()
    
    print_header("DEMONSTRATION COMPLETE")
    print("""
    Key capabilities demonstrated:
    
    1. ✅ Quick diagnosis from sensors + DTCs + symptoms
    2. ✅ Interactive sessions with test recommendations  
    3. ✅ Differential diagnosis (distinguishing similar failures)
    4. ✅ Automatic sensor threshold interpretation
    5. ✅ API output format for integration
    
    The system combines:
    - Physics-based causal reasoning
    - Bayesian belief updating
    - Domain knowledge encoding
    - Machine learning patterns
    
    Result: Systematic diagnosis that would take 1-2 hours 
    manually now takes minutes with guided test recommendations.
    """)


if __name__ == "__main__":
    main()
