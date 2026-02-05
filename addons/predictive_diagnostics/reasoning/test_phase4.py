#!/usr/bin/env python3
"""
Phase 4 Validation: Diagnostic Reasoning

Tests that the reasoning module can:
1. Update beliefs correctly with Bayesian inference
2. Recommend informative tests
3. Reach accurate conclusions
4. Explain its reasoning
"""

import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.reasoning import (
    BayesianReasoner,
    BeliefState,
    Diagnostician,
    DiagnosticSession,
    DiagnosticConclusion,
)


def test_bayesian_update():
    """Test Bayesian belief updating."""
    print("\n" + "="*60)
    print("TEST: Bayesian Belief Update")
    print("="*60)
    
    reasoner = BayesianReasoner()
    
    # Start with uniform prior
    state = reasoner.create_initial_state()
    
    print(f"Initial entropy: {state.get_entropy():.2f} bits")
    print(f"Initial top hypotheses:")
    for h, p in state.get_top_hypotheses(3):
        print(f"  {h}: {p:.1%}")
    
    # Observe high coolant temp
    state = reasoner.update(state, "coolant_temp_high", observed=True)
    
    print(f"\nAfter observing HIGH coolant temp:")
    print(f"Entropy: {state.get_entropy():.2f} bits")
    for h, p in state.get_top_hypotheses(5):
        print(f"  {h}: {p:.1%}")
    
    # Verify update worked
    top = state.get_top_hypotheses(1)[0]
    assert top[0] in ["thermostat_stuck_closed", "ect_sensor_failed_high", 
                      "radiator_blocked", "water_pump_failure"], \
        f"Top hypothesis should be heat-related, got {top[0]}"
    
    # Add more evidence: fan is running
    state = reasoner.update(state, "fan_not_running_when_hot", observed=False)
    
    print(f"\nAfter observing fan IS running:")
    print(f"Entropy: {state.get_entropy():.2f} bits")
    for h, p in state.get_top_hypotheses(5):
        print(f"  {h}: {p:.1%}")
    
    # Fan working rules out fan failure
    fan_prob = state.probabilities.get("cooling_fan_not_operating", 0)
    assert fan_prob < 0.1, f"Fan failure should be low probability, got {fan_prob:.1%}"
    
    print("\n✓ Bayesian update PASSED")


def test_test_recommendation():
    """Test that reasoner recommends informative tests."""
    print("\n" + "="*60)
    print("TEST: Test Recommendation")
    print("="*60)
    
    reasoner = BayesianReasoner()
    state = reasoner.create_initial_state()
    
    # Get initial recommendation (should suggest something)
    test = reasoner.get_best_test(state)
    print(f"Initial recommendation: {test['test']}")
    print(f"  Description: {test['description']}")
    print(f"  Expected info gain: {test['expected_info_gain']:.3f} bits")
    
    assert test is not None, "Should recommend a test"
    assert test['expected_info_gain'] > 0, "Test should have positive info gain"
    
    # After observing high temp, should recommend discriminating test
    state = reasoner.update(state, "coolant_temp_high", observed=True)
    test = reasoner.get_best_test(state)
    
    print(f"\nAfter high temp observed: {test['test']}")
    print(f"  Expected info gain: {test['expected_info_gain']:.3f} bits")
    
    print("\n✓ Test recommendation PASSED")


