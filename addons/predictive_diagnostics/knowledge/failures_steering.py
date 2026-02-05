"""
Steering system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


PS_PUMP_FAILING = FailureMode(
    id="ps_pump_failing",
    name="Power Steering Pump Failing",
    category=FailureCategory.MECHANICAL,
    component_id="ps_pump",
    system_id="steering",
    immediate_effect="Reduced hydraulic pressure for steering assist",
    cascade_effects=["Increased steering effort", "Whining noise", "Fluid leak"],
    symptoms=[Symptom("Whining noise when turning", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check PS fluid level", "Pressure test PS system"],
    repair_actions=["Replace power steering pump"],
    relative_frequency=0.5,
)


RACK_WEAR = FailureMode(
    id="rack_wear",
    name="Steering Rack Wear",
    category=FailureCategory.MECHANICAL,
    component_id="steering_rack",
    system_id="steering",
    immediate_effect="Excessive play in steering",
    cascade_effects=["Vague steering feel", "Wandering at highway speed"],
    symptoms=[Symptom("Loose steering", SymptomSeverity.MODERATE)],
    discriminating_tests=["Check steering free play", "Inspect rack boots"],
    repair_actions=["Replace steering rack"],
    relative_frequency=0.4,
)


STEERING_ANGLE_SENSOR_FAILED = FailureMode(
    id="steering_angle_sensor_failed",
    name="Steering Angle Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="steering_angle_sensor",
    system_id="steering",
    immediate_effect="No steering angle signal to stability control",
    expected_dtcs=["C0455", "C0710"],
    symptoms=[Symptom("Stability control light on", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check steering angle sensor output with scan tool", "Verify sensor calibration"],
    repair_actions=["Replace/recalibrate steering angle sensor"],
    relative_frequency=0.3,
)


EPS_MOTOR_FAILING = FailureMode(
    id="eps_motor_failing",
    name="Electric Power Steering Motor Failing",
    category=FailureCategory.ELECTRICAL,
    component_id="eps_motor",
    system_id="steering",
    immediate_effect="Intermittent or no power steering assist",
    expected_dtcs=["C0545", "C0550"],
    symptoms=[Symptom("Intermittent heavy steering", SymptomSeverity.SEVERE)],
    discriminating_tests=["Check EPS motor current draw", "Monitor assist torque vs input with scan tool"],
    repair_actions=["Replace EPS motor/module"],
    relative_frequency=0.3,
)


TIE_ROD_WORN = FailureMode(
    id="tie_rod_worn",
    name="Tie Rod End Worn",
    category=FailureCategory.MECHANICAL,
    component_id="tie_rod",
    system_id="steering",
    immediate_effect="Play in steering linkage",
    symptoms=[Symptom("Clunking over bumps", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Wiggle test on front wheels"],
    repair_actions=["Replace tie rod ends", "Perform alignment"],
    relative_frequency=0.5,
)


# Exports
__all__ = [
    "PS_PUMP_FAILING",
    "RACK_WEAR",
    "STEERING_ANGLE_SENSOR_FAILED",
    "EPS_MOTOR_FAILING",
    "TIE_ROD_WORN",
]
