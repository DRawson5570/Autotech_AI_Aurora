"""
Emissions system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


CATALYTIC_CONVERTER_DEGRADED = FailureMode(
    id="catalytic_converter_degraded",
    name="Catalytic Converter Degraded",
    category=FailureCategory.DRIFT,
    component_id="catalytic_converter",
    system_id="emissions",
    immediate_effect="Reduced catalyst efficiency",
    expected_dtcs=["P0420", "P0430"],
    symptoms=[Symptom("Check engine light", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Compare upstream/downstream O2 sensors"],
    repair_actions=["Replace catalytic converter"],
    relative_frequency=0.4,
)


O2_SENSOR_UPSTREAM_FAILED = FailureMode(
    id="o2_sensor_upstream_failed",
    name="Upstream O2 Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="o2_sensor_upstream",
    system_id="emissions",
    immediate_effect="No or incorrect fuel mixture feedback",
    expected_dtcs=["P0131", "P0132", "P0133", "P0134"],
    symptoms=[Symptom("Poor fuel economy", SymptomSeverity.MODERATE)],
    discriminating_tests=["Monitor O2 sensor switching rate", "Check O2 heater circuit resistance"],
    repair_actions=["Replace upstream O2 sensor"],
    relative_frequency=0.5,
)


O2_SENSOR_DOWNSTREAM_FAILED = FailureMode(
    id="o2_sensor_downstream_failed",
    name="Downstream O2 Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="o2_sensor_downstream",
    system_id="emissions",
    immediate_effect="No catalyst efficiency monitoring",
    expected_dtcs=["P0137", "P0138", "P0140", "P0141"],
    symptoms=[Symptom("Check engine light", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Compare downstream to upstream O2 waveform", "Check sensor response to rich/lean condition"],
    repair_actions=["Replace downstream O2 sensor"],
    relative_frequency=0.4,
)


EGR_VALVE_STUCK_CLOSED = FailureMode(
    id="egr_valve_stuck_closed",
    name="EGR Valve Stuck Closed",
    category=FailureCategory.STUCK,
    component_id="egr_valve",
    system_id="emissions",
    immediate_effect="No exhaust gas recirculation",
    expected_dtcs=["P0401"],
    symptoms=[Symptom("Possible engine knock under load", SymptomSeverity.MODERATE)],
    discriminating_tests=["Command EGR open with scan tool - observe engine response", "Inspect EGR passages for carbon buildup"],
    repair_actions=["Clean or replace EGR valve"],
    relative_frequency=0.4,
)


EGR_VALVE_STUCK_OPEN = FailureMode(
    id="egr_valve_stuck_open",
    name="EGR Valve Stuck Open",
    category=FailureCategory.STUCK,
    component_id="egr_valve",
    system_id="emissions",
    immediate_effect="Excessive exhaust gas recirculation",
    expected_dtcs=["P0402", "P0300"],
    symptoms=[Symptom("Rough idle", SymptomSeverity.OBVIOUS)],
    discriminating_tests=["Command EGR closed with scan tool - check if idle improves", "Visual inspection of EGR valve position"],
    repair_actions=["Clean or replace EGR valve"],
    relative_frequency=0.3,
)


EVAP_LEAK_LARGE = FailureMode(
    id="evap_leak_large",
    name="EVAP System Large Leak",
    category=FailureCategory.LEAK,
    component_id="evap_system",
    system_id="emissions",
    immediate_effect="EVAP system cannot hold vacuum",
    expected_dtcs=["P0455", "P0456"],
    symptoms=[Symptom("Fuel smell", SymptomSeverity.MODERATE)],
    discriminating_tests=["Smoke test EVAP system"],
    repair_actions=["Locate and repair leak", "Check gas cap"],
    relative_frequency=0.5,
)


EVAP_PURGE_VALVE_STUCK = FailureMode(
    id="evap_purge_valve_stuck",
    name="EVAP Purge Valve Stuck",
    category=FailureCategory.STUCK,
    component_id="purge_valve",
    system_id="emissions",
    immediate_effect="Improper fuel vapor purging",
    expected_dtcs=["P0441"],
    symptoms=[Symptom("Hard start when hot", SymptomSeverity.MODERATE)],
    discriminating_tests=["Command purge valve with scan tool - listen for click", "Check vacuum at purge valve"],
    repair_actions=["Replace purge valve"],
    relative_frequency=0.3,
)


EVAP_PURGE_CIRCUIT_OPEN = FailureMode(
    id="evap_purge_circuit_open",
    name="EVAP Purge Solenoid Circuit Open",
    category=FailureCategory.ELECTRICAL,
    component_id="purge_valve",
    system_id="emissions",
    immediate_effect="PCM cannot control purge valve - open circuit detected",
    cascade_effects=[
        "No purge flow during engine operation",
        "Fuel tank pressure may build",
        "Possible fuel smell or hard starting",
    ],
    expected_dtcs=["P0443"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Code returns after replacing purge valve", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check 12V power at purge solenoid connector (KOEO)",
        "Check ground signal with scan tool active test - command valve ON",
        "Measure solenoid resistance (typically 15-35 ohms)",
        "Inspect connector pins for corrosion or spread terminals",
        "Check wiring harness for chafing or breaks",
    ],
    repair_actions=[
        "Repair open circuit in wiring harness",
        "Replace damaged connector",
        "Repair corroded terminals",
        "Check PCM driver circuit if wiring OK",
    ],
    relative_frequency=0.4,
)


EVAP_PURGE_CIRCUIT_SHORT = FailureMode(
    id="evap_purge_circuit_short",
    name="EVAP Purge Solenoid Circuit Short",
    category=FailureCategory.ELECTRICAL,
    component_id="purge_valve",
    system_id="emissions",
    immediate_effect="PCM detects short to ground or voltage on purge circuit",
    cascade_effects=[
        "Purge valve may be stuck on or off",
        "Possible blown fuse",
        "Potential PCM driver damage if prolonged",
    ],
    expected_dtcs=["P0443", "P0444", "P0445"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Blown EVAP or emissions fuse", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check for blown fuse (ASD relay circuit or emissions fuse)",
        "Disconnect solenoid - if code clears, solenoid shorted internally",
        "Check wiring for chafing against metal/ground",
        "Measure resistance to ground on control wire (should be high/OL)",
    ],
    repair_actions=[
        "Repair shorted wiring",
        "Replace damaged solenoid",
        "Repair chafed harness",
    ],
    relative_frequency=0.3,
)


EVAP_PURGE_CONNECTOR_FAULT = FailureMode(
    id="evap_purge_connector_fault",
    name="EVAP Purge Solenoid Connector Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="purge_valve",
    system_id="emissions",
    immediate_effect="Poor or no electrical connection at purge solenoid",
    cascade_effects=[
        "Intermittent or no communication with solenoid",
        "Code may return after valve replacement",
    ],
    expected_dtcs=["P0443"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Code returns after replacing purge valve", SymptomSeverity.OBVIOUS),
        Symptom("Intermittent code setting", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Inspect connector for spread/fretting terminals",
        "Check for corrosion or water intrusion",
        "Wiggle test while monitoring with scan tool",
        "Check terminal tension with test pin",
    ],
    repair_actions=[
        "Replace connector/pigtail",
        "Clean and treat corroded terminals",
        "Repair spread terminals or replace connector",
    ],
    relative_frequency=0.5,
)


O2_HEATER_CIRCUIT_FAILED = FailureMode(
    id="o2_heater_circuit_failed",
    name="O2 Sensor Heater Circuit Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="o2_sensor",
    system_id="emissions",
    immediate_effect="O2 sensor takes longer to reach operating temperature",
    cascade_effects=[
        "Delayed closed loop operation",
        "Poor fuel economy during warmup",
        "Increased emissions",
    ],
    expected_dtcs=["P0135", "P0141", "P0155", "P0161", "P0030", "P0036"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check heater circuit resistance (typically 3-15 ohms)",
        "Check for power and ground at heater circuit",
        "Monitor heater current with scan tool",
    ],
    repair_actions=["Replace O2 sensor", "Check wiring and fuse"],
    repair_time_hours=0.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.5,
)


FUEL_TANK_PRESSURE_SENSOR_FAILED = FailureMode(
    id="fuel_tank_pressure_sensor_failed",
    name="Fuel Tank Pressure Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ftp_sensor",
    system_id="emissions",
    immediate_effect="PCM cannot monitor EVAP system pressure",
    cascade_effects=[
        "EVAP system cannot be properly tested",
        "May not detect EVAP leaks",
    ],
    expected_dtcs=["P0451", "P0452", "P0453"],
    symptoms=[
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("EVAP related codes", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check FTP sensor voltage range",
        "Apply pressure/vacuum to tank and monitor sensor",
        "Check wiring and connector",
    ],
    repair_actions=["Replace fuel tank pressure sensor"],
    repair_time_hours=0.5,
    parts_cost_low=50,
    parts_cost_high=150,
    relative_frequency=0.3,
)


DPF_CLOGGED = FailureMode(
    id="dpf_clogged",
    name="Diesel Particulate Filter Clogged",
    category=FailureCategory.BLOCKAGE,
    component_id="dpf",
    system_id="emissions",
    immediate_effect="Exhaust flow restricted by soot buildup",
    cascade_effects=[
        "Reduced power",
        "Limp mode",
        "Increased fuel consumption",
        "Possible engine damage if ignored",
    ],
    expected_dtcs=["P2002", "P2003", "P244A", "P244B"],
    symptoms=[
        Symptom("DPF warning light on", SymptomSeverity.OBVIOUS),
        Symptom("Reduced power/limp mode", SymptomSeverity.SEVERE),
        Symptom("Regeneration not completing", SymptomSeverity.MODERATE),
        Symptom("Increased fuel consumption", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check DPF soot level with scan tool",
        "Check back pressure",
        "Check regeneration history",
    ],
    repair_actions=["Force regeneration", "Clean DPF", "Replace DPF if too clogged"],
    repair_time_hours=2.0,
    parts_cost_low=100,
    parts_cost_high=2000,
    relative_frequency=0.4,
)


DEF_SYSTEM_FAULT = FailureMode(
    id="def_system_fault",
    name="DEF/SCR System Fault (Diesel)",
    category=FailureCategory.ELECTRICAL,
    component_id="def_system",
    system_id="emissions",
    immediate_effect="DEF (urea) system not functioning properly",
    cascade_effects=[
        "High NOx emissions",
        "Potential limp mode",
        "Vehicle may be speed limited",
    ],
    expected_dtcs=["P203B", "P203D", "P207F", "P20E8", "P20EE"],
    symptoms=[
        Symptom("DEF warning light on", SymptomSeverity.OBVIOUS),
        Symptom("Message to add DEF", SymptomSeverity.OBVIOUS),
        Symptom("Speed limited or limp mode", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Check DEF level and quality",
        "Check DEF injector operation",
        "Check SCR catalyst temperature",
        "Scan for DEF system codes",
    ],
    repair_actions=["Fill/replace DEF fluid", "Replace DEF injector", "Replace DEF pump", "Clean SCR catalyst"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=1000,
    relative_frequency=0.3,
)


# Exports
__all__ = [
    "CATALYTIC_CONVERTER_DEGRADED",
    "O2_SENSOR_UPSTREAM_FAILED",
    "O2_SENSOR_DOWNSTREAM_FAILED",
    "EGR_VALVE_STUCK_CLOSED",
    "EGR_VALVE_STUCK_OPEN",
    "EVAP_LEAK_LARGE",
    "EVAP_PURGE_VALVE_STUCK",
    "EVAP_PURGE_CIRCUIT_OPEN",
    "EVAP_PURGE_CIRCUIT_SHORT",
    "EVAP_PURGE_CONNECTOR_FAULT",
    "O2_HEATER_CIRCUIT_FAILED",
    "FUEL_TANK_PRESSURE_SENSOR_FAILED",
    "DPF_CLOGGED",
    "DEF_SYSTEM_FAULT",
]
