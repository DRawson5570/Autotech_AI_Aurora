"""
Tpms system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


TPMS_SENSOR_BATTERY_DEAD = FailureMode(
    id="tpms_sensor_battery_dead",
    name="TPMS Sensor Battery Dead",
    category=FailureCategory.ELECTRICAL,
    component_id="tpms_sensor",
    system_id="tpms",
    immediate_effect="TPMS sensor stops transmitting",
    cascade_effects=[
        "TPMS light on",
        "No pressure reading from that wheel",
    ],
    expected_dtcs=["C0750", "C0755", "C0760", "C0765"],
    symptoms=[
        Symptom("TPMS warning light on", SymptomSeverity.OBVIOUS),
        Symptom("One tire shows no reading", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "TPMS scan tool to check sensor response",
        "Check if sensor ID is still recognized",
        "Check battery life in scan tool data",
    ],
    repair_actions=["Replace TPMS sensor", "Relearn new sensor to vehicle"],
    repair_time_hours=0.5,
    parts_cost_low=40,
    parts_cost_high=100,
    relative_frequency=0.5,
)


TPMS_SENSOR_DAMAGED = FailureMode(
    id="tpms_sensor_damaged",
    name="TPMS Sensor Damaged",
    category=FailureCategory.MECHANICAL,
    component_id="tpms_sensor",
    system_id="tpms",
    immediate_effect="TPMS sensor physically damaged or malfunctioning",
    cascade_effects=[
        "TPMS light on",
        "Incorrect readings",
        "Possible air leak at sensor seal",
    ],
    expected_dtcs=["C0750", "C0755", "C0760", "C0765"],
    symptoms=[
        Symptom("TPMS warning light on", SymptomSeverity.OBVIOUS),
        Symptom("Erratic or incorrect pressure reading", SymptomSeverity.MODERATE),
        Symptom("Slow leak from tire", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection of sensor (if accessible)",
        "Check sensor with TPMS tool",
        "Check for damage during tire service",
    ],
    repair_actions=["Replace TPMS sensor", "Replace sensor seal if leaking"],
    repair_time_hours=0.5,
    parts_cost_low=40,
    parts_cost_high=100,
    relative_frequency=0.4,
)


TPMS_MODULE_FAILURE = FailureMode(
    id="tpms_module_failure",
    name="TPMS Module/Receiver Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="tpms_module",
    system_id="tpms",
    immediate_effect="Vehicle cannot receive TPMS signals",
    cascade_effects=[
        "TPMS light on",
        "All sensors show no data",
    ],
    expected_dtcs=["C0775", "U0184"],
    symptoms=[
        Symptom("TPMS light on", SymptomSeverity.OBVIOUS),
        Symptom("All tires show no reading", SymptomSeverity.OBVIOUS),
        Symptom("Cannot relearn sensors", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check if module powers up",
        "Check for communication with scan tool",
        "Verify all 4 sensors are functional with TPMS tool",
    ],
    repair_actions=["Replace TPMS module", "Check wiring to module"],
    repair_time_hours=1.0,
    parts_cost_low=100,
    parts_cost_high=300,
    relative_frequency=0.2,
)


# Exports
__all__ = [
    "TPMS_SENSOR_BATTERY_DEAD",
    "TPMS_SENSOR_DAMAGED",
    "TPMS_MODULE_FAILURE",
]