def test_diagnostic_session():
    """Test full diagnostic session flow."""
    print("\n" + "="*60)
    print("TEST: Diagnostic Session")
    print("="*60)
    
    diag = Diagnostician()
    
    # Start session with overheating complaint
    session = diag.start_session(
        vehicle_info={"year": "2015", "make": "Toyota", "model": "Camry"},
        initial_symptoms=["engine running hot", "temp gauge high"]
    )
    
    print(f"Session started: {session.session_id}")
    print(f"Initial symptoms: {session.initial_symptoms}")
    
    state = diag.get_current_state(session)
    print(f"\nInitial beliefs after symptoms:")
    for h, p in state.get_top_hypotheses(5):
        print(f"  {h}: {p:.1%}")
    
    # Record observations
    diag.record_observation(session, "fan_not_running_when_hot", observed=True)
    
    state = diag.get_current_state(session)
    print(f"\nAfter observing fan NOT running:")
    for h, p in state.get_top_hypotheses(3):
        print(f"  {h}: {p:.1%}")
    
    # This should strongly suggest fan failure
    top = state.get_top_hypotheses(1)[0]
    assert "fan" in top[0].lower() or top[1] > 0.3, \
        "Fan not running should suggest fan failure"
    
    print("\n✓ Diagnostic session PASSED")


def test_conclusion_generation():
    """Test reaching a diagnostic conclusion."""
    print("\n" + "="*60)
    print("TEST: Conclusion Generation")
    print("="*60)
    
    diag = Diagnostician()
    
    # Scenario: Clear thermostat stuck open case
    session = diag.start_session(
        initial_symptoms=["engine running cold", "no heat from heater"]
    )
    
    # Add evidence pointing to stuck open thermostat
    diag.record_observation(session, "coolant_temp_low", observed=True)
    diag.record_observation(session, "dtc_P0128", observed=True)
    
    # Force conclusion
    conclusion = diag.force_conclusion(session)
    
    print(conclusion)
    
    # Verify conclusion
    assert conclusion.primary_diagnosis in ["thermostat_stuck_open", "ect_sensor_failed_low"], \
        f"Expected thermostat or sensor diagnosis, got {conclusion.primary_diagnosis}"
    assert conclusion.confidence > 0.3, "Should have reasonable confidence"
    assert len(conclusion.recommended_actions) > 0, "Should have repair recommendations"
    
    print("\n✓ Conclusion generation PASSED")


def test_reasoning_explanation():
    """Test generating reasoning explanation."""
    print("\n" + "="*60)
    print("TEST: Reasoning Explanation")
    print("="*60)
    
    diag = Diagnostician()
    
    session = diag.start_session(
        initial_symptoms=["overheating at idle"]
    )
    
    diag.record_observation(session, "coolant_temp_high", observed=True)
    diag.record_observation(session, "coolant_level_low", observed=False)  # Level OK
    
    explanation = diag.explain_reasoning(session)
    print(explanation)
    
    assert "Evidence collected" in explanation, "Should show evidence"
    assert "Current beliefs" in explanation, "Should show beliefs"
    
    print("\n✓ Reasoning explanation PASSED")


def test_quick_diagnose():
    """Test the quick diagnosis function."""
    print("\n" + "="*60)
    print("TEST: Quick Diagnose")
    print("="*60)
    
    from addons.predictive_diagnostics.reasoning.diagnostician import quick_diagnose
    
    # Scenario: Clear ECT sensor failure (gauge reads hot, but engine is cool)
    result = quick_diagnose(
        symptoms=["temp gauge very high"],
        observations={
            "coolant_temp_high": True,  # Gauge reads high
            "infrared_temp_differs_from_gauge": True,  # But IR says it's normal
        }
    )
    
    print(result)
    
    assert result.primary_diagnosis in ["ect_sensor_failed_high"], \
        f"Expected sensor failure, got {result.primary_diagnosis}"
    
    print("\n✓ Quick diagnose PASSED")


def main():
    """Run all Phase 4 validation tests."""
    print("\n" + "#"*60)
    print("# PHASE 4 VALIDATION: Diagnostic Reasoning")
    print("#"*60)
    
    try:
        test_bayesian_update()
        test_test_recommendation()
        test_diagnostic_session()
        test_conclusion_generation()
        test_reasoning_explanation()
        test_quick_diagnose()
        
        print("\n" + "="*60)
        print("ALL PHASE 4 TESTS PASSED!")
        print("="*60)
        print("\nPhase 4 is complete. Ready for Phase 5: Integration")
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
