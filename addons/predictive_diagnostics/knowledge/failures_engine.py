"""
Engine system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


LOW_COMPRESSION = FailureMode(
    id="low_compression",
    name="Low Cylinder Compression",
    category=FailureCategory.MECHANICAL,
    component_id="cylinder",
    system_id="engine",
    
    immediate_effect="Cylinder cannot build proper compression pressure",
    cascade_effects=[
        "Reduced power from affected cylinder",
        "Incomplete combustion",
        "Misfire condition",
        "Rough idle and poor performance",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", ">0 for affected cylinder"),
        PIDEffect("rpm", "unstable", "Fluctuates at idle"),
    ],
    
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
    
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.OBVIOUS),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
        Symptom("Engine misfire", SymptomSeverity.OBVIOUS),
        Symptom("Hard starting", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Compression test - should be 125-175 psi, within 15% between cylinders",
        "Leak-down test to identify rings vs valves vs head gasket",
        "Add oil to cylinder and retest (wet test)",
    ],
    
    repair_actions=[
        "If wet compression improves: replace piston rings",
        "If no improvement: inspect valves/seats or head gasket",
        "May require engine overhaul",
    ],
    relative_frequency=0.3,
)


HEAD_GASKET_FAILURE = FailureMode(
    id="head_gasket_failure",
    name="Head Gasket Failure",
    category=FailureCategory.LEAK,
    component_id="head_gasket",
    system_id="engine",
    
    immediate_effect="Seal between head and block compromised",
    cascade_effects=[
        "Coolant enters combustion chamber or oil passages",
        "Combustion gases enter cooling system",
        "Oil/coolant mixing",
        "Overheating from coolant loss",
        "Hydro-lock risk if severe",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", "Overheating"),
        PIDEffect("misfire_count", "high", "If coolant enters cylinder"),
    ],
    
    expected_dtcs=["P0300", "P0217", "P0128"],
    
    symptoms=[
        Symptom("White smoke from exhaust", SymptomSeverity.OBVIOUS),
        Symptom("Milky oil (coolant in oil)", SymptomSeverity.SEVERE),
        Symptom("Bubbles in coolant reservoir", SymptomSeverity.OBVIOUS),
        Symptom("Coolant loss without visible leak", SymptomSeverity.MODERATE),
        Symptom("Overheating", SymptomSeverity.SEVERE),
        Symptom("Sweet smell from exhaust", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Block test (chemical test for combustion gases in coolant)",
        "Compression test - adjacent cylinders with similar low readings",
        "Cooling system pressure test - pressure drops, no visible leak",
        "Check oil for milky appearance",
        "Look for coolant in combustion chambers",
    ],
    
    repair_actions=[
        "Replace head gasket",
        "Check head for warpage (machine if needed)",
        "Inspect block deck surface",
        "Flush cooling system and change oil",
    ],
    relative_frequency=0.4,
)


TIMING_CHAIN_STRETCHED = FailureMode(
    id="timing_chain_stretched",
    name="Timing Chain Stretched/Worn",
    category=FailureCategory.MECHANICAL,
    component_id="timing_chain",
    system_id="engine",
    
    immediate_effect="Valve timing retarded from designed specification",
    cascade_effects=[
        "Loss of power",
        "Poor fuel economy",
        "Rough idle",
        "Potential valve-piston contact if severe",
    ],
    
    pid_effects=[
        PIDEffect("cam_crank_correlation", "out_of_spec", "Timing deviation"),
    ],
    
    expected_dtcs=["P0016", "P0017", "P0018", "P0019", "P0341"],
    
    symptoms=[
        Symptom("Rattling noise from front of engine on startup", SymptomSeverity.OBVIOUS),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Check cam/crank correlation with scope",
        "Listen for chain rattle on cold start",
        "Inspect chain tensioner wear",
    ],
    
    repair_actions=[
        "Replace timing chain, guides, and tensioner",
        "Inspect sprockets for wear",
        "Reset timing marks",
    ],
    relative_frequency=0.3,
)


OIL_PUMP_FAILURE = FailureMode(
    id="oil_pump_failure",
    name="Oil Pump Failure",
    category=FailureCategory.MECHANICAL,
    component_id="oil_pump",
    system_id="engine",
    
    immediate_effect="Insufficient oil pressure to lubricate engine",
    cascade_effects=[
        "Bearing wear and damage",
        "Increased friction and heat",
        "Engine seizure if severe",
        "Catastrophic engine damage",
    ],
    
    pid_effects=[
        PIDEffect("oil_pressure", "low", "<10 psi at idle"),
    ],
    
    expected_dtcs=["P0520", "P0521", "P0522", "P0523"],
    
    symptoms=[
        Symptom("Low oil pressure warning light", SymptomSeverity.SEVERE),
        Symptom("Engine knock/tick", SymptomSeverity.SEVERE),
        Symptom("Oil pressure gauge reads low", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Mechanical oil pressure gauge test",
        "Check oil level first",
        "Inspect oil pickup tube for blockage",
    ],
    
    repair_actions=[
        "Check oil level and condition",
        "Replace oil pump",
        "Inspect bearings for damage",
        "May need engine rebuild if damage occurred",
    ],
    relative_frequency=0.2,
)


PCV_VALVE_STUCK = FailureMode(
    id="pcv_valve_stuck",
    name="PCV Valve Stuck",
    category=FailureCategory.STUCK,
    component_id="pcv_valve",
    system_id="engine",
    
    immediate_effect="Crankcase ventilation impaired",
    cascade_effects=[
        "Stuck closed: pressure buildup, oil leaks, oil consumption",
        "Stuck open: vacuum leak, rough idle, lean condition",
    ],
    
    pid_effects=[
        PIDEffect("stft", "variable", "Lean if stuck open"),
        PIDEffect("map", "low", "High vacuum if stuck open"),
    ],
    
    expected_dtcs=["P0171", "P0174", "P0505"],
    
    symptoms=[
        Symptom("Oil leaks (stuck closed)", SymptomSeverity.MODERATE),
        Symptom("Rough idle (stuck open)", SymptomSeverity.MODERATE),
        Symptom("Whistling noise from engine", SymptomSeverity.SUBTLE),
        Symptom("Oil consumption", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Remove and shake PCV valve - should rattle",
        "Check vacuum at PCV port",
        "Inspect for oil in intake manifold",
    ],
    
    repair_actions=["Replace PCV valve", "Clean or replace breather hoses"],
    relative_frequency=0.5,
)


VVT_SOLENOID_STUCK = FailureMode(
    id="vvt_solenoid_stuck",
    name="VVT Solenoid Stuck/Failed",
    category=FailureCategory.STUCK,
    component_id="vvt_solenoid",
    system_id="engine",
    
    immediate_effect="Can't control cam timing",
    cascade_effects=[
        "Poor performance",
        "Rough idle",
        "Poor fuel economy",
        "Emissions increase",
    ],
    
    pid_effects=[
        PIDEffect("cam_timing", "stuck", "Not matching commanded"),
        PIDEffect("cam_retard", "stuck", "Can't advance or retard"),
    ],
    
    expected_dtcs=["P0010", "P0011", "P0012", "P0013", "P0014", "P0015", 
                   "P0020", "P0021", "P0022", "P0023", "P0024", "P0025"],
    
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("Reduced power", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Command VVT with scan tool, monitor response",
        "Check VVT solenoid resistance",
        "Check oil pressure",
        "Check for sludge in oil system",
    ],
    
    repair_actions=[
        "Replace VVT solenoid",
        "Change oil if contaminated",
        "Check cam phaser if solenoid OK",
    ],
    repair_time_hours=1.0,
    parts_cost_low=30,
    parts_cost_high=150,
    relative_frequency=0.4,
)


CAM_PHASER_WORN = FailureMode(
    id="cam_phaser_worn",
    name="Cam Phaser Worn/Rattling",
    category=FailureCategory.MECHANICAL,
    component_id="cam_phaser",
    system_id="engine",
    
    immediate_effect="Cam timing not holding position",
    cascade_effects=[
        "Rattling noise at startup",
        "Timing variation",
        "Performance issues",
    ],
    
    pid_effects=[
        PIDEffect("cam_timing", "erratic", "Fluctuating"),
    ],
    
    expected_dtcs=["P0011", "P0012", "P0014", "P0015", "P0021", "P0022", "P0024", "P0025"],
    
    symptoms=[
        Symptom("Rattling/knocking at cold start", SymptomSeverity.OBVIOUS),
        Symptom("Rattle goes away when warm", SymptomSeverity.MODERATE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Listen for rattle at cold start",
        "Monitor cam timing stability",
        "Check oil pressure",
        "Common on Ford 5.4L, GM LS engines",
    ],
    
    repair_actions=[
        "Replace cam phaser(s)",
        "Replace timing chain if stretched",
        "Change oil more frequently",
    ],
    repair_time_hours=8.0,
    parts_cost_low=200,
    parts_cost_high=600,
    relative_frequency=0.3,
)


TIMING_BELT_WORN = FailureMode(
    id="timing_belt_worn",
    name="Timing Belt Worn/Stretched",
    category=FailureCategory.DRIFT,
    component_id="timing_belt",
    system_id="engine",
    immediate_effect="Valve timing drifts from spec",
    cascade_effects=[
        "Poor performance",
        "Rough running",
        "Eventually jumps or breaks",
    ],
    expected_dtcs=["P0340", "P0341", "P0016", "P0017"],
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
        Symptom("Ticking noise from timing cover", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check timing belt condition (if accessible)",
        "Check cam/crank correlation with scan tool",
        "Check for cam timing codes",
    ],
    repair_actions=["Replace timing belt", "Replace tensioner and idler"],
    repair_time_hours=4.0,
    parts_cost_low=100,
    parts_cost_high=300,
    relative_frequency=0.4,
)


PISTON_RING_WORN = FailureMode(
    id="piston_ring_worn",
    name="Piston Rings Worn",
    category=FailureCategory.MECHANICAL,
    component_id="piston_rings",
    system_id="engine",
    immediate_effect="Blow-by past rings, oil consumption",
    cascade_effects=[
        "Oil burning",
        "Blue smoke from exhaust",
        "Loss of compression",
        "Fouled spark plugs",
    ],
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
    symptoms=[
        Symptom("Blue smoke from exhaust", SymptomSeverity.OBVIOUS),
        Symptom("Oil consumption", SymptomSeverity.MODERATE),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Compression test (compare cylinders)",
        "Leak-down test (air escaping past rings)",
        "Check PCV system for oil contamination",
    ],
    repair_actions=["Engine rebuild or replacement"],
    repair_time_hours=20.0,
    parts_cost_low=500,
    parts_cost_high=2000,
    relative_frequency=0.2,
)


VALVE_SEAL_LEAKING = FailureMode(
    id="valve_seal_leaking",
    name="Valve Seals Leaking",
    category=FailureCategory.LEAK,
    component_id="valve_seals",
    system_id="engine",
    immediate_effect="Oil leaks past valve stems into cylinders",
    cascade_effects=[
        "Oil burning on startup",
        "Blue smoke on startup or deceleration",
        "Fouled spark plugs",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Blue smoke on startup (then clears)", SymptomSeverity.OBVIOUS),
        Symptom("Blue smoke on deceleration", SymptomSeverity.MODERATE),
        Symptom("Oil consumption", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Blue smoke on cold start that clears",
        "Smoke on deceleration (vacuum pulls oil past seals)",
        "Compression test should be normal (unlike rings)",
    ],
    repair_actions=["Replace valve seals"],
    repair_time_hours=6.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.3,
)


ENGINE_MOUNT_WORN = FailureMode(
    id="engine_mount_worn",
    name="Engine Mount Worn",
    category=FailureCategory.MECHANICAL,
    component_id="engine_mount",
    system_id="engine",
    immediate_effect="Excessive engine movement",
    cascade_effects=[
        "Vibration at idle",
        "Clunk on acceleration/deceleration",
        "Can stress drivetrain components",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Vibration at idle in gear", SymptomSeverity.MODERATE),
        Symptom("Clunk on acceleration", SymptomSeverity.MODERATE),
        Symptom("Engine visible moving", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of mounts",
        "Check for torn or collapsed rubber",
        "Have helper put in gear while you watch engine movement",
    ],
    repair_actions=["Replace engine mount(s)"],
    repair_time_hours=1.5,
    parts_cost_low=40,
    parts_cost_high=150,
    relative_frequency=0.5,
)


OIL_LEAK_VALVE_COVER = FailureMode(
    id="oil_leak_valve_cover",
    name="Valve Cover Gasket Leak",
    category=FailureCategory.LEAK,
    component_id="valve_cover",
    system_id="engine",
    immediate_effect="Oil leaks from valve cover",
    cascade_effects=[
        "Oil drips on exhaust (smoke/smell)",
        "Oil level drops",
        "Messy engine bay",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Oil on engine", SymptomSeverity.OBVIOUS),
        Symptom("Burning oil smell", SymptomSeverity.MODERATE),
        Symptom("Smoke from engine bay", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of valve cover area",
        "Clean and recheck after driving",
        "Look for oil tracking down engine",
    ],
    repair_actions=["Replace valve cover gasket"],
    repair_time_hours=1.5,
    parts_cost_low=20,
    parts_cost_high=80,
    relative_frequency=0.6,
)


OIL_LEAK_OIL_PAN = FailureMode(
    id="oil_leak_oil_pan",
    name="Oil Pan Gasket Leak",
    category=FailureCategory.LEAK,
    component_id="oil_pan",
    system_id="engine",
    immediate_effect="Oil leaks from oil pan",
    cascade_effects=[
        "Oil drips on ground",
        "Oil level drops",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Oil spots under vehicle", SymptomSeverity.OBVIOUS),
        Symptom("Low oil level", SymptomSeverity.MODERATE),
        Symptom("Oil visible on bottom of oil pan", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection from below",
        "Check pan bolts for tightness",
        "Look for impact damage to pan",
    ],
    repair_actions=["Replace oil pan gasket", "May need to lift engine/subframe"],
    repair_time_hours=2.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.5,
)


OIL_LEAK_REAR_MAIN_SEAL = FailureMode(
    id="oil_leak_rear_main_seal",
    name="Rear Main Seal Leak",
    category=FailureCategory.LEAK,
    component_id="rear_main_seal",
    system_id="engine",
    immediate_effect="Oil leaks at back of engine",
    cascade_effects=[
        "Oil on flywheel/flexplate",
        "Oil drips",
        "Potential clutch contamination",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Oil leak at bell housing", SymptomSeverity.OBVIOUS),
        Symptom("Oil on flywheel/flexplate", SymptomSeverity.MODERATE),
        Symptom("Clutch slipping (manual trans)", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection at back of engine",
        "Check if leak is from engine or transmission",
        "Need to remove transmission for repair",
    ],
    repair_actions=["Replace rear main seal", "Requires trans removal"],
    repair_time_hours=5.0,
    parts_cost_low=25,
    parts_cost_high=75,
    relative_frequency=0.3,
)


OIL_PRESSURE_SENSOR_FAILED = FailureMode(
    id="oil_pressure_sensor_failed",
    name="Oil Pressure Sensor/Switch Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="oil_pressure_sensor",
    system_id="engine",
    immediate_effect="False oil pressure reading",
    cascade_effects=[
        "Oil light on with good oil pressure",
        "Or no warning when pressure is actually low",
    ],
    expected_dtcs=["P0520", "P0521", "P0522", "P0523"],
    symptoms=[
        Symptom("Oil pressure light on", SymptomSeverity.OBVIOUS),
        Symptom("Erratic oil pressure gauge reading", SymptomSeverity.MODERATE),
        Symptom("Oil leak at sensor", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Verify actual oil pressure with mechanical gauge",
        "Check sensor wiring and connector",
        "Check for oil leak at sensor threads",
    ],
    repair_actions=["Replace oil pressure sensor"],
    repair_time_hours=0.5,
    parts_cost_low=15,
    parts_cost_high=60,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "LOW_COMPRESSION",
    "HEAD_GASKET_FAILURE",
    "TIMING_CHAIN_STRETCHED",
    "OIL_PUMP_FAILURE",
    "PCV_VALVE_STUCK",
    "VVT_SOLENOID_STUCK",
    "CAM_PHASER_WORN",
    "TIMING_BELT_WORN",
    "PISTON_RING_WORN",
    "VALVE_SEAL_LEAKING",
    "ENGINE_MOUNT_WORN",
    "OIL_LEAK_VALVE_COVER",
    "OIL_LEAK_OIL_PAN",
    "OIL_LEAK_REAR_MAIN_SEAL",
    "OIL_PRESSURE_SENSOR_FAILED",
]
