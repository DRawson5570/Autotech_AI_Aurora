"""
Starting system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


STARTER_MOTOR_FAILING = FailureMode(
    id="starter_motor_failing",
    name="Starter Motor Failing",
    category=FailureCategory.MECHANICAL,
    component_id="starter_motor",
    system_id="starting",
    
    immediate_effect="Starter spins slowly or intermittently",
    cascade_effects=[
        "Slow cranking",
        "No start",
        "Eventual complete failure",
    ],
    
    pid_effects=[
        PIDEffect("cranking_rpm", "low", "<150 RPM"),
        PIDEffect("battery_voltage", "drops_excessively", "<9V during crank"),
    ],
    
    expected_dtcs=["P0615", "P0616", "P0617"],
    
    symptoms=[
        Symptom("Slow cranking", SymptomSeverity.OBVIOUS),
        Symptom("Click but no crank", SymptomSeverity.SEVERE),
        Symptom("Grinding during start", SymptomSeverity.OBVIOUS),
        Symptom("Intermittent no-start", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Load test starter current draw",
        "Check voltage drop across starter circuit",
        "Tap starter and try again (worn brushes)",
        "Check battery and cables first",
    ],
    
    repair_actions=[
        "Replace starter motor",
        "Check battery cables",
        "Check flywheel/flexplate ring gear",
    ],
    repair_time_hours=1.5,
    parts_cost_low=100,
    parts_cost_high=350,
    relative_frequency=0.4,
)


STARTER_SOLENOID_FAILED = FailureMode(
    id="starter_solenoid_failed",
    name="Starter Solenoid Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="starter_solenoid",
    system_id="starting",
    
    immediate_effect="Solenoid doesn't engage starter gear",
    cascade_effects=[
        "Click but no crank",
        "No start condition",
    ],
    
    pid_effects=[],  # Usually no PIDs available
    
    expected_dtcs=["P0615", "P0616"],
    
    symptoms=[
        Symptom("Click when turning key, no crank", SymptomSeverity.SEVERE),
        Symptom("Starter spins but doesn't engage", SymptomSeverity.SEVERE),
        Symptom("Intermittent no-start", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Listen for solenoid click",
        "Check voltage at solenoid trigger wire",
        "Jump solenoid directly - does it engage?",
        "Check solenoid resistance",
    ],
    
    repair_actions=[
        "Replace starter (solenoid usually integral)",
        "Check ignition switch and neutral safety switch",
        "Check wiring",
    ],
    repair_time_hours=1.5,
    parts_cost_low=100,
    parts_cost_high=350,
    relative_frequency=0.3,
)


IGNITION_SWITCH_FAILED = FailureMode(
    id="ignition_switch_failed",
    name="Ignition Switch Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ignition_switch",
    system_id="starting",
    immediate_effect="Ignition switch doesn't complete circuits properly",
    cascade_effects=[
        "No crank",
        "No start",
        "Intermittent electrical cutout",
        "Accessories don't work in ACC position",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("No crank when turning key", SymptomSeverity.SEVERE),
        Symptom("Engine dies while driving", SymptomSeverity.SEVERE),
        Symptom("Key turns but nothing happens", SymptomSeverity.OBVIOUS),
        Symptom("Accessories intermittent", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check for power at switch outputs in each position",
        "Wiggle key while trying to start",
        "Check ignition switch connector",
    ],
    repair_actions=["Replace ignition switch"],
    repair_time_hours=1.5,
    parts_cost_low=30,
    parts_cost_high=150,
    relative_frequency=0.3,
)


GLOW_PLUG_FAILED = FailureMode(
    id="glow_plug_failed",
    name="Glow Plug Failed (Diesel)",
    category=FailureCategory.ELECTRICAL,
    component_id="glow_plug",
    system_id="starting",
    immediate_effect="Cylinder not pre-heated for cold start",
    cascade_effects=[
        "Hard starting in cold weather",
        "Rough idle when cold",
        "White smoke on startup",
    ],
    expected_dtcs=["P0380", "P0381", "P0670", "P0671", "P0672", "P0673", "P0674"],
    symptoms=[
        Symptom("Hard starting when cold", SymptomSeverity.MODERATE),
        Symptom("Glow plug light stays on", SymptomSeverity.OBVIOUS),
        Symptom("White smoke on cold start", SymptomSeverity.MODERATE),
        Symptom("Rough idle when cold", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check glow plug resistance (typically 0.5-2 ohms)",
        "Check glow plug current draw",
        "Scan for glow plug circuit codes",
    ],
    repair_actions=["Replace failed glow plug(s)"],
    repair_time_hours=1.5,
    parts_cost_low=15,
    parts_cost_high=50,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "STARTER_MOTOR_FAILING",
    "STARTER_SOLENOID_FAILED",
    "IGNITION_SWITCH_FAILED",
    "GLOW_PLUG_FAILED",
]
