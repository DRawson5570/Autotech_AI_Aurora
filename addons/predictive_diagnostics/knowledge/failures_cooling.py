"""
Cooling system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


THERMOSTAT_STUCK_CLOSED = FailureMode(
    id="thermostat_stuck_closed",
    name="Thermostat Stuck Closed",
    category=FailureCategory.STUCK,
    component_id="thermostat",
    system_id="cooling",
    
    immediate_effect="Coolant cannot flow to radiator",
    cascade_effects=[
        "Heat cannot be rejected from engine",
        "Coolant temperature rises rapidly",
        "Engine overheats",
        "ECU may retard timing or reduce power to protect engine",
        "Potential engine damage if not addressed",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">105°C / >220°F", 
                  "Temperature climbs above normal operating range"),
        PIDEffect("engine_load", "may_decrease", None,
                  "ECU may de-rate engine to protect"),
    ],
    
    expected_dtcs=["P0217", "P0118"],  # Engine overtemp, ECT high
    
    symptoms=[
        Symptom("Temperature gauge in red zone", SymptomSeverity.OBVIOUS),
        Symptom("Overheating warning light illuminated", SymptomSeverity.OBVIOUS),
        Symptom("Steam from under hood", SymptomSeverity.SEVERE, "if coolant boils"),
        Symptom("Reduced engine power", SymptomSeverity.MODERATE, "limp mode"),
    ],
    
    discriminating_tests=[
        "Feel upper and lower radiator hoses - both should be hot at operating temp; if lower is cold, thermostat not opening",
        "IR thermometer: compare engine block temp to radiator - large difference indicates blocked thermostat",
        "Remove thermostat and test in hot water - should open at rated temperature",
    ],
    
    repair_actions=["Replace thermostat", "Flush cooling system if contaminated"],
    repair_time_hours=1.0,
    parts_cost_low=25,
    parts_cost_high=75,
    relative_frequency=0.7,
)


THERMOSTAT_STUCK_OPEN = FailureMode(
    id="thermostat_stuck_open",
    name="Thermostat Stuck Open",
    category=FailureCategory.STUCK,
    component_id="thermostat",
    system_id="cooling",
    
    immediate_effect="Coolant flows through radiator constantly, even when cold",
    cascade_effects=[
        "Engine never reaches normal operating temperature",
        "Coolant temperature stays low (~70°C / 160°F instead of 90°C / 195°F)",
        "ECU sees cold engine, maintains rich fuel mixture",
        "Poor fuel economy",
        "Increased emissions",
        "Heater may not blow hot",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "low", "<82°C / <180°F",
                  "Temperature plateaus below normal operating range"),
        PIDEffect("stft", "positive", "+5% to +15%",
                  "ECU adds fuel for perceived cold engine"),
        PIDEffect("ltft", "positive", "+3% to +10%",
                  "Long-term adaptation to cold running"),
    ],
    
    expected_dtcs=["P0128"],  # Coolant temp below thermostat regulating temp
    
    symptoms=[
        Symptom("Temperature gauge stays low", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("Heater not blowing hot", SymptomSeverity.MODERATE, "in cold weather"),
        Symptom("Slow warmup", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Compare coolant temp (PID) to IR reading of thermostat housing - should match",
        "Block radiator airflow with cardboard - temp should rise; if thermostat working, would already be closed",
        "Remove thermostat and test in hot water - check if stuck open",
    ],
    
    repair_actions=["Replace thermostat"],
    repair_time_hours=1.0,
    parts_cost_low=25,
    parts_cost_high=75,
    relative_frequency=0.6,
)


WATER_PUMP_FAILURE = FailureMode(
    id="water_pump_failure",
    name="Water Pump Failure",
    category=FailureCategory.MECHANICAL,
    component_id="water_pump",
    system_id="cooling",
    
    immediate_effect="Coolant circulation reduced or stopped",
    cascade_effects=[
        "Insufficient coolant flow through engine",
        "Local hot spots develop",
        "Engine overheats, especially under load",
        "May have noise from failed bearing",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">105°C under load",
                  "Temperature rises especially under load"),
    ],
    
    expected_dtcs=["P0217"],  # Engine overtemp
    
    symptoms=[
        Symptom("Overheating under load", SymptomSeverity.OBVIOUS),
        Symptom("Whining or grinding noise from pump", SymptomSeverity.MODERATE, "bearing failure"),
        Symptom("Coolant leak from weep hole", SymptomSeverity.MODERATE, "seal failure"),
    ],
    
    discriminating_tests=[
        "Check for play in water pump shaft - indicates bearing failure",
        "Check weep hole for coolant leak - indicates seal failure",
        "Feel upper radiator hose at operating temp - should be firm with pressure pulses",
        "Use coolant pressure tester and watch for pressure drop",
    ],
    
    repair_actions=["Replace water pump", "Replace drive belt if worn", "Check and replace timing belt if belt-driven"],
    repair_time_hours=3.0,
    parts_cost_low=80,
    parts_cost_high=250,
    relative_frequency=0.4,
)


WATER_PUMP_BELT_SLIPPING = FailureMode(
    id="water_pump_belt_slipping",
    name="Water Pump Belt Slipping",
    category=FailureCategory.MECHANICAL,
    component_id="water_pump",
    system_id="cooling",
    
    immediate_effect="Reduced pump speed, insufficient coolant circulation",
    cascade_effects=[
        "Coolant flow reduced",
        "Engine runs hot, especially at idle or low RPM",
        "May squeal when cold or wet",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">100°C at idle",
                  "Temperature higher than normal, especially at idle"),
    ],
    
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Squealing noise from belt", SymptomSeverity.MODERATE, "especially when cold"),
        Symptom("Overheating at idle, better at speed", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Inspect belt for glazing, cracks, wear",
        "Check belt tension",
        "Spray water on belt - if squealing stops, belt needs replacement",
    ],
    
    repair_actions=["Adjust belt tension", "Replace belt if worn"],
    relative_frequency=0.5,
)


RADIATOR_BLOCKED_EXTERNAL = FailureMode(
    id="radiator_blocked_external",
    name="Radiator Blocked (External)",
    category=FailureCategory.BLOCKAGE,
    component_id="radiator",
    system_id="cooling",
    
    immediate_effect="Airflow through radiator restricted by debris",
    cascade_effects=[
        "Reduced heat rejection",
        "Engine overheats, especially at low speed or idle",
        "A/C performance reduced (shares condenser)",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">100°C at idle/low speed",
                  "Temperature rises when airflow is low"),
    ],
    
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Overheating in traffic or at idle", SymptomSeverity.OBVIOUS),
        Symptom("Temperature normal at highway speed", SymptomSeverity.MODERATE),
        Symptom("Visible debris on radiator", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Visual inspection of radiator face for bugs, debris, leaves",
        "Check if temp drops significantly at highway speed vs idle",
    ],
    
    repair_actions=["Clean radiator with water and compressed air", "Install bug screen if recurring"],
    relative_frequency=0.5,
)


RADIATOR_BLOCKED_INTERNAL = FailureMode(
    id="radiator_blocked_internal",
    name="Radiator Blocked (Internal)",
    category=FailureCategory.BLOCKAGE,
    component_id="radiator",
    system_id="cooling",
    
    immediate_effect="Coolant flow through radiator restricted by deposits",
    cascade_effects=[
        "Reduced heat rejection",
        "Engine overheats",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">105°C",
                  "Temperature above normal"),
    ],
    
    expected_dtcs=["P0217"],
    
    symptoms=[
        Symptom("Overheating", SymptomSeverity.OBVIOUS),
        Symptom("Discolored or contaminated coolant", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "IR scan of radiator surface - should have even temperature distribution; cold spots indicate blockage",
        "Check coolant condition - rust, oil, deposits",
        "Flow test radiator (removed)",
    ],
    
    repair_actions=["Replace radiator", "Flush cooling system", "Check for source of contamination"],
    relative_frequency=0.3,
)


COOLING_FAN_NOT_OPERATING = FailureMode(
    id="cooling_fan_not_operating",
    name="Cooling Fan Not Operating",
    category=FailureCategory.ELECTRICAL,
    component_id="cooling_fan",
    system_id="cooling",
    
    immediate_effect="No airflow through radiator at low vehicle speed",
    cascade_effects=[
        "Cannot reject heat when stationary or slow",
        "Overheating in traffic, at idle, when A/C on",
        "Temperature normal at highway speed",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">105°C at idle",
                  "Temperature rises at low speed/idle"),
    ],
    
    expected_dtcs=["P0480", "P0481"],  # Cooling fan control codes
    
    symptoms=[
        Symptom("Overheating in traffic or at idle", SymptomSeverity.OBVIOUS),
        Symptom("Fan not spinning when hot", SymptomSeverity.OBVIOUS),
        Symptom("Temperature drops at highway speed", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Turn on A/C max - fan should activate",
        "Check fan relay and fuse",
        "Apply 12V directly to fan motor",
        "Check fan thermal switch or ECU control circuit",
    ],
    
    repair_actions=[
        "Replace fan motor if failed",
        "Replace fan relay if failed",
        "Replace thermal switch if failed",
        "Repair wiring if damaged",
    ],
    relative_frequency=0.5,
)


COOLING_FAN_ALWAYS_ON = FailureMode(
    id="cooling_fan_always_on",
    name="Cooling Fan Running Constantly",
    category=FailureCategory.ELECTRICAL,
    component_id="cooling_fan",
    system_id="cooling",
    
    immediate_effect="Fan runs even when engine cold",
    cascade_effects=[
        "Engine may run too cool (similar to stuck-open thermostat)",
        "Battery drain",
        "Fan motor premature wear",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "low", "<82°C",
                  "May run cool if fan prevents normal warmup"),
    ],
    
    expected_dtcs=["P0128"],  # If running too cool
    
    symptoms=[
        Symptom("Fan runs immediately on startup", SymptomSeverity.MODERATE),
        Symptom("Slow warmup", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Check if relay stuck closed",
        "Check for short in thermal switch circuit",
        "Check ECU commands vs actual fan operation",
    ],
    
    repair_actions=["Replace relay if stuck", "Repair short circuit", "Replace thermal switch"],
    relative_frequency=0.2,
)


PRESSURE_CAP_FAULTY = FailureMode(
    id="pressure_cap_faulty",
    name="Radiator Pressure Cap Faulty",
    category=FailureCategory.MECHANICAL,
    component_id="pressure_cap",
    system_id="cooling",
    
    immediate_effect="Cannot maintain system pressure",
    cascade_effects=[
        "Coolant boiling point reduced",
        "Coolant boils at lower temperature",
        "Loss of coolant through overflow",
        "Air enters system creating air lock",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "erratic", None,
                  "May show spikes when coolant boils"),
    ],
    
    expected_dtcs=[],
    
    symptoms=[
        Symptom("Coolant loss without visible leak", SymptomSeverity.MODERATE),
        Symptom("Overflow reservoir always full/overflowing when hot", SymptomSeverity.MODERATE),
        Symptom("Overheating at high ambient temps", SymptomSeverity.MODERATE),
        Symptom("Air in cooling system", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Pressure test cap - should hold rated pressure (typically 13-16 psi / 90-110 kPa)",
        "Check cap seal condition",
    ],
    
    repair_actions=["Replace pressure cap"],
    relative_frequency=0.4,
)


COOLANT_LEAK = FailureMode(
    id="coolant_leak",
    name="Coolant Leak",
    category=FailureCategory.LEAK,
    component_id="cooling_system",  # Generic to system
    system_id="cooling",
    
    immediate_effect="Coolant escaping from system",
    cascade_effects=[
        "Coolant level drops",
        "Air enters system",
        "Reduced coolant volume means less heat capacity",
        "Eventually overheats when coolant too low",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "high", ">105°C",
                  "Temperature rises as coolant level drops"),
    ],
    
    expected_dtcs=["P0217"],  # When overheating occurs
    
    symptoms=[
        Symptom("Visible coolant puddle under vehicle", SymptomSeverity.OBVIOUS),
        Symptom("Sweet smell from engine bay", SymptomSeverity.MODERATE),
        Symptom("Low coolant warning", SymptomSeverity.OBVIOUS),
        Symptom("Need to add coolant frequently", SymptomSeverity.MODERATE),
        Symptom("Overheating (eventually)", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Pressure test system cold - watch gauge for pressure drop",
        "Pressure test hot - some leaks only appear when hot",
        "UV dye test - add dye and check with UV light",
        "Visual inspection of hoses, water pump weep hole, radiator",
    ],
    
    repair_actions=[
        "Identify leak source",
        "Replace leaking component (hose, water pump, radiator, etc.)",
        "Check for head gasket failure if coolant loss with no external leak",
    ],
    relative_frequency=0.7,
)


ECT_SENSOR_FAILED_HIGH = FailureMode(
    id="ect_sensor_failed_high",
    name="Coolant Temp Sensor Reading High",
    category=FailureCategory.ELECTRICAL,
    component_id="coolant_temp_sensor",
    system_id="cooling",
    
    immediate_effect="Sensor sends signal indicating higher temp than actual",
    cascade_effects=[
        "ECU thinks engine hot when it's not",
        "Fan runs unnecessarily",
        "Engine may run too cool (overcooling)",
        "Possible lean condition (ECU reduces fuel for 'hot' engine)",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "stuck_high", ">105°C even when cold",
                  "Shows hot even when engine cold or after sitting"),
    ],
    
    expected_dtcs=["P0118"],  # ECT circuit high
    
    symptoms=[
        Symptom("Fan runs immediately at startup", SymptomSeverity.MODERATE),
        Symptom("Temp gauge shows hot when engine cold", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Compare ECT PID to actual temperature (IR gun, other gauge)",
        "Check sensor resistance - should match spec for actual temp",
        "Check for short to ground in sensor circuit",
    ],
    
    repair_actions=["Check wiring for short to ground", "Replace sensor if faulty"],
    relative_frequency=0.3,
)


ECT_SENSOR_FAILED_LOW = FailureMode(
    id="ect_sensor_failed_low",
    name="Coolant Temp Sensor Reading Low",
    category=FailureCategory.ELECTRICAL,
    component_id="coolant_temp_sensor",
    system_id="cooling",
    
    immediate_effect="Sensor sends signal indicating lower temp than actual",
    cascade_effects=[
        "ECU thinks engine cold when it's hot",
        "Fan doesn't activate when needed",
        "Rich fuel mixture (cold enrichment stays on)",
        "Engine may overheat (no fan, no protection)",
    ],
    
    pid_effects=[
        PIDEffect("coolant_temp", "stuck_low", "<50°C even when hot",
                  "Shows cold even after extended driving"),
        PIDEffect("stft", "positive", "+10% to +20%",
                  "Rich mixture for perceived cold engine"),
    ],
    
    expected_dtcs=["P0117", "P0128"],  # ECT circuit low, thermostat below temp
    
    symptoms=[
        Symptom("Fan never activates", SymptomSeverity.MODERATE),
        Symptom("Temp gauge always shows cold", SymptomSeverity.OBVIOUS),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("May overheat (no fan activation)", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Compare ECT PID to actual temperature (IR gun)",
        "Check sensor resistance - should match spec for actual temp",
        "Check for open circuit in sensor wiring",
    ],
    
    repair_actions=["Check wiring for open circuit", "Replace sensor if faulty"],
    relative_frequency=0.4,
)


HEATER_HOSE_LEAK = FailureMode(
    id="heater_hose_leak",
    name="Heater Hose Leak",
    category=FailureCategory.LEAK,
    component_id="heater_hose",
    system_id="cooling",
    immediate_effect="Coolant leaks from heater hose",
    cascade_effects=[
        "Coolant loss",
        "Possible overheating",
        "Coolant smell in cabin",
    ],
    expected_dtcs=["P0128"],
    symptoms=[
        Symptom("Sweet coolant smell", SymptomSeverity.MODERATE),
        Symptom("Low coolant level", SymptomSeverity.MODERATE),
        Symptom("Coolant drips near firewall", SymptomSeverity.OBVIOUS),
        Symptom("Steam from engine bay", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of heater hoses",
        "Pressure test cooling system",
        "Check hose clamps",
    ],
    repair_actions=["Replace heater hose", "Check clamps"],
    repair_time_hours=0.5,
    parts_cost_low=15,
    parts_cost_high=50,
    relative_frequency=0.4,
)


WATER_OUTLET_HOUSING_LEAK = FailureMode(
    id="water_outlet_housing_leak",
    name="Water Outlet/Thermostat Housing Leak",
    category=FailureCategory.LEAK,
    component_id="water_outlet",
    system_id="cooling",
    immediate_effect="Coolant leaks at thermostat housing",
    cascade_effects=[
        "Coolant loss",
        "Possible overheating",
    ],
    expected_dtcs=["P0128"],
    symptoms=[
        Symptom("Coolant leak at front of engine", SymptomSeverity.OBVIOUS),
        Symptom("Low coolant level", SymptomSeverity.MODERATE),
        Symptom("Visible coolant at housing", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of thermostat housing",
        "Check for plastic housing cracks (common on some vehicles)",
        "Pressure test cooling system",
    ],
    repair_actions=["Replace thermostat housing", "Replace gasket/O-ring"],
    repair_time_hours=1.0,
    parts_cost_low=20,
    parts_cost_high=100,
    relative_frequency=0.4,
)


FAN_CLUTCH_FAILED = FailureMode(
    id="fan_clutch_failed",
    name="Fan Clutch Failed (Mechanical)",
    category=FailureCategory.MECHANICAL,
    component_id="fan_clutch",
    system_id="cooling",
    immediate_effect="Fan doesn't engage properly",
    cascade_effects=[
        "Overheating at idle or low speed",
        "Or fan always engaged (poor fuel economy, noise)",
    ],
    expected_dtcs=["P0480", "P0481"],
    symptoms=[
        Symptom("Overheating at idle/in traffic", SymptomSeverity.MODERATE),
        Symptom("Roaring noise from engine (fan always on)", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy (fan always on)", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Spin fan by hand (cold engine) - should have some resistance",
        "Check for silicone oil leak from clutch",
        "Fan should engage harder when engine hot",
    ],
    repair_actions=["Replace fan clutch"],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "THERMOSTAT_STUCK_CLOSED",
    "THERMOSTAT_STUCK_OPEN",
    "WATER_PUMP_FAILURE",
    "WATER_PUMP_BELT_SLIPPING",
    "RADIATOR_BLOCKED_EXTERNAL",
    "RADIATOR_BLOCKED_INTERNAL",
    "COOLING_FAN_NOT_OPERATING",
    "COOLING_FAN_ALWAYS_ON",
    "PRESSURE_CAP_FAULTY",
    "COOLANT_LEAK",
    "ECT_SENSOR_FAILED_HIGH",
    "ECT_SENSOR_FAILED_LOW",
    "HEATER_HOSE_LEAK",
    "WATER_OUTLET_HOUSING_LEAK",
    "FAN_CLUTCH_FAILED",
]
