"""
Brakes system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


ABS_MODULE_FAILED = FailureMode(
    id="abs_module_failed",
    name="ABS Control Module Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="abs_module",
    system_id="brakes",
    
    immediate_effect="ABS system disabled",
    cascade_effects=[
        "ABS light on",
        "No anti-lock function",
        "May affect stability control",
    ],
    
    pid_effects=[],
    
    expected_dtcs=["C0265", "U0121", "C0550"],
    
    symptoms=[
        Symptom("ABS warning light", SymptomSeverity.OBVIOUS),
        Symptom("Traction control light", SymptomSeverity.OBVIOUS),
        Symptom("Wheels lock during hard braking", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Scan for ABS codes",
        "Check power and ground to module",
        "Check CAN communication",
        "Check for internal faults",
    ],
    
    repair_actions=[
        "Replace ABS module",
        "Check wiring and connectors",
        "Bleed ABS system",
    ],
    repair_time_hours=2.0,
    parts_cost_low=300,
    parts_cost_high=800,
    relative_frequency=0.2,
)


ABS_PUMP_MOTOR_FAILED = FailureMode(
    id="abs_pump_motor_failed",
    name="ABS Pump Motor Failed",
    category=FailureCategory.MECHANICAL,
    component_id="abs_pump",
    system_id="brakes",
    
    immediate_effect="Can't build ABS pressure",
    cascade_effects=[
        "ABS disabled",
        "Longer ABS activation buzz",
        "Pump runs continuously",
    ],
    
    pid_effects=[],
    
    expected_dtcs=["C0110", "C0265"],
    
    symptoms=[
        Symptom("ABS light on", SymptomSeverity.OBVIOUS),
        Symptom("Pump runs excessively or not at all", SymptomSeverity.OBVIOUS),
        Symptom("Grinding noise from ABS unit", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Listen for pump operation during ABS activation",
        "Check pump motor current draw",
        "Check for seized motor",
    ],
    
    repair_actions=[
        "Replace ABS modulator assembly",
        "Check brake fluid for contamination",
    ],
    repair_time_hours=2.5,
    parts_cost_low=400,
    parts_cost_high=1200,
    relative_frequency=0.15,
)


WHEEL_SPEED_SENSOR_FAILED = FailureMode(
    id="wheel_speed_sensor_failed",
    name="Wheel Speed Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="wheel_speed_sensor",
    system_id="brakes",
    
    immediate_effect="ABS can't monitor wheel speed",
    cascade_effects=[
        "ABS disabled for that wheel",
        "May disable traction control",
        "May affect speedometer",
    ],
    
    pid_effects=[
        PIDEffect("wheel_speed", "erratic", "Zero or erratic"),
    ],
    
    expected_dtcs=["C0035", "C0040", "C0045", "C0050", "C0055"],
    
    symptoms=[
        Symptom("ABS light on", SymptomSeverity.OBVIOUS),
        Symptom("Traction control disabled", SymptomSeverity.OBVIOUS),
        Symptom("Speedometer erratic (if VSS derived)", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Check wheel speed sensor signal with scope",
        "Check sensor resistance (usually 800-2000 ohms)",
        "Check sensor gap to tone ring",
        "Inspect tone ring for damage",
    ],
    
    repair_actions=[
        "Replace wheel speed sensor",
        "Check wiring and connector",
        "Inspect tone ring",
        "Clean sensor tip",
    ],
    repair_time_hours=0.75,
    parts_cost_low=25,
    parts_cost_high=80,
    relative_frequency=0.5,
)


BRAKE_PADS_WORN = FailureMode(
    id="brake_pads_worn",
    name="Brake Pads Worn",
    category=FailureCategory.MECHANICAL,
    component_id="brake_pads",
    system_id="brakes",
    
    immediate_effect="Reduced braking material",
    cascade_effects=[
        "Reduced braking performance",
        "Rotor damage if metal-to-metal",
        "Brake fade",
        "Increased stopping distance",
    ],
    
    pid_effects=[],
    
    expected_dtcs=[],  # Usually no DTCs unless equipped with wear sensors
    
    symptoms=[
        Symptom("Squealing when braking", SymptomSeverity.OBVIOUS),
        Symptom("Grinding noise (metal-to-metal)", SymptomSeverity.SEVERE),
        Symptom("Brake warning light (if equipped)", SymptomSeverity.OBVIOUS),
        Symptom("Increased stopping distance", SymptomSeverity.MODERATE),
        Symptom("Pedal feels different", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Visual inspection through wheel",
        "Measure pad thickness - minimum 2-3mm",
        "Check for wear indicator contact",
        "Inspect rotors for scoring",
    ],
    
    repair_actions=[
        "Replace brake pads",
        "Inspect/resurface rotors",
        "Check brake fluid level",
        "Bed in new pads properly",
    ],
    relative_frequency=0.8,
)


BRAKE_ROTOR_WARPED = FailureMode(
    id="brake_rotor_warped",
    name="Brake Rotor Warped",
    category=FailureCategory.MECHANICAL,
    component_id="brake_rotor",
    system_id="brakes",
    
    immediate_effect="Uneven braking surface",
    cascade_effects=[
        "Pulsation during braking",
        "Vibration in steering wheel",
        "Premature pad wear",
    ],
    
    pid_effects=[],
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Brake pulsation/vibration", SymptomSeverity.OBVIOUS),
        Symptom("Steering wheel shake when braking", SymptomSeverity.OBVIOUS),
        Symptom("Pedal pulsation", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Measure rotor runout with dial indicator - max 0.002\"",
        "Measure rotor thickness variation - max 0.0005\"",
        "Check for hot spots or discoloration",
    ],
    
    repair_actions=[
        "Machine rotors if above minimum thickness",
        "Replace rotors if below minimum or cracked",
        "Replace pads at same time",
    ],
    relative_frequency=0.5,
)


ABS_SENSOR_FAILED = FailureMode(
    id="abs_sensor_failed",
    name="ABS Wheel Speed Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="abs_sensor",
    system_id="brakes",
    
    immediate_effect="No wheel speed signal from affected wheel",
    cascade_effects=[
        "ABS disabled",
        "Traction control disabled",
        "Stability control disabled",
    ],
    
    pid_effects=[
        PIDEffect("wheel_speed", "erratic", "One wheel different from others"),
    ],
    
    expected_dtcs=["C0035", "C0040", "C0045", "C0050", "C0221", "C0222", "C0223", "C0224"],
    
    symptoms=[
        Symptom("ABS warning light on", SymptomSeverity.OBVIOUS),
        Symptom("Traction control light on", SymptomSeverity.OBVIOUS),
        Symptom("ABS not functioning", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Read wheel speed PIDs - compare all four wheels",
        "Check sensor resistance (typically 800-2000 ohms)",
        "Check sensor gap and tone ring condition",
        "Inspect wiring for damage",
    ],
    
    repair_actions=[
        "Replace wheel speed sensor",
        "Check tone ring for damage",
        "Repair wiring if damaged",
        "Clean sensor mounting area",
    ],
    relative_frequency=0.5,
)


BRAKE_CALIPER_STICKING = FailureMode(
    id="brake_caliper_sticking",
    name="Brake Caliper Sticking/Seized",
    category=FailureCategory.STUCK,
    component_id="brake_caliper",
    system_id="brakes",
    
    immediate_effect="Caliper doesn't release properly",
    cascade_effects=[
        "Constant brake drag",
        "Excessive heat buildup",
        "Premature pad/rotor wear",
        "Reduced fuel economy",
        "Vehicle pulls to one side",
    ],
    
    pid_effects=[],
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Vehicle pulls to one side when braking", SymptomSeverity.OBVIOUS),
        Symptom("One wheel hotter than others", SymptomSeverity.MODERATE),
        Symptom("Burning smell from wheel area", SymptomSeverity.OBVIOUS),
        Symptom("Uneven pad wear", SymptomSeverity.MODERATE),
        Symptom("Car drags/slow to coast", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Feel wheel temp after driving - one significantly hotter",
        "Jack up and spin wheel - should rotate freely",
        "Check brake hose for internal collapse",
        "Inspect caliper slides for corrosion",
    ],
    
    repair_actions=[
        "Clean and lubricate caliper slides",
        "Replace caliper if piston seized",
        "Check brake hose for collapse",
        "Replace pads and rotors if damaged",
    ],
    relative_frequency=0.4,
)


MASTER_CYLINDER_FAILING = FailureMode(
    id="master_cylinder_failing",
    name="Brake Master Cylinder Failing",
    category=FailureCategory.LEAK,
    component_id="master_cylinder",
    system_id="brakes",
    
    immediate_effect="Internal seal failure causes brake fluid bypass",
    cascade_effects=[
        "Sinking brake pedal",
        "Soft pedal",
        "Loss of braking (severe)",
    ],
    
    pid_effects=[],
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Brake pedal sinks slowly when held", SymptomSeverity.SEVERE),
        Symptom("Soft/spongy brake pedal", SymptomSeverity.MODERATE),
        Symptom("Low brake fluid level", SymptomSeverity.MODERATE),
        Symptom("Pedal goes to floor", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Hold firm pressure on pedal - should not sink",
        "Check for external leaks at master cylinder",
        "Check for internal bypass - pedal sinks with pressure held",
        "Inspect brake fluid level",
    ],
    
    repair_actions=[
        "Replace master cylinder",
        "Bleed entire brake system",
        "Bench bleed new master cylinder before install",
    ],
    relative_frequency=0.3,
)


BRAKE_FLUID_CONTAMINATED = FailureMode(
    id="brake_fluid_contaminated",
    name="Brake Fluid Contaminated",
    category=FailureCategory.DRIFT,
    component_id="brake_fluid",
    system_id="brakes",
    immediate_effect="Contaminated fluid damages seals and components",
    cascade_effects=[
        "Swelling of rubber seals",
        "Master cylinder failure",
        "Caliper seal failure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Soft or spongy brake pedal", SymptomSeverity.MODERATE),
        Symptom("Swollen master cylinder cap", SymptomSeverity.SUBTLE),
        Symptom("Brake drag", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check brake fluid color (should be clear/amber)",
        "Check for petroleum smell",
        "Inspect rubber seals for swelling",
    ],
    repair_actions=["Flush entire brake system", "Replace all rubber components"],
    repair_time_hours=3.0,
    parts_cost_low=50,
    parts_cost_high=500,
    relative_frequency=0.2,
)


BRAKE_HOSE_DETERIORATED = FailureMode(
    id="brake_hose_deteriorated",
    name="Brake Hose Deteriorated",
    category=FailureCategory.MECHANICAL,
    component_id="brake_hose",
    system_id="brakes",
    immediate_effect="Internal hose collapse restricts fluid flow",
    cascade_effects=[
        "Brake drags on one wheel",
        "Possible brake pull",
        "Hose may burst externally",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("One brake drags after releasing pedal", SymptomSeverity.MODERATE),
        Symptom("Wheel hot after driving", SymptomSeverity.OBVIOUS),
        Symptom("Vehicle pulls under braking", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Open bleeder after drag - does brake release?",
        "Inspect hoses for cracks or bulges",
        "Check caliper pistons retract when hose loosened",
    ],
    repair_actions=["Replace brake hose"],
    repair_time_hours=0.5,
    parts_cost_low=15,
    parts_cost_high=50,
    relative_frequency=0.3,
)


PARKING_BRAKE_STUCK = FailureMode(
    id="parking_brake_stuck",
    name="Parking Brake Stuck/Frozen",
    category=FailureCategory.STUCK,
    component_id="parking_brake",
    system_id="brakes",
    immediate_effect="Parking brake won't release (or won't hold)",
    cascade_effects=[
        "Rear brake drag",
        "Burning smell",
        "Or vehicle rolls when parked",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Vehicle won't move freely", SymptomSeverity.OBVIOUS),
        Symptom("Rear brakes dragging", SymptomSeverity.MODERATE),
        Symptom("Parking brake pedal/lever stuck", SymptomSeverity.OBVIOUS),
        Symptom("Vehicle rolls on incline when parked", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Check cable for corrosion or damage",
        "Check parking brake shoes/pads",
        "Check electric parking brake motor (if equipped)",
    ],
    repair_actions=["Lubricate or replace parking brake cable", "Adjust parking brake", "Replace EPB motor"],
    repair_time_hours=1.0,
    parts_cost_low=30,
    parts_cost_high=200,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "ABS_MODULE_FAILED",
    "ABS_PUMP_MOTOR_FAILED",
    "WHEEL_SPEED_SENSOR_FAILED",
    "BRAKE_PADS_WORN",
    "BRAKE_ROTOR_WARPED",
    "ABS_SENSOR_FAILED",
    "BRAKE_CALIPER_STICKING",
    "MASTER_CYLINDER_FAILING",
    "BRAKE_FLUID_CONTAMINATED",
    "BRAKE_HOSE_DETERIORATED",
    "PARKING_BRAKE_STUCK",
]
