"""
PHEV (Plug-in Hybrid Electric Vehicle) system failure modes.

This module defines failure modes specific to PHEVs, focusing on integration
issues between the ICE (Internal Combustion Engine) and electric systems,
mode transitions, smaller HV battery packs, and charging/regen blending.

These complement pure ICE failures (e.g., from failures_engine.py) and pure EV
failures (from failures_ev.py). PHEVs inherit many from both but have unique
hybrid-specific faults.

Follows the same structure for consistency.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


PHEV_MODE_TRANSITION_FAULT = FailureMode(
    id="phev_mode_transition_fault",
    name="PHEV Mode Transition Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="hybrid_control_module",
    system_id="phev_hybrid",
    immediate_effect="Faulty switch between EV, Hybrid, and Charge modes",
    cascade_effects=[
        "Abrupt engine start/stop",
        "Loss of EV-only mode",
        "Reduced fuel efficiency",
        "Limp mode",
    ],
    expected_dtcs=["P0A0D", "P0A1A", "P0C00", "P0AA6"],  # Hybrid system interlock/mode faults
    symptoms=[
        Symptom("Engine starts unexpectedly in EV mode", SymptomSeverity.MODERATE),
        Symptom("No EV mode available", SymptomSeverity.MODERATE),
        Symptom("Jerky transition to gas engine", SymptomSeverity.OBVIOUS),
        Symptom("Hybrid system warning light", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Monitor mode request vs actual (EV/HEV/CS/CD)",
        "Check clutch/actuator for mode switching",
        "Scan for hybrid readiness monitors",
    ],
    repair_actions=["Update/reprogram hybrid ECU", "Replace mode actuator/clutch"],
    repair_time_hours=2.5,
    parts_cost_low=300,
    parts_cost_high=2000,
    relative_frequency=0.4,
)


PHEV_HV_BATTERY_DEGRADATION = FailureMode(
    id="phev_hv_battery_degradation",
    name="PHEV HV Battery Capacity Degradation",
    category=FailureCategory.DRIFT,
    component_id="phev_hv_battery",
    system_id="phev_battery",
    immediate_effect="Reduced usable capacity in smaller PHEV pack",
    cascade_effects=[
        "Shorter EV-only range",
        "More frequent engine starts",
        "BMS limits power output",
        "Eventual hybrid system disable",
    ],
    expected_dtcs=["P0A7F", "P0A80", "P0AA1"],  # Battery pack deterioration
    symptoms=[
        Symptom("EV range significantly reduced", SymptomSeverity.MODERATE),
        Symptom("Engine runs more often", SymptomSeverity.MODERATE),
        Symptom("Battery health below spec on scan tool", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check SOH (State of Health) via scan tool",
        "Perform capacity test (full charge/discharge cycle)",
        "Monitor cell voltages and delta",
    ],
    repair_actions=["Battery reconditioning (rarely effective)", "Replace hybrid battery pack"],
    repair_time_hours=6.0,
    parts_cost_low=3000,
    parts_cost_high=8000,
    relative_frequency=0.6,
)


PHEV_REGEN_BRAKE_BLENDING_FAULT = FailureMode(
    id="phev_regen_brake_blending_fault",
    name="Regenerative Brake Blending Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="brake_control_module",
    system_id="phev_hybrid",
    immediate_effect="Improper coordination between regen and friction brakes",
    cascade_effects=[
        "Inconsistent brake feel",
        "Reduced regen efficiency",
        "Potential ABS/ESC interference",
    ],
    expected_dtcs=["C1A00", "P0A1B", "U0416"],  # Brake system/hybrid integration faults
    symptoms=[
        Symptom("Brake pedal feel inconsistent", SymptomSeverity.MODERATE),
        Symptom("Reduced regenerative braking", SymptomSeverity.MODERATE),
        Symptom("Brake warning with hybrid fault", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Monitor regen torque vs brake pressure",
        "Road test for blending smoothness",
        "Check wheel speed vs deceleration",
    ],
    repair_actions=["Reprogram brake/hybrid modules", "Replace brake actuator if faulty"],
    repair_time_hours=2.0,
    parts_cost_low=500,
    parts_cost_high=2500,
    relative_frequency=0.4,
)


PHEV_HV_BATTERY_HEATER_FAILURE = FailureMode(
    id="phev_hv_battery_heater_failure",
    name="HV Battery Heater Failure (Cold Weather)",
    category=FailureCategory.ELECTRICAL,
    component_id="battery_heater",
    system_id="phev_thermal",
    immediate_effect="Cannot precondition battery in cold temps",
    cascade_effects=[
        "No charging in cold weather",
        "Reduced power/range when cold",
        "Engine forced on for heat",
    ],
    expected_dtcs=["P0A0B", "P0A0C", "P1A00"],  # Heater circuit faults
    symptoms=[
        Symptom("Charging disabled below freezing", SymptomSeverity.OBVIOUS),
        Symptom("Reduced power in cold conditions", SymptomSeverity.MODERATE),
        Symptom("Battery heater fault message", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check heater current draw",
        "Monitor battery temp vs cabin request",
        "Test PTC heater element resistance",
    ],
    repair_actions=["Replace battery heater element", "Check coolant loop"],
    repair_time_hours=3.0,
    parts_cost_low=400,
    parts_cost_high=1500,
    relative_frequency=0.5,
)


PHEV_GENERATOR_CLUTCH_FAULT = FailureMode(
    id="phev_generator_clutch_fault",
    name="Generator/Motor Clutch Fault",
    category=FailureCategory.MECHANICAL,
    component_id="generator_clutch",
    system_id="phev_powertrain",
    immediate_effect="Cannot engage/disengage generator mode",
    cascade_effects=[
        "No engine charging of battery",
        "Loss of series hybrid mode",
        "Reduced efficiency",
    ],
    expected_dtcs=["P0A40", "P0A41", "P0C00"],  # Drive motor/generator faults
    symptoms=[
        Symptom("Battery not charging from engine", SymptomSeverity.MODERATE),
        Symptom("No series mode operation", SymptomSeverity.MODERATE),
        Symptom("Hybrid system malfunction", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Monitor clutch actuator position",
        "Check for slippage under load",
        "Scan for clutch feedback codes",
    ],
    repair_actions=["Replace clutch actuator", "Inspect transaxle integration"],
    repair_time_hours=5.0,
    parts_cost_low=800,
    parts_cost_high=3000,
    relative_frequency=0.3,
)


PHEV_DC_DC_CONVERTER_FAULT = FailureMode(
    id="phev_dc_dc_converter_fault",
    name="DC-DC Converter Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="dc_dc_converter",
    system_id="phev_hybrid",
    immediate_effect="No 12V charging from HV system",
    cascade_effects=[
        "12V battery drain",
        "Electrical accessory issues",
        "Eventual no-start",
    ],
    expected_dtcs=["P0AEF", "P0AF0", "P0A08"],
    symptoms=[
        Symptom("12V battery warning", SymptomSeverity.MODERATE),
        Symptom("Dim lights/accessories failing", SymptomSeverity.MODERATE),
        Symptom("Vehicle shuts down after HV depletion", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Measure DC-DC output voltage",
        "Check 12V charge rate with HV on",
        "Monitor current draw",
    ],
    repair_actions=["Replace DC-DC converter module"],
    repair_time_hours=2.5,
    parts_cost_low=600,
    parts_cost_high=2000,
    relative_frequency=0.4,
)


# Exports - add these to failures.py re-exports and FAILURE_REGISTRY
__all__ = [
    "PHEV_MODE_TRANSITION_FAULT",
    "PHEV_HV_BATTERY_DEGRADATION",
    "PHEV_REGEN_BRAKE_BLENDING_FAULT",
    "PHEV_HV_BATTERY_HEATER_FAILURE",
    "PHEV_GENERATOR_CLUTCH_FAULT",
    "PHEV_DC_DC_CONVERTER_FAULT",
]
