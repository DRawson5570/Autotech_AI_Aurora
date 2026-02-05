"""
Safety system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


AIRBAG_SENSOR_FAILED = FailureMode(
    id="airbag_sensor_failed",
    name="Airbag Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="airbag_sensor",
    system_id="safety",
    immediate_effect="Airbag system cannot detect impact properly",
    cascade_effects=[
        "Airbag light on",
        "Airbags may not deploy in crash",
        "Or may deploy unexpectedly",
    ],
    expected_dtcs=["B0001", "B0002", "B0012", "B0022"],
    symptoms=[
        Symptom("Airbag warning light on", SymptomSeverity.SEVERE),
        Symptom("Airbag light stays on after start", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Scan for airbag codes",
        "Check sensor connector",
        "Check for damage to sensor",
        "Do NOT test airbag deployment",
    ],
    repair_actions=["Replace airbag sensor", "Clear codes and verify"],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.3,
)


AIRBAG_CLOCK_SPRING_FAILED = FailureMode(
    id="airbag_clock_spring_failed",
    name="Airbag Clock Spring Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="clock_spring",
    system_id="safety",
    immediate_effect="Electrical connection to steering wheel interrupted",
    cascade_effects=[
        "Driver airbag may not work",
        "Horn may not work",
        "Steering wheel controls may not work",
    ],
    expected_dtcs=["B0053", "B0054", "B1000"],
    symptoms=[
        Symptom("Airbag light on", SymptomSeverity.SEVERE),
        Symptom("Horn not working", SymptomSeverity.MODERATE),
        Symptom("Steering wheel buttons not working", SymptomSeverity.MODERATE),
        Symptom("Clicking noise when turning wheel", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check horn operation",
        "Check steering wheel controls",
        "Scan for airbag codes",
        "Check clock spring continuity",
    ],
    repair_actions=["Replace clock spring"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


SEATBELT_BUCKLE_SWITCH_FAILED = FailureMode(
    id="seatbelt_buckle_switch_failed",
    name="Seatbelt Buckle Switch Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="seatbelt_switch",
    system_id="safety",
    immediate_effect="Vehicle thinks seatbelt is unbuckled (or buckled when not)",
    cascade_effects=[
        "Constant seatbelt warning chime",
        "Seatbelt light stays on",
        "Or no warning when unbuckled",
    ],
    expected_dtcs=["B0073", "B0074"],
    symptoms=[
        Symptom("Seatbelt warning stays on when buckled", SymptomSeverity.OBVIOUS),
        Symptom("Constant chime", SymptomSeverity.OBVIOUS),
        Symptom("No warning when unbuckled", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check buckle switch operation with scan tool",
        "Check wiring to buckle",
        "Try known good buckle",
    ],
    repair_actions=["Replace seatbelt buckle assembly"],
    repair_time_hours=0.5,
    parts_cost_low=40,
    parts_cost_high=150,
    relative_frequency=0.3,
)


BACKUP_CAMERA_FAILED = FailureMode(
    id="backup_camera_failed",
    name="Backup Camera Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="backup_camera",
    system_id="safety",
    immediate_effect="No or poor rearview image",
    cascade_effects=[
        "Screen shows no image or static",
        "Image distorted or dark",
    ],
    expected_dtcs=["C0246"],
    symptoms=[
        Symptom("No image when in reverse", SymptomSeverity.OBVIOUS),
        Symptom("Distorted or blurry image", SymptomSeverity.MODERATE),
        Symptom("Image flickers", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check camera lens for dirt/condensation",
        "Check wiring to camera",
        "Check fuse",
        "Test with another camera if possible",
    ],
    repair_actions=["Clean camera lens", "Replace backup camera", "Repair wiring"],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=300,
    relative_frequency=0.4,
)


PARKING_SENSOR_FAILED = FailureMode(
    id="parking_sensor_failed",
    name="Parking Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="parking_sensor",
    system_id="safety",
    immediate_effect="Parking sensor not detecting obstacles",
    cascade_effects=[
        "No warning when approaching objects",
        "Constant false alarm",
        "System may disable",
    ],
    expected_dtcs=["C0245", "U0300"],
    symptoms=[
        Symptom("Parking sensor warning stays on", SymptomSeverity.MODERATE),
        Symptom("No beep when near objects", SymptomSeverity.MODERATE),
        Symptom("Constant beeping (false alarm)", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check sensor face for dirt or paint",
        "Listen/feel for sensor click with ignition on",
        "Check wiring to sensor",
        "Scan for parking sensor codes",
    ],
    repair_actions=["Clean sensor", "Replace parking sensor"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "AIRBAG_SENSOR_FAILED",
    "AIRBAG_CLOCK_SPRING_FAILED",
    "SEATBELT_BUCKLE_SWITCH_FAILED",
    "BACKUP_CAMERA_FAILED",
    "PARKING_SENSOR_FAILED",
]
