"""
Suspension system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


SHOCK_WORN = FailureMode(
    id="shock_worn",
    name="Shock Absorber Worn",
    category=FailureCategory.MECHANICAL,
    component_id="shock_absorber",
    system_id="suspension",
    immediate_effect="Reduced damping of suspension",
    cascade_effects=["Excessive bounce", "Poor handling", "Tire wear"],
    symptoms=[Symptom("Bouncy ride", SymptomSeverity.MODERATE)],
    discriminating_tests=["Bounce test", "Visual inspection for leaks"],
    repair_actions=["Replace shocks/struts"],
    relative_frequency=0.6,
)


SPRING_BROKEN = FailureMode(
    id="spring_broken",
    name="Coil Spring Broken",
    category=FailureCategory.MECHANICAL,
    component_id="coil_spring",
    system_id="suspension",
    immediate_effect="Loss of spring support on one corner",
    symptoms=[Symptom("Vehicle sits low on one corner", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Measure ride height at all corners", "Visual inspection of spring coils"],
    repair_actions=["Replace coil spring (in pairs)"],
    relative_frequency=0.3,
)


CONTROL_ARM_BUSHING_WORN = FailureMode(
    id="control_arm_bushing_worn",
    name="Control Arm Bushing Worn",
    category=FailureCategory.MECHANICAL,
    component_id="control_arm",
    system_id="suspension",
    immediate_effect="Excessive movement in control arm",
    symptoms=[Symptom("Clunking noise over bumps", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check for bushing play with pry bar"],
    repair_actions=["Replace control arm or bushings"],
    relative_frequency=0.5,
)


WHEEL_BEARING_FAILING = FailureMode(
    id="wheel_bearing_failing",
    name="Wheel Bearing Failing",
    category=FailureCategory.MECHANICAL,
    component_id="wheel_bearing",
    system_id="suspension",
    immediate_effect="Friction and play in wheel bearing",
    symptoms=[Symptom("Humming noise at speed", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check for wheel play", "Listen for noise changes with steering"],
    repair_actions=["Replace wheel bearing/hub assembly"],
    relative_frequency=0.5,
)


STRUT_MOUNT_WORN = FailureMode(
    id="strut_mount_worn",
    name="Strut Mount Worn",
    category=FailureCategory.MECHANICAL,
    component_id="strut_mount",
    system_id="suspension",
    immediate_effect="Noise and reduced strut function",
    symptoms=[Symptom("Clunk when turning steering", SymptomSeverity.MODERATE)],
    discriminating_tests=["Check for play at strut tower while turning", "Inspect strut mount bearing"],
    repair_actions=["Replace strut mounts (usually with struts)"],
    relative_frequency=0.4,
)


SWAY_BAR_LINK_WORN = FailureMode(
    id="sway_bar_link_worn",
    name="Sway Bar Link Worn",
    category=FailureCategory.MECHANICAL,
    component_id="sway_bar_link",
    system_id="suspension",
    immediate_effect="Play in sway bar link causes noise",
    cascade_effects=[
        "Clunking noise over bumps",
        "Reduced body roll control",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Clunk over bumps", SymptomSeverity.MODERATE),
        Symptom("Rattle from front end", SymptomSeverity.MODERATE),
        Symptom("More body roll in turns", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Grab sway bar link and check for play",
        "Pry on link while watching for movement",
        "Visual inspection for torn boots",
    ],
    repair_actions=["Replace sway bar link(s)"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.6,
)


BALL_JOINT_WORN = FailureMode(
    id="ball_joint_worn",
    name="Ball Joint Worn",
    category=FailureCategory.MECHANICAL,
    component_id="ball_joint",
    system_id="suspension",
    immediate_effect="Play in ball joint affects steering and suspension geometry",
    cascade_effects=[
        "Clunking noise",
        "Wandering steering",
        "Tire wear",
        "Can separate completely (dangerous)",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Clunk over bumps", SymptomSeverity.MODERATE),
        Symptom("Steering wander", SymptomSeverity.MODERATE),
        Symptom("Uneven tire wear", SymptomSeverity.SUBTLE),
        Symptom("Clicking when turning", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check ball joint for play (wheel off ground)",
        "Pry on control arm with bar",
        "Check for torn dust boot",
        "Measure play with dial indicator if equipped with wear indicator",
    ],
    repair_actions=["Replace ball joint", "Alignment after"],
    repair_time_hours=1.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.5,
)


STRUT_LEAKING = FailureMode(
    id="strut_leaking",
    name="Strut Leaking",
    category=FailureCategory.LEAK,
    component_id="strut",
    system_id="suspension",
    immediate_effect="Strut loses damping ability",
    cascade_effects=[
        "Poor ride quality",
        "Bouncy ride",
        "Poor handling",
        "Excessive tire wear",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Bouncy ride", SymptomSeverity.MODERATE),
        Symptom("Oil visible on strut body", SymptomSeverity.OBVIOUS),
        Symptom("Nose dive when braking", SymptomSeverity.MODERATE),
        Symptom("Cupped tire wear", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection for oil on strut",
        "Bounce test - should stop in 1-2 bounces",
        "Check for misting on strut body",
    ],
    repair_actions=["Replace strut", "Consider complete strut assembly"],
    repair_time_hours=2.0,
    parts_cost_low=80,
    parts_cost_high=250,
    relative_frequency=0.5,
)


# Exports
__all__ = [
    "SHOCK_WORN",
    "SPRING_BROKEN",
    "CONTROL_ARM_BUSHING_WORN",
    "WHEEL_BEARING_FAILING",
    "STRUT_MOUNT_WORN",
    "SWAY_BAR_LINK_WORN",
    "BALL_JOINT_WORN",
    "STRUT_LEAKING",
]
