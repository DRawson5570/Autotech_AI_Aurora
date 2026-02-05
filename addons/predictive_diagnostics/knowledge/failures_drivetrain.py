"""
Drivetrain system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


CV_JOINT_WORN = FailureMode(
    id="cv_joint_worn",
    name="CV Joint Worn",
    category=FailureCategory.MECHANICAL,
    component_id="cv_joint",
    system_id="drivetrain",
    immediate_effect="Play in CV joint allows clicking and vibration",
    cascade_effects=[
        "Clicking noise on turns",
        "Vibration during acceleration",
        "Eventually complete failure/separation",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Clicking noise on sharp turns", SymptomSeverity.OBVIOUS),
        Symptom("Vibration on acceleration", SymptomSeverity.MODERATE),
        Symptom("Grease splattered around wheel/fender", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Listen for clicking during low-speed turns",
        "Inspect CV boot for tears",
        "Grab axle and check for play",
    ],
    repair_actions=["Replace CV axle assembly", "Replace CV boot if joint OK"],
    repair_time_hours=1.5,
    parts_cost_low=80,
    parts_cost_high=250,
    relative_frequency=0.6,
)


CV_BOOT_TORN = FailureMode(
    id="cv_boot_torn",
    name="CV Boot Torn",
    category=FailureCategory.LEAK,
    component_id="cv_boot",
    system_id="drivetrain",
    immediate_effect="Grease leaks out, dirt/water gets in",
    cascade_effects=[
        "CV joint contamination",
        "Accelerated CV joint wear",
        "Eventually clicking and failure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Grease on wheel or fender", SymptomSeverity.OBVIOUS),
        Symptom("No noise yet if caught early", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Visual inspection of CV boots",
        "Look for grease splatter",
    ],
    repair_actions=["Replace CV boot", "Or replace entire axle if joint damaged"],
    repair_time_hours=1.5,
    parts_cost_low=30,
    parts_cost_high=80,
    relative_frequency=0.5,
)


DIFFERENTIAL_NOISE = FailureMode(
    id="differential_noise",
    name="Differential Worn/Noisy",
    category=FailureCategory.MECHANICAL,
    component_id="differential",
    system_id="drivetrain",
    immediate_effect="Worn gears or bearings cause noise",
    cascade_effects=[
        "Whining or howling noise",
        "May progress to complete failure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Whining noise on acceleration", SymptomSeverity.MODERATE),
        Symptom("Howling noise on deceleration", SymptomSeverity.MODERATE),
        Symptom("Rumbling from rear/center", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Listen for noise changes on accel vs decel",
        "Check differential fluid level and condition",
        "Check for metal in fluid",
    ],
    repair_actions=["Replace differential fluid", "Rebuild or replace differential"],
    repair_time_hours=4.0,
    parts_cost_low=200,
    parts_cost_high=1500,
    relative_frequency=0.3,
)


TRANSFER_CASE_FAILURE = FailureMode(
    id="transfer_case_failure",
    name="Transfer Case Failure",
    category=FailureCategory.MECHANICAL,
    component_id="transfer_case",
    system_id="drivetrain",
    immediate_effect="4WD/AWD system does not engage or disengage properly",
    cascade_effects=[
        "Grinding or binding on turns",
        "No 4WD engagement",
        "Stuck in 4WD",
    ],
    expected_dtcs=["C0327", "C0387"],
    symptoms=[
        Symptom("4WD light flashing or on", SymptomSeverity.OBVIOUS),
        Symptom("Grinding noise", SymptomSeverity.OBVIOUS),
        Symptom("Binding on tight turns", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check transfer case fluid level and condition",
        "Test 4WD engagement with scan tool",
        "Check encoder motor operation",
    ],
    repair_actions=["Replace fluid", "Replace encoder motor", "Rebuild transfer case"],
    repair_time_hours=3.0,
    parts_cost_low=150,
    parts_cost_high=1200,
    relative_frequency=0.3,
)


DRIVESHAFT_U_JOINT_WORN = FailureMode(
    id="driveshaft_u_joint_worn",
    name="Driveshaft U-Joint Worn",
    category=FailureCategory.MECHANICAL,
    component_id="driveshaft",
    system_id="drivetrain",
    immediate_effect="Play in U-joint causes vibration and clunk",
    cascade_effects=[
        "Vibration at speed",
        "Clunk on shift between drive/reverse",
        "Can eventually separate completely",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Vibration at highway speed", SymptomSeverity.MODERATE),
        Symptom("Clunk when shifting to drive/reverse", SymptomSeverity.OBVIOUS),
        Symptom("Squeaking from driveshaft area", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check U-joints for play",
        "Grab driveshaft and rotate - should be no play",
        "Visual inspection for rust/lack of grease",
    ],
    repair_actions=["Replace U-joints", "Replace driveshaft if needed"],
    repair_time_hours=1.0,
    parts_cost_low=25,
    parts_cost_high=100,
    relative_frequency=0.4,
)


AXLE_BEARING_FAILURE = FailureMode(
    id="axle_bearing_failure",
    name="Axle Bearing Failure",
    category=FailureCategory.MECHANICAL,
    component_id="axle_bearing",
    system_id="drivetrain",
    immediate_effect="Worn bearing causes noise and play",
    cascade_effects=[
        "Humming/roaring noise",
        "Play in axle",
        "Eventually seizes",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Humming noise from wheel area", SymptomSeverity.MODERATE),
        Symptom("Noise changes with vehicle speed", SymptomSeverity.MODERATE),
        Symptom("Play felt at wheel", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Lift vehicle and spin wheel - listen for roughness",
        "Check for play by rocking wheel top-to-bottom",
        "Noise may change when turning (loads/unloads bearing)",
    ],
    repair_actions=["Replace axle bearing", "Check seal and fluid"],
    repair_time_hours=2.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "CV_JOINT_WORN",
    "CV_BOOT_TORN",
    "DIFFERENTIAL_NOISE",
    "TRANSFER_CASE_FAILURE",
    "DRIVESHAFT_U_JOINT_WORN",
    "AXLE_BEARING_FAILURE",
]
