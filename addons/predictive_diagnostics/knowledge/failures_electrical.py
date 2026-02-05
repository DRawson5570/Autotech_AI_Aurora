"""
Electrical system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


GROUND_CIRCUIT_POOR = FailureMode(
    id="ground_circuit_poor",
    name="Poor Ground Connection",
    category=FailureCategory.ELECTRICAL,
    component_id="ground_circuit",
    system_id="electrical",
    immediate_effect="High resistance in ground path",
    cascade_effects=[
        "Multiple systems may be affected",
        "Intermittent problems",
        "Dim lights when other loads active",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Multiple intermittent electrical issues", SymptomSeverity.MODERATE),
        Symptom("Dim or flickering lights", SymptomSeverity.MODERATE),
        Symptom("Hard starting", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Voltage drop test on ground circuits (<0.2V)",
        "Check engine-to-chassis ground straps",
        "Check battery negative cable connections",
    ],
    repair_actions=[
        "Clean and tighten ground connections",
        "Add supplemental ground strap if needed",
    ],
    repair_time_hours=0.5,
    parts_cost_low=5,
    parts_cost_high=30,
    relative_frequency=0.6,
)


POWER_FEED_CIRCUIT_ISSUE = FailureMode(
    id="power_feed_circuit_issue",
    name="Power Feed Circuit Problem",
    category=FailureCategory.ELECTRICAL,
    component_id="power_circuit",
    system_id="electrical",
    immediate_effect="Insufficient power to component",
    cascade_effects=[
        "Component operates erratically or not at all",
        "Blown fuse possible",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Component not working", SymptomSeverity.OBVIOUS),
        Symptom("Intermittent operation", SymptomSeverity.MODERATE),
        Symptom("Blown fuse", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check fuse condition",
        "Check voltage at component (should be battery voltage)",
        "Voltage drop test on power side",
    ],
    repair_actions=[
        "Replace fuse",
        "Repair wiring",
        "Replace relay if applicable",
    ],
    repair_time_hours=0.5,
    parts_cost_low=5,
    parts_cost_high=50,
    relative_frequency=0.5,
)


RELAY_FAILED = FailureMode(
    id="relay_failed",
    name="Relay Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="relay",
    system_id="electrical",
    immediate_effect="Circuit controlled by relay does not operate",
    cascade_effects=[
        "Component powered by relay is inoperative",
        "May be stuck on or stuck off",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Component not working (fan, pump, etc.)", SymptomSeverity.OBVIOUS),
        Symptom("Component stuck on", SymptomSeverity.OBVIOUS),
        Symptom("No click when relay should activate", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Swap with known good relay of same type",
        "Check for relay click when activated",
        "Bench test relay with jumper wires",
        "Check control signal to relay coil",
    ],
    repair_actions=["Replace relay"],
    repair_time_hours=0.2,
    parts_cost_low=10,
    parts_cost_high=40,
    relative_frequency=0.5,
)


FUSE_BLOWN = FailureMode(
    id="fuse_blown",
    name="Blown Fuse",
    category=FailureCategory.ELECTRICAL,
    component_id="fuse",
    system_id="electrical",
    immediate_effect="Circuit is open - no power to component",
    cascade_effects=[
        "One or more components inoperative",
        "Root cause may be short circuit",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Component completely inoperative", SymptomSeverity.OBVIOUS),
        Symptom("Multiple components on same circuit not working", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of fuse",
        "Test fuse with multimeter",
        "If fuse blows again, look for short circuit",
    ],
    repair_actions=[
        "Replace fuse",
        "Find and repair short if fuse blows again",
    ],
    repair_time_hours=0.2,
    parts_cost_low=1,
    parts_cost_high=5,
    relative_frequency=0.7,
)


WIRING_HARNESS_CHAFED = FailureMode(
    id="wiring_harness_chafed",
    name="Wiring Harness Chafed/Damaged",
    category=FailureCategory.ELECTRICAL,
    component_id="wiring",
    system_id="electrical",
    immediate_effect="Exposed wire may short to ground or other circuits",
    cascade_effects=[
        "Blown fuses",
        "Intermittent problems",
        "Short circuits",
        "Possible fire hazard",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Intermittent electrical problems", SymptomSeverity.MODERATE),
        Symptom("Blown fuses", SymptomSeverity.OBVIOUS),
        Symptom("Burning smell", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Visual inspection along harness route",
        "Check common chafe points (pass-throughs, clamps)",
        "Wiggle harness while monitoring circuit",
    ],
    repair_actions=[
        "Repair damaged wiring",
        "Add protective loom or tape",
        "Reroute harness away from sharp edges",
    ],
    repair_time_hours=1.0,
    parts_cost_low=10,
    parts_cost_high=50,
    relative_frequency=0.4,
)


CONNECTOR_CORROSION = FailureMode(
    id="connector_corrosion",
    name="Connector Corrosion",
    category=FailureCategory.ELECTRICAL,
    component_id="connector",
    system_id="electrical",
    immediate_effect="High resistance or open circuit at connector",
    cascade_effects=[
        "Intermittent connection",
        "Complete circuit failure",
        "Heat buildup at connector",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Intermittent problems", SymptomSeverity.MODERATE),
        Symptom("Green/white corrosion visible", SymptomSeverity.OBVIOUS),
        Symptom("Component works sometimes", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection of connector",
        "Voltage drop across connector",
        "Measure resistance through connector pins",
    ],
    repair_actions=[
        "Clean connector with electrical cleaner",
        "Apply dielectric grease",
        "Replace connector if severely corroded",
    ],
    repair_time_hours=0.5,
    parts_cost_low=5,
    parts_cost_high=50,
    relative_frequency=0.5,
)


PARASITIC_DRAIN = FailureMode(
    id="parasitic_drain",
    name="Parasitic Battery Drain",
    category=FailureCategory.ELECTRICAL,
    component_id="electrical_system",
    system_id="electrical",
    immediate_effect="Something is draining battery when vehicle is off",
    cascade_effects=[
        "Dead battery after sitting",
        "Repeated jump starts needed",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Battery dead after sitting overnight or longer", SymptomSeverity.OBVIOUS),
        Symptom("Battery keeps dying", SymptomSeverity.SEVERE),
        Symptom("Jump starts vehicle but dies again", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Parasitic drain test (measure current with car off)",
        "Normal is <50mA after modules sleep",
        "Pull fuses one at a time to find circuit",
    ],
    repair_actions=["Find and repair source of drain", "Check for stuck relay", "Check aftermarket accessories"],
    repair_time_hours=2.0,
    parts_cost_low=0,
    parts_cost_high=200,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "GROUND_CIRCUIT_POOR",
    "POWER_FEED_CIRCUIT_ISSUE",
    "RELAY_FAILED",
    "FUSE_BLOWN",
    "WIRING_HARNESS_CHAFED",
    "CONNECTOR_CORROSION",
    "PARASITIC_DRAIN",
]
