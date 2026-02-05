"""
Communication system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


CAN_BUS_FAILURE = FailureMode(
    id="can_bus_failure",
    name="CAN Bus Communication Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="can_bus",
    system_id="communication",
    immediate_effect="Modules cannot communicate with each other",
    cascade_effects=[
        "Multiple warning lights",
        "Multiple systems inoperative",
        "No communication with scan tool",
    ],
    expected_dtcs=["U0100", "U0101", "U0121", "U0140", "U0155"],
    symptoms=[
        Symptom("Multiple warning lights", SymptomSeverity.SEVERE),
        Symptom("Scan tool cannot communicate", SymptomSeverity.OBVIOUS),
        Symptom("Multiple systems not working", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Check CAN bus termination (60 ohms between CAN H and CAN L)",
        "Check for proper voltage on CAN lines",
        "Check for damaged/shorted CAN wires",
        "Unplug modules one at a time to find bad one",
    ],
    repair_actions=[
        "Repair CAN bus wiring",
        "Replace faulty module",
        "Check DLC connector",
    ],
    repair_time_hours=2.0,
    parts_cost_low=50,
    parts_cost_high=500,
    relative_frequency=0.3,
)


MODULE_INTERNAL_FAILURE = FailureMode(
    id="module_internal_failure",
    name="Control Module Internal Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="control_module",
    system_id="communication",
    immediate_effect="Module does not function correctly",
    cascade_effects=[
        "System controlled by module is inoperative",
        "Possible U-codes in other modules",
    ],
    expected_dtcs=["U0100", "U0101", "U0121", "U0140"],
    symptoms=[
        Symptom("System completely inoperative", SymptomSeverity.SEVERE),
        Symptom("No response to inputs", SymptomSeverity.OBVIOUS),
        Symptom("Check engine or warning light", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check power and ground to module",
        "Check for communication with scan tool",
        "Verify inputs and outputs with scope",
    ],
    repair_actions=["Replace module", "Program/configure new module"],
    repair_time_hours=1.5,
    parts_cost_low=200,
    parts_cost_high=1500,
    relative_frequency=0.3,
)


DLC_CONNECTOR_DAMAGED = FailureMode(
    id="dlc_connector_damaged",
    name="DLC Connector Damaged",
    category=FailureCategory.ELECTRICAL,
    component_id="dlc",
    system_id="communication",
    immediate_effect="Cannot communicate with vehicle via OBD port",
    cascade_effects=[
        "Cannot read codes",
        "Cannot perform diagnostics",
        "May indicate CAN bus issue",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Scan tool won't connect", SymptomSeverity.OBVIOUS),
        Symptom("Intermittent scan tool connection", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Inspect DLC for bent/pushed pins",
        "Check for power at pin 16 (B+) and ground at pins 4,5",
        "Check CAN signals at pins 6 and 14",
    ],
    repair_actions=["Replace DLC connector", "Repair wiring to DLC"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=80,
    relative_frequency=0.3,
)


# Exports
__all__ = [
    "CAN_BUS_FAILURE",
    "MODULE_INTERNAL_FAILURE",
    "DLC_CONNECTOR_DAMAGED",
]
