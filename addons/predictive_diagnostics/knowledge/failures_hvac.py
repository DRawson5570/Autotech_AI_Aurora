"""
Hvac system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


AC_COMPRESSOR_FAILING = FailureMode(
    id="ac_compressor_failing",
    name="A/C Compressor Failing",
    category=FailureCategory.MECHANICAL,
    component_id="ac_compressor",
    system_id="hvac",
    immediate_effect="Reduced or no refrigerant compression",
    expected_dtcs=["B1421", "B1422"],
    symptoms=[Symptom("A/C blows warm air", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check high/low pressures", "Listen for compressor noise"],
    repair_actions=["Replace A/C compressor", "Evacuate and recharge system"],
    relative_frequency=0.4,
)


REFRIGERANT_LEAK = FailureMode(
    id="refrigerant_leak",
    name="Refrigerant Leak",
    category=FailureCategory.LEAK,
    component_id="ac_system",
    system_id="hvac",
    immediate_effect="Loss of refrigerant",
    symptoms=[Symptom("A/C gradually stops cooling", SymptomSeverity.MODERATE)],
    discriminating_tests=["UV dye test", "Electronic leak detector"],
    repair_actions=["Locate and repair leak", "Evacuate and recharge"],
    relative_frequency=0.6,
)


BLEND_DOOR_STUCK = FailureMode(
    id="blend_door_stuck",
    name="Blend Door Actuator Stuck",
    category=FailureCategory.STUCK,
    component_id="blend_door",
    system_id="hvac",
    immediate_effect="Temperature control not working",
    symptoms=[Symptom("Only hot or only cold air", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Listen for actuator motor", "Check door movement"],
    repair_actions=["Replace blend door actuator"],
    relative_frequency=0.4,
)


BLOWER_MOTOR_FAILING = FailureMode(
    id="blower_motor_failing",
    name="Blower Motor Failing",
    category=FailureCategory.ELECTRICAL,
    component_id="blower_motor",
    system_id="hvac",
    immediate_effect="Reduced or no airflow from vents",
    symptoms=[Symptom("Weak or no air from vents", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check blower motor voltage", "Test motor directly"],
    repair_actions=["Replace blower motor", "Check resistor pack"],
    relative_frequency=0.4,
)


HEATER_CORE_CLOGGED = FailureMode(
    id="heater_core_clogged",
    name="Heater Core Clogged/Failing",
    category=FailureCategory.BLOCKAGE,
    component_id="heater_core",
    system_id="hvac",
    immediate_effect="Reduced coolant flow through heater core",
    symptoms=[Symptom("No heat from heater", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Check both heater hoses temperature"],
    repair_actions=["Flush heater core", "Replace if flush fails"],
    relative_frequency=0.3,
)


AC_COMPRESSOR_CLUTCH_FAILED = FailureMode(
    id="ac_compressor_clutch_failed",
    name="A/C Compressor Clutch Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ac_compressor_clutch",
    system_id="hvac",
    immediate_effect="Compressor clutch doesn't engage",
    cascade_effects=[
        "No A/C",
        "Compressor may be fine but clutch is bad",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("A/C blows warm", SymptomSeverity.OBVIOUS),
        Symptom("Clutch not engaging (visual)", SymptomSeverity.OBVIOUS),
        Symptom("No click when A/C turned on", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check clutch for engagement when A/C on",
        "Check power at clutch connector",
        "Check clutch coil resistance",
        "Verify pressure switches are satisfied",
    ],
    repair_actions=["Replace clutch", "Or replace compressor assembly"],
    repair_time_hours=1.5,
    parts_cost_low=100,
    parts_cost_high=300,
    relative_frequency=0.4,
)


AC_EXPANSION_VALVE_STUCK = FailureMode(
    id="ac_expansion_valve_stuck",
    name="A/C Expansion Valve Stuck",
    category=FailureCategory.STUCK,
    component_id="expansion_valve",
    system_id="hvac",
    immediate_effect="Improper refrigerant metering",
    cascade_effects=[
        "Stuck open: icing on evaporator, poor cooling",
        "Stuck closed: no cooling, high head pressure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("A/C blows warm or cold intermittently", SymptomSeverity.MODERATE),
        Symptom("Icing on lines", SymptomSeverity.OBVIOUS),
        Symptom("Abnormal pressures", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check A/C pressures (compare to specs)",
        "Check for icing at expansion valve",
        "Check superheat/subcooling",
    ],
    repair_actions=["Replace expansion valve", "Evacuate and recharge system"],
    repair_time_hours=2.0,
    parts_cost_low=50,
    parts_cost_high=150,
    relative_frequency=0.3,
)


EVAPORATOR_CORE_LEAK = FailureMode(
    id="evaporator_core_leak",
    name="A/C Evaporator Core Leak",
    category=FailureCategory.LEAK,
    component_id="evaporator",
    system_id="hvac",
    immediate_effect="Refrigerant leaks from evaporator",
    cascade_effects=[
        "System loses charge",
        "A/C performance degrades",
        "Dye may be visible at drain tube",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("A/C gradually loses cooling", SymptomSeverity.MODERATE),
        Symptom("Oily residue at evap drain", SymptomSeverity.SUBTLE),
        Symptom("A/C only works after recharge for short time", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "UV dye test",
        "Electronic leak detector at vents",
        "Check drain tube for oil/dye",
    ],
    repair_actions=["Replace evaporator core", "Evacuate and recharge"],
    repair_time_hours=6.0,
    parts_cost_low=150,
    parts_cost_high=400,
    relative_frequency=0.3,
)


CONDENSER_CLOGGED = FailureMode(
    id="condenser_clogged",
    name="A/C Condenser Clogged/Blocked",
    category=FailureCategory.BLOCKAGE,
    component_id="condenser",
    system_id="hvac",
    immediate_effect="Cannot reject heat from refrigerant",
    cascade_effects=[
        "High head pressure",
        "Poor cooling",
        "Compressor may cycle on high pressure switch",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("A/C works better at highway speed", SymptomSeverity.MODERATE),
        Symptom("Poor cooling at idle", SymptomSeverity.MODERATE),
        Symptom("High side pressure too high", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check condenser for debris (bugs, leaves)",
        "Check A/C pressures",
        "Clean condenser and retest",
    ],
    repair_actions=["Clean condenser", "Replace if damaged"],
    repair_time_hours=0.5,
    parts_cost_low=0,
    parts_cost_high=200,
    relative_frequency=0.4,
)


BLOWER_MOTOR_RESISTOR_FAILED = FailureMode(
    id="blower_motor_resistor_failed",
    name="Blower Motor Resistor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="blower_resistor",
    system_id="hvac",
    immediate_effect="Some or all blower speeds don't work",
    cascade_effects=[
        "Only high speed works (common)",
        "No blower at all",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Blower only works on high", SymptomSeverity.OBVIOUS),
        Symptom("Some speeds don't work", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Test each speed setting",
        "Check resistor for burn marks",
        "Check connector for melting",
    ],
    repair_actions=["Replace blower motor resistor", "Check connector condition"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.5,
)


CABIN_AIR_FILTER_CLOGGED = FailureMode(
    id="cabin_air_filter_clogged",
    name="Cabin Air Filter Clogged",
    category=FailureCategory.BLOCKAGE,
    component_id="cabin_filter",
    system_id="hvac",
    immediate_effect="Restricted airflow into cabin",
    cascade_effects=[
        "Weak airflow from vents",
        "Musty smell",
        "AC/heat less effective",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Weak airflow from vents", SymptomSeverity.MODERATE),
        Symptom("Musty smell from vents", SymptomSeverity.MODERATE),
        Symptom("Windshield fogs up", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Inspect cabin air filter",
        "Check airflow improvement after removal",
    ],
    repair_actions=["Replace cabin air filter"],
    repair_time_hours=0.2,
    parts_cost_low=15,
    parts_cost_high=40,
    relative_frequency=0.7,
)


AC_PRESSURE_SENSOR_FAILED = FailureMode(
    id="ac_pressure_sensor_failed",
    name="A/C Pressure Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ac_pressure_sensor",
    system_id="hvac",
    immediate_effect="PCM receives incorrect A/C pressure data",
    cascade_effects=[
        "A/C may not engage",
        "Compressor may not be protected",
        "Poor A/C performance",
    ],
    expected_dtcs=["P0530", "P0531", "P0532", "P0533"],
    symptoms=[
        Symptom("A/C not working", SymptomSeverity.OBVIOUS),
        Symptom("A/C compressor won't engage", SymptomSeverity.OBVIOUS),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check A/C pressure with gauges",
        "Compare gauge reading to sensor reading",
        "Check sensor connector and wiring",
    ],
    repair_actions=["Replace A/C pressure sensor"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.3,
)


AMBIENT_AIR_TEMP_SENSOR_FAILED = FailureMode(
    id="ambient_air_temp_sensor_failed",
    name="Ambient Air Temperature Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ambient_temp_sensor",
    system_id="hvac",
    immediate_effect="Incorrect outside temperature reading",
    cascade_effects=[
        "Auto climate control may not work properly",
        "Temperature display incorrect",
    ],
    expected_dtcs=["B1249", "B1318"],
    symptoms=[
        Symptom("Outside temp display incorrect", SymptomSeverity.OBVIOUS),
        Symptom("Auto climate control issues", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Compare displayed temp to actual",
        "Check sensor resistance vs temp chart",
        "Check connector and wiring",
    ],
    repair_actions=["Replace ambient temperature sensor"],
    repair_time_hours=0.3,
    parts_cost_low=15,
    parts_cost_high=50,
    relative_frequency=0.3,
)


# Exports
__all__ = [
    "AC_COMPRESSOR_FAILING",
    "REFRIGERANT_LEAK",
    "BLEND_DOOR_STUCK",
    "BLOWER_MOTOR_FAILING",
    "HEATER_CORE_CLOGGED",
    "AC_COMPRESSOR_CLUTCH_FAILED",
    "AC_EXPANSION_VALVE_STUCK",
    "EVAPORATOR_CORE_LEAK",
    "CONDENSER_CLOGGED",
    "BLOWER_MOTOR_RESISTOR_FAILED",
    "CABIN_AIR_FILTER_CLOGGED",
    "AC_PRESSURE_SENSOR_FAILED",
    "AMBIENT_AIR_TEMP_SENSOR_FAILED",
]
