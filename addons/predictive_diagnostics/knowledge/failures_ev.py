"""
EV (Electric Vehicle) system failure modes.

This module defines common failure modes specific to electric vehicles,
including high-voltage battery, traction motor, inverter, charging system,
and thermal management components.

Follows the same structure as other failures_*.py modules for consistency.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


HV_BATTERY_CELL_IMBALANCE = FailureMode(
    id="hv_battery_cell_imbalance",
    name="HV Battery Cell Imbalance",
    category=FailureCategory.DRIFT,
    component_id="hv_battery_pack",
    system_id="ev_battery",
    immediate_effect="Voltage differences between cells exceed limits",
    cascade_effects=[
        "Reduced usable capacity",
        "BMS limits charging/discharging",
        "Potential long-term degradation",
        "Reduced range",
    ],
    expected_dtcs=["P0A1F", "P0A00", "P0AC0"],  # Common hybrid/EV cell balance codes
    symptoms=[
        Symptom("Reduced electric range", SymptomSeverity.MODERATE),
        Symptom("Charging stops prematurely", SymptomSeverity.MODERATE),
        Symptom("Battery warning light", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Scan for cell voltage data - max/min delta > spec (typically >0.1-0.3V)",
        "Monitor cell voltages during charge/discharge",
        "Check BMS history for balance events",
    ],
    repair_actions=["Perform battery balance procedure", "Replace weak module if persistent"],
    repair_time_hours=2.0,
    parts_cost_low=500,
    parts_cost_high=5000,
    relative_frequency=0.5,
)


HV_CONTACTOR_STUCK_OPEN = FailureMode(
    id="hv_contactor_stuck_open",
    name="HV Contactor Stuck Open",
    category=FailureCategory.STUCK,
    component_id="hv_contactor",
    system_id="ev_battery",
    immediate_effect="High-voltage circuit cannot close",
    cascade_effects=[
        "Vehicle cannot enter ready/drive mode",
        "No propulsion",
        "Possible 12V system drain",
    ],
    expected_dtcs=["P0A0A", "P0AA6", "P0A94"],
    symptoms=[
        Symptom("Vehicle won't go into READY mode", SymptomSeverity.SEVERE),
        Symptom("High voltage system fault warning", SymptomSeverity.OBVIOUS),
        Symptom("No response when pressing accelerator", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Listen for contactor click on key-on",
        "Check pre-charge circuit",
        "Scan for contactor feedback signal",
    ],
    repair_actions=["Replace main contactor assembly"],
    repair_time_hours=3.0,
    parts_cost_low=800,
    parts_cost_high=2000,
    relative_frequency=0.4,
)


HV_ISOLATION_FAULT = FailureMode(
    id="hv_isolation_fault",
    name="High Voltage Isolation Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="hv_system",
    system_id="ev_battery",
    immediate_effect="Leakage current from HV to chassis",
    cascade_effects=[
        "HV system shutdown for safety",
        "No propulsion",
        "Charging disabled",
    ],
    expected_dtcs=["P0AA1", "P0AA4", "P0A1D"],
    symptoms=[
        Symptom("Isolation fault warning", SymptomSeverity.SEVERE),
        Symptom("Vehicle in limp/safe mode", SymptomSeverity.SEVERE),
        Symptom("Cannot charge or drive", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Use insulation tester on HV system",
        "Check for water intrusion or damaged HV cables",
        "Isolate components to find leakage path",
    ],
    repair_actions=["Repair damaged HV cable/connector", "Replace faulty component (inverter, compressor, etc.)"],
    repair_time_hours=4.0,
    parts_cost_low=200,
    parts_cost_high=3000,
    relative_frequency=0.4,
)


BATTERY_THERMAL_RUNAWAY_RISK = FailureMode(
    id="battery_thermal_runaway_risk",
    name="Battery Thermal Runaway Risk Detected",
    category=FailureCategory.THERMAL,
    component_id="hv_battery_pack",
    system_id="ev_battery",
    immediate_effect="BMS detects abnormal temperature rise or gas",
    cascade_effects=[
        "Immediate HV shutdown",
        "Vehicle immobilized",
        "Potential fire hazard",
    ],
    expected_dtcs=["P0A0F", "P0A7F", "P0A80"],  # Thermal event codes
    symptoms=[
        Symptom("Battery fire/thermal event warning", SymptomSeverity.SEVERE),
        Symptom("Smell of off-gassing", SymptomSeverity.SEVERE),
        Symptom("Vehicle shuts down unexpectedly", SymptomSeverity.SEVERE),
    ],
    discriminating_tests=[
        "Check battery temperature sensors",
        "Inspect for physical damage or swelling",
        "Review event logs in BMS",
    ],
    repair_actions=["Quarantine vehicle", "Professional battery pack inspection/replacement"],
    repair_time_hours=8.0,
    parts_cost_low=5000,
    parts_cost_high=20000,
    relative_frequency=0.1,
)


INVERTER_FAILURE = FailureMode(
    id="inverter_failure",
    name="Traction Inverter Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="traction_inverter",
    system_id="ev_powertrain",
    immediate_effect="No AC power to traction motor",
    cascade_effects=[
        "No propulsion",
        "Reduced power or limp mode",
    ],
    expected_dtcs=["P0A78", "P0A79", "P0A3F"],
    symptoms=[
        Symptom("Power delivery fault", SymptomSeverity.SEVERE),
        Symptom("Vehicle won't move", SymptomSeverity.SEVERE),
        Symptom("Inverter fault light", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check IGBT/module temperatures",
        "Scan for phase current faults",
        "Test gate driver signals",
    ],
    repair_actions=["Replace inverter assembly"],
    repair_time_hours=4.0,
    parts_cost_low=2000,
    parts_cost_high=8000,
    relative_frequency=0.3,
)


TRACTION_MOTOR_RESOLVER_FAULT = FailureMode(
    id="traction_motor_resolver_fault",
    name="Traction Motor Resolver/Position Sensor Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="traction_motor",
    system_id="ev_powertrain",
    immediate_effect="Incorrect rotor position feedback",
    cascade_effects=[
        "Jerky or no propulsion",
        "Reduced torque",
        "Limp mode",
    ],
    expected_dtcs=["P0A3C", "P0A3D", "P0C1A"],
    symptoms=[
        Symptom("Jerky acceleration", SymptomSeverity.OBVIOUS),
        Symptom("Reduced power message", SymptomSeverity.MODERATE),
        Symptom("Motor noise or vibration", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check resolver waveform with oscilloscope",
        "Verify excitation signal",
        "Swap with known good if possible",
    ],
    repair_actions=["Replace resolver or motor assembly"],
    repair_time_hours=5.0,
    parts_cost_low=1000,
    parts_cost_high=5000,
    relative_frequency=0.3,
)


ONBOARD_CHARGER_FAILURE = FailureMode(
    id="onboard_charger_failure",
    name="Onboard Charger (OBC) Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="onboard_charger",
    system_id="ev_charging",
    immediate_effect="Cannot convert AC to DC for battery charging",
    cascade_effects=[
        "No Level 1/2 charging",
        "DC fast charging may still work",
    ],
    expected_dtcs=["P0D2D", "P0D30", "P0AED"],
    symptoms=[
        Symptom("Charging fault when plugged in", SymptomSeverity.OBVIOUS),
        Symptom("No charge current on AC", SymptomSeverity.OBVIOUS),
        Symptom("Charging interrupted", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Monitor AC input vs DC output",
        "Check pilot signal communication",
        "Test OBC temperature sensors",
    ],
    repair_actions=["Replace onboard charger module"],
    repair_time_hours=3.0,
    parts_cost_low=1000,
    parts_cost_high=4000,
    relative_frequency=0.4,
)


CHARGE_PORT_FAULT = FailureMode(
    id="charge_port_fault",
    name="Charge Port / CCID Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="charge_port",
    system_id="ev_charging",
    immediate_effect="Improper communication or detection of charger",
    cascade_effects=[
        "Charging refused or interrupted",
        "No pilot signal",
    ],
    expected_dtcs=["P0D3A", "P0D3B", "P0D2F"],
    symptoms=[
        Symptom("Charging won't start", SymptomSeverity.OBVIOUS),
        Symptom("Charge port door issues (if powered)", SymptomSeverity.MODERATE),
        Symptom("Fault light on port", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check proximity and pilot signals with multimeter",
        "Inspect port for damage/contamination",
        "Test with known good EVSE",
    ],
    repair_actions=["Clean/replace charge port assembly", "Replace latch actuator if equipped"],
    repair_time_hours=1.5,
    parts_cost_low=200,
    parts_cost_high=1000,
    relative_frequency=0.5,
)


BATTERY_COOLANT_PUMP_FAILURE = FailureMode(
    id="battery_coolant_pump_failure",
    name="Battery Coolant Pump Failure",
    category=FailureCategory.MECHANICAL,
    component_id="battery_coolant_pump",
    system_id="ev_thermal",
    immediate_effect="Reduced or no coolant flow to battery pack",
    cascade_effects=[
        "Battery overheating",
        "Reduced power/charging rate",
        "Thermal shutdown",
    ],
    expected_dtcs=["P0A01", "P0C00", "P0A08"],
    symptoms=[
        Symptom("Battery temperature high warning", SymptomSeverity.MODERATE),
        Symptom("Reduced power in hot conditions", SymptomSeverity.MODERATE),
        Symptom("Cooling fan runs constantly", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check pump operation (current draw/sound)",
        "Monitor coolant flow sensor if equipped",
        "Pressure test cooling loop",
    ],
    repair_actions=["Replace electric coolant pump"],
    repair_time_hours=2.0,
    parts_cost_low=300,
    parts_cost_high=800,
    relative_frequency=0.4,
)


# Exports - add these to failures.py re-exports and FAILURE_REGISTRY
__all__ = [
    "HV_BATTERY_CELL_IMBALANCE",
    "HV_CONTACTOR_STUCK_OPEN",
    "HV_ISOLATION_FAULT",
    "BATTERY_THERMAL_RUNAWAY_RISK",
    "INVERTER_FAILURE",
    "TRACTION_MOTOR_RESOLVER_FAULT",
    "ONBOARD_CHARGER_FAILURE",
    "CHARGE_PORT_FAULT",
    "BATTERY_COOLANT_PUMP_FAILURE",
]
