"""
Body system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


DOOR_LOCK_ACTUATOR_FAILED = FailureMode(
    id="door_lock_actuator_failed",
    name="Door Lock Actuator Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="door_lock",
    system_id="body",
    immediate_effect="Power door lock does not operate",
    cascade_effects=[
        "Door won't lock/unlock with button or remote",
        "Manual lock still works",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Power lock doesn't work on one door", SymptomSeverity.MODERATE),
        Symptom("Buzzing/grinding from door", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check for power at actuator connector",
        "Listen for actuator noise when lock button pressed",
        "Check for binding linkage",
    ],
    repair_actions=["Replace door lock actuator"],
    repair_time_hours=1.5,
    parts_cost_low=30,
    parts_cost_high=150,
    relative_frequency=0.4,
)


WINDOW_REGULATOR_FAILED = FailureMode(
    id="window_regulator_failed",
    name="Window Regulator Failed",
    category=FailureCategory.MECHANICAL,
    component_id="window_regulator",
    system_id="body",
    immediate_effect="Power window does not move or falls down",
    cascade_effects=[
        "Window stuck up or down",
        "May hear motor running but window doesn't move",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Window doesn't move", SymptomSeverity.OBVIOUS),
        Symptom("Window falls down into door", SymptomSeverity.OBVIOUS),
        Symptom("Grinding noise from door", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Can you hear motor running?",
        "Check for broken cable or track",
        "Check regulator mounting",
    ],
    repair_actions=["Replace window regulator", "May include motor"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.5,
)


WINDOW_MOTOR_FAILED = FailureMode(
    id="window_motor_failed",
    name="Window Motor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="window_motor",
    system_id="body",
    immediate_effect="Power window motor does not operate",
    cascade_effects=[
        "Window stuck",
        "No noise when switch pressed",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Window doesn't move", SymptomSeverity.OBVIOUS),
        Symptom("No sound when pressing switch", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check for power at motor with switch pressed",
        "Check ground",
        "Test motor directly with jumper wires",
    ],
    repair_actions=["Replace window motor", "Or replace regulator assembly"],
    repair_time_hours=1.5,
    parts_cost_low=40,
    parts_cost_high=150,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "DOOR_LOCK_ACTUATOR_FAILED",
    "WINDOW_REGULATOR_FAILED",
    "WINDOW_MOTOR_FAILED",
]
