"""
Transmission system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


TRANSMISSION_FLUID_LOW = FailureMode(
    id="trans_fluid_low",
    name="Transmission Fluid Low/Burnt",
    category=FailureCategory.LEAK,
    component_id="transmission",
    system_id="transmission",
    
    immediate_effect="Insufficient fluid for proper operation",
    cascade_effects=[
        "Slipping",
        "Delayed engagement",
        "Overheating",
        "Internal damage",
    ],
    
    pid_effects=[
        PIDEffect("trans_temp", "high", ">200°F"),
    ],
    
    expected_dtcs=["P0710", "P0711", "P0712", "P0713", "P0218"],
    
    symptoms=[
        Symptom("Transmission slipping", SymptomSeverity.OBVIOUS),
        Symptom("Delayed engagement", SymptomSeverity.MODERATE),
        Symptom("Burnt fluid smell", SymptomSeverity.OBVIOUS),
        Symptom("Fluid puddle under vehicle", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Check fluid level and condition",
        "Fluid should be red/pink, not brown/black",
        "Fluid should not smell burnt",
        "Check for leaks",
    ],
    
    repair_actions=[
        "Add correct fluid if low",
        "Repair leak source",
        "Flush and refill if burnt",
        "May need rebuild if damage occurred",
    ],
    relative_frequency=0.5,
)


TORQUE_CONVERTER_SHUDDER = FailureMode(
    id="torque_converter_shudder",
    name="Torque Converter Clutch Shudder",
    category=FailureCategory.MECHANICAL,
    component_id="torque_converter",
    system_id="transmission",
    
    immediate_effect="TCC doesn't engage smoothly",
    cascade_effects=[
        "Vibration during lockup",
        "Premature wear",
        "Driver discomfort",
    ],
    
    pid_effects=[
        PIDEffect("tcc_slip", "erratic", "Fluctuating during lockup"),
    ],
    
    expected_dtcs=["P0740", "P0741", "P0742", "P0743", "P0744"],
    
    symptoms=[
        Symptom("Shudder/vibration at highway speeds", SymptomSeverity.OBVIOUS),
        Symptom("Shudder when TCC applies (40-60 mph)", SymptomSeverity.OBVIOUS),
        Symptom("Feels like driving over rumble strips", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Drive at TCC engagement speed (usually 40-50 mph)",
        "Disable TCC with scan tool - does shudder stop?",
        "Check fluid condition",
        "Check for TCC-related DTCs",
    ],
    
    repair_actions=[
        "Try transmission fluid flush with friction modifier",
        "Replace torque converter if flush fails",
        "May need transmission rebuild",
    ],
    relative_frequency=0.4,
)


SHIFT_SOLENOID_FAILED = FailureMode(
    id="shift_solenoid_failed",
    name="Shift Solenoid Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="shift_solenoid",
    system_id="transmission",
    
    immediate_effect="Transmission stuck in wrong gear or won't shift",
    cascade_effects=[
        "Harsh shifts",
        "No shift",
        "Limp mode",
        "Transmission damage if driven",
    ],
    
    pid_effects=[
        PIDEffect("trans_gear", "stuck", "Won't change from commanded"),
    ],
    
    expected_dtcs=["P0750", "P0755", "P0760", "P0765", "P0770", "P0975", "P0976"],
    
    symptoms=[
        Symptom("Won't shift out of gear", SymptomSeverity.SEVERE),
        Symptom("Harsh/late shifts", SymptomSeverity.OBVIOUS),
        Symptom("Transmission limp mode", SymptomSeverity.SEVERE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Check DTCs for specific solenoid",
        "Command solenoid with scan tool",
        "Check solenoid resistance (typically 10-30 ohms)",
        "Check wiring and connector",
    ],
    
    repair_actions=[
        "Replace failed solenoid",
        "Check wiring to solenoid",
        "Change fluid and filter",
    ],
    relative_frequency=0.4,
)


VALVE_BODY_FAILURE = FailureMode(
    id="valve_body_failure",
    name="Valve Body Failure/Wear",
    category=FailureCategory.MECHANICAL,
    component_id="valve_body",
    system_id="transmission",
    
    immediate_effect="Hydraulic pressure routing problems",
    cascade_effects=[
        "Erratic or harsh shifting",
        "Delayed engagement",
        "Slipping between gears",
        "Multiple gear-related DTCs",
    ],
    
    pid_effects=[
        PIDEffect("line_pressure", "erratic", "Fluctuating or incorrect"),
        PIDEffect("shift_time", "high", "Longer than normal"),
    ],
    
    expected_dtcs=["P0730", "P0731", "P0732", "P0733", "P0734", "P0780", "P0781", "P0782"],
    
    symptoms=[
        Symptom("Harsh shifts in multiple gears", SymptomSeverity.OBVIOUS),
        Symptom("Slipping between gears", SymptomSeverity.OBVIOUS),
        Symptom("Delayed gear engagement", SymptomSeverity.MODERATE),
        Symptom("Multiple shift-related codes", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Check line pressure with gauge",
        "Check shift quality in all gears",
        "Scan for multiple shift DTCs",
        "Check fluid for metal contamination",
    ],
    
    repair_actions=[
        "Replace or rebuild valve body",
        "Check for debris in valve body",
        "Flush transmission cooler lines",
    ],
    repair_time_hours=4.0,
    parts_cost_low=200,
    parts_cost_high=600,
    relative_frequency=0.3,
)


TCC_STUCK_OFF = FailureMode(
    id="tcc_stuck_off",
    name="Torque Converter Clutch Stuck Off",
    category=FailureCategory.STUCK,
    component_id="torque_converter",
    system_id="transmission",
    
    immediate_effect="TCC won't engage/lock",
    cascade_effects=[
        "Engine RPM stays higher at highway speeds",
        "Reduced fuel economy",
        "Transmission overheating",
        "Excessive slip",
    ],
    
    pid_effects=[
        PIDEffect("tcc_slip", "high", ">100 RPM at cruise"),
        PIDEffect("trans_temp", "high", ">200°F"),
    ],
    
    expected_dtcs=["P0741", "P0740"],
    
    symptoms=[
        Symptom("Higher than normal RPM at highway speed", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("Transmission running hot", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Monitor TCC command vs actual engagement",
        "Check TCC solenoid resistance",
        "Check wiring to TCC solenoid",
        "Check for worn TCC friction material",
    ],
    
    repair_actions=[
        "Replace TCC solenoid",
        "Check wiring",
        "May need torque converter replacement",
    ],
    relative_frequency=0.35,
)


TCC_STUCK_ON = FailureMode(
    id="tcc_stuck_on",
    name="Torque Converter Clutch Stuck On",
    category=FailureCategory.STUCK,
    component_id="torque_converter",
    system_id="transmission",
    
    immediate_effect="TCC won't release",
    cascade_effects=[
        "Engine stalls when coming to a stop",
        "No torque multiplication at launch",
        "Poor acceleration from stop",
    ],
    
    pid_effects=[
        PIDEffect("tcc_slip", "low", "0 RPM even at stop"),
    ],
    
    expected_dtcs=["P0742"],
    
    symptoms=[
        Symptom("Engine stalls when stopping", SymptomSeverity.SEVERE),
        Symptom("Vehicle bucks/surges at low speed", SymptomSeverity.OBVIOUS),
        Symptom("Poor acceleration from stop", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Does engine stall when coming to stop with trans in gear?",
        "Check TCC solenoid command vs actual",
        "Check for binding in TCC apply circuit",
    ],
    
    repair_actions=[
        "Replace TCC solenoid",
        "Check hydraulic circuit",
        "May need torque converter replacement",
    ],
    relative_frequency=0.2,
)


TRANS_SPEED_SENSOR_FAILED = FailureMode(
    id="trans_speed_sensor_failed",
    name="Transmission Speed Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="speed_sensor",
    system_id="transmission",
    
    immediate_effect="ECU can't determine vehicle or turbine speed",
    cascade_effects=[
        "Incorrect shift points",
        "Speedometer malfunction",
        "Erratic shifting",
        "Limp mode",
    ],
    
    pid_effects=[
        PIDEffect("vss", "erratic", "Erratic or zero"),
        PIDEffect("input_speed", "erratic", "Erratic or zero"),
    ],
    
    expected_dtcs=["P0715", "P0716", "P0717", "P0720", "P0721", "P0722"],
    
    symptoms=[
        Symptom("Speedometer not working", SymptomSeverity.OBVIOUS),
        Symptom("Harsh/incorrect shift points", SymptomSeverity.OBVIOUS),
        Symptom("Transmission limp mode", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Check speed sensor signal with scope",
        "Check sensor resistance",
        "Check wiring and connector",
        "Check tone ring for damage",
    ],
    
    repair_actions=[
        "Replace speed sensor",
        "Check wiring",
        "Inspect tone ring",
    ],
    repair_time_hours=1.0,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


VSS_SENSOR_FAILED = FailureMode(
    id="vss_sensor_failed",
    name="Vehicle Speed Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="vss_sensor",
    system_id="transmission",
    immediate_effect="PCM/TCM cannot read vehicle speed",
    cascade_effects=[
        "Speedometer not working",
        "Transmission shift problems",
        "Cruise control inoperative",
    ],
    expected_dtcs=["P0500", "P0501", "P0502", "P0503"],
    symptoms=[
        Symptom("Speedometer not working", SymptomSeverity.OBVIOUS),
        Symptom("Erratic shifting", SymptomSeverity.MODERATE),
        Symptom("Cruise control inoperative", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check for speed signal while driving (scan tool)",
        "Check sensor resistance and wiring",
        "Check for damaged reluctor/tone ring",
    ],
    repair_actions=["Replace VSS", "Check wiring and connector"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


TRANS_FLUID_CONTAMINATED = FailureMode(
    id="trans_fluid_contaminated",
    name="Transmission Fluid Contaminated",
    category=FailureCategory.DRIFT,
    component_id="transmission",
    system_id="transmission",
    immediate_effect="Degraded fluid causes poor lubrication and shift quality",
    cascade_effects=[
        "Harsh shifts",
        "Slipping",
        "Internal wear",
    ],
    expected_dtcs=["P0700", "P0730", "P0731", "P0732"],
    symptoms=[
        Symptom("Harsh or delayed shifts", SymptomSeverity.MODERATE),
        Symptom("Burnt smell from fluid", SymptomSeverity.MODERATE),
        Symptom("Dark/black fluid", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check fluid color and smell",
        "Check for debris on dipstick",
        "Inspect fluid on white paper towel",
    ],
    repair_actions=["Flush transmission", "Replace filter", "May need rebuild if damage done"],
    repair_time_hours=2.0,
    parts_cost_low=100,
    parts_cost_high=300,
    relative_frequency=0.5,
)


TRANS_MOUNT_WORN = FailureMode(
    id="trans_mount_worn",
    name="Transmission Mount Worn",
    category=FailureCategory.MECHANICAL,
    component_id="trans_mount",
    system_id="transmission",
    immediate_effect="Excessive transmission movement",
    cascade_effects=[
        "Clunk on shift",
        "Vibration",
        "Possible drivetrain damage",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Clunk when shifting to drive/reverse", SymptomSeverity.MODERATE),
        Symptom("Vibration at idle", SymptomSeverity.MODERATE),
        Symptom("Visible transmission movement", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of mount",
        "Check for torn rubber",
        "Put in gear and watch for excessive movement",
    ],
    repair_actions=["Replace transmission mount"],
    repair_time_hours=1.0,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


TRANS_INPUT_SHAFT_SEAL_LEAK = FailureMode(
    id="trans_input_shaft_seal_leak",
    name="Transmission Input Shaft Seal Leak",
    category=FailureCategory.LEAK,
    component_id="trans_seal",
    system_id="transmission",
    immediate_effect="Fluid leaks from front of transmission",
    cascade_effects=[
        "Low fluid level",
        "Potential clutch contamination (manual)",
        "Eventually leads to transmission damage",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Fluid leak between engine and transmission", SymptomSeverity.OBVIOUS),
        Symptom("Clutch slipping (manual trans)", SymptomSeverity.MODERATE),
        Symptom("Low fluid level", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection at bell housing",
        "Check fluid level",
        "Clean area and re-check after driving",
    ],
    repair_actions=["Replace input shaft seal", "Requires trans removal in most cases"],
    repair_time_hours=4.0,
    parts_cost_low=20,
    parts_cost_high=50,
    relative_frequency=0.3,
)


CLUTCH_WORN = FailureMode(
    id="clutch_worn",
    name="Clutch Worn (Manual Trans)",
    category=FailureCategory.MECHANICAL,
    component_id="clutch",
    system_id="transmission",
    immediate_effect="Clutch disc material worn thin",
    cascade_effects=[
        "Clutch slips under load",
        "High engagement point",
        "Eventually no drive at all",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Clutch slips on acceleration", SymptomSeverity.OBVIOUS),
        Symptom("RPM rises but speed doesn't", SymptomSeverity.OBVIOUS),
        Symptom("Burning smell", SymptomSeverity.MODERATE),
        Symptom("High engagement point", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Slip test: start in 4th gear, release clutch slowly",
        "Check clutch fluid level",
        "Feel for grab point in pedal travel",
    ],
    repair_actions=["Replace clutch kit (disc, pressure plate, throw-out bearing)"],
    repair_time_hours=5.0,
    parts_cost_low=200,
    parts_cost_high=500,
    relative_frequency=0.5,
)


CLUTCH_HYDRAULIC_FAILURE = FailureMode(
    id="clutch_hydraulic_failure",
    name="Clutch Hydraulic System Failure",
    category=FailureCategory.LEAK,
    component_id="clutch_hydraulic",
    system_id="transmission",
    immediate_effect="Cannot disengage clutch properly",
    cascade_effects=[
        "Clutch won't fully release",
        "Grinding gears",
        "Cannot shift",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Soft or spongy clutch pedal", SymptomSeverity.MODERATE),
        Symptom("Clutch pedal goes to floor", SymptomSeverity.OBVIOUS),
        Symptom("Cannot get into gear", SymptomSeverity.SEVERE),
        Symptom("Fluid leak at master or slave cylinder", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check clutch fluid level",
        "Check master cylinder for leak",
        "Check slave cylinder for leak",
        "Bleed system and retest",
    ],
    repair_actions=["Bleed clutch hydraulic system", "Replace master cylinder", "Replace slave cylinder"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "TRANSMISSION_FLUID_LOW",
    "TORQUE_CONVERTER_SHUDDER",
    "SHIFT_SOLENOID_FAILED",
    "VALVE_BODY_FAILURE",
    "TCC_STUCK_OFF",
    "TCC_STUCK_ON",
    "TRANS_SPEED_SENSOR_FAILED",
    "VSS_SENSOR_FAILED",
    "TRANS_FLUID_CONTAMINATED",
    "TRANS_MOUNT_WORN",
    "TRANS_INPUT_SHAFT_SEAL_LEAK",
    "CLUTCH_WORN",
    "CLUTCH_HYDRAULIC_FAILURE",
]
