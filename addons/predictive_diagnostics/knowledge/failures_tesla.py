"""
Tesla-specific failure modes.

This module defines common failure modes for Tesla vehicles (Model 3, Y, S, X, Cybertruck),
focusing on high-voltage systems, drive units, thermal management, and other Tesla-unique issues.
These complement general EV failures (failures_ev.py) and are tuned for Tesla's proprietary alerts,
diagnostics, and common real-world patterns (e.g., PTC heater coolant intrusion causing isolation faults).

Follows the same structure as other failures_*.py modules for consistency in the registry.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


# sources: NHTSA Tech Note on isolation testing (SB-10052460-6095), Tesla Service Manual (Isolation/Insulation Test)
TESLA_HV_ISOLATION_FAULT = FailureMode(
    id="tesla_hv_isolation_fault",
    name="Tesla High Voltage Isolation Fault (Leakage to Chassis)",
    category=FailureCategory.ELECTRICAL,
    component_id="hv_system",
    system_id="tesla_hv_battery",
    immediate_effect="BMS detects low insulation resistance between HV rails and chassis",
    cascade_effects=[
        "Safety shutdown: HV contactors remain open",
        "Vehicle cannot enter READY mode",
        "No propulsion or HV charging",
        "Potential reduced power/limp mode",
    ],
    # Include Tesla proprietary DTC and PID effect so causal graph and evidence match
    expected_dtcs=["BMS_f035"],  # Tesla proprietary isolation alert
    pid_effects=[PIDEffect(pid_name="insulation_resistance", effect="low", typical_value="<1 MΩ", description="Low insulation resistance between HV rails and chassis (MΩ)")],
    expected_alerts=["BMS_f035", "BMS_u018", "isoFault", "P0AA1"],  # include generic isolation DTC where applicable
    references=[
        "https://static.nhtsa.gov/odi/tsbs/2013/SB-10052460-6095.pdf",  # NHTSA Tech Note: Isolation/Insulation guidance
        "https://service.tesla.com/docs/Model3/ServiceManual/en-us/GUID-41BA9871-C6AA-4157-937D-D7CB2DB2B9A7.html",  # Tesla Service Manual: Isolation/Insulation Test
    ],
    symptoms=[
        Symptom("High voltage isolation fault warning on dashboard", SymptomSeverity.SEVERE),
        Symptom("Vehicle won't enter READY mode", SymptomSeverity.SEVERE),
        Symptom("Cannot drive or charge", SymptomSeverity.SEVERE),
        Symptom("No unusual heat, smells, or smoke", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Scan for specific BMS/VCFRONT alerts to pinpoint component (e.g., Cabin Heater, Compressor)",
        "Megohmmeter test: HV+ to chassis and HV- to chassis (>500 MΩ expected)",
        "Sequential disconnection: Unplug PTC cabin heater, A/C compressor, drive units, and re-test isolation",
        "Visual inspection for coolant leaks at PTC heater or compressor",
        "Check battery penthouse for water intrusion or corrosion",
    ],
    repair_actions=[
        "Replace PTC cabin/battery heater (most common cause: coolant seal failure)",
        "Replace A/C compressor if leaking",
        "Repair/replace damaged HV orange cabling or connectors",
        "Dry and reseal penthouse if water ingress",
    ],
    repair_time_hours=4.0,
    parts_cost_low=800,
    parts_cost_high=4000,
    relative_frequency=0.95,  # Extremely common in Model 3/Y
)


# sources: Tesla Service Manual (PTC heater R&R), owner/tech diagnostics threads corroborate isolation failures linked to PTC coolant intrusion
TESLA_PTC_HEATER_FAILURE = FailureMode(
    id="tesla_ptc_heater_failure",
    name="Tesla PTC Cabin/Battery Heater Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="ptc_heater",
    system_id="tesla_thermal",
    immediate_effect="HV heater element or coolant loop failure",
    cascade_effects=[
        "No cabin preconditioning or battery heating in cold",
        "Often triggers isolation fault due to coolant intrusion",
        "Reduced cold-weather range/performance",
    ],
    expected_dtcs=[],  # Alerts: BMS_f035 (common isolation trigger), heater circuit faults
    expected_alerts=["BMS_f035", "Isolation fault"],
    references=[
        "https://service.tesla.com/docs/Model3/ServiceManual/en-us/GUID-2C41494D-BC74-474C-8438-3A032F01B1A3.html",  # Tesla Service Manual: PTC heater R&R
        "https://teslamotorsclub.com/threads/need-help-understanding-these-battery-coolant-heater-diagnostics.318456/",  # Owner reports and diagnostic discussions
    ],
    symptoms=[
        Symptom("No cabin heat or preconditioning", SymptomSeverity.MODERATE),
        Symptom("Isolation fault in cold/wet conditions", SymptomSeverity.SEVERE),
        Symptom("Reduced power/range when cold", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check heater current draw and resistance",
        "Inspect for coolant leak into heater housing",
        "Monitor battery temp vs precondition request",
    ],
    repair_actions=["Replace PTC heater assembly"],
    repair_time_hours=3.0,
    parts_cost_low=1200,
    parts_cost_high=2500,
    relative_frequency=0.85,
)


# sources: NHTSA TSBs and Tesla technical bulletins on drive unit clunk/hum (see NHTSA TSB docs)
TESLA_DRIVE_UNIT_NOISE = FailureMode(
    id="tesla_drive_unit_noise",
    name="Tesla Drive Unit Whine/Humming (Bearing Wear)",
    category=FailureCategory.MECHANICAL,
    component_id="drive_unit",
    system_id="tesla_powertrain",
    immediate_effect="Bearing or gear wear in front/rear drive unit",
    cascade_effects=[
        "Increasing noise with speed/mileage",
        "Potential eventual failure",
    ],
    expected_dtcs=[],  # Usually no codes until severe
    expected_alerts=[],
    references=[
        "https://static.nhtsa.gov/odi/tsbs/2019/MC-10162295-9999.pdf",  # NHTSA TSB: Replace LH Front Drive Unit Clevis Mount and Halfshafts
        "https://static.nhtsa.gov/odi/tsbs/2021/MC-10203323-9999.pdf",  # NHTSA TSB: Drive unit vibration/clunk guidance
    ],
    symptoms=[ 
        Symptom("Whining or humming noise from front/rear", SymptomSeverity.MODERATE),
        Symptom("Noise increases with speed", SymptomSeverity.OBVIOUS),
        Symptom("Common at 50k–100k miles", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Road test at highway speeds",
        "Lift vehicle and spin wheels by hand",
        "Compare front vs rear unit",
    ],
    repair_actions=["Replace affected drive unit (warranty common up to 150k miles on some models)"],
    repair_time_hours=5.0,
    parts_cost_low=3000,
    parts_cost_high=7000,
    relative_frequency=0.8,
)


# sources: Owner/tech writeups and recall/support pages discussing frequent 12V battery failures and warning messages
TESLA_12V_BATTERY_FAILURE = FailureMode(
    id="tesla_12v_battery_failure",
    name="Tesla 12V Auxiliary Battery Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="12v_battery",
    system_id="tesla_auxiliary",
    immediate_effect="Low voltage system unstable",
    cascade_effects=[
        "Random warnings, accessory failures",
        "Vehicle may not wake or enter READY",
        "HV contactor issues secondary",
    ],
    expected_dtcs=[],  # Alerts: low voltage battery, service 12V soon
    expected_alerts=["12V_battery_low", "12V Battery Must Be Replaced Soon", "12V battery needs service"],
    references=[
        "https://evclinic.eu/2025/04/12/model-3-12v-battery-failure-mistakes-owners-make/",  # Owner/tech writeup on 12V failures
        "https://www.tesla.com/support/annual-and-recall-service",  # Tesla recall/support & VIN recall lookup
        "https://www.teslarati.com/understanding-tesla-12v-battery-service-warning/",  # Explainer on common 12V warnings
    ],
    symptoms=[ 
        Symptom("12V battery warning or random electrical glitches", SymptomSeverity.MODERATE),
        Symptom("Vehicle won't wake from app", SymptomSeverity.MODERATE),
        Symptom("Clicking relays on startup", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Check 12V voltage (should hold >12.4V off, >13.5V running)",
        "Load test battery",
    ],
    repair_actions=["Replace 12V battery (Li-ion in newer models)"],
    repair_time_hours=0.5,
    parts_cost_low=150,
    parts_cost_high=300,
    relative_frequency=0.7,
)


# sources: NHTSA TSB: Replace Charge Port Latch Actuator Carrier; Tesla SB: Inspect & Adjust Charge Port Door
TESLA_CHARGE_PORT_FAULT = FailureMode(
    id="tesla_charge_port_fault",
    name="Tesla Charge Port / Inlet Fault",
    category=FailureCategory.ELECTRICAL,
    component_id="charge_port",
    system_id="tesla_charging",
    immediate_effect="Charging communication or latch failure",
    cascade_effects=[
        "Charging won't initiate or interrupts",
        "Port door issues on motorized models",
    ],
    expected_dtcs=[],  # Alerts: charge port fault, latch error
    expected_alerts=["charge_port_fault", "latch_error", "Charge Port Latch Not Engaged"],
    references=[
        "https://static.nhtsa.gov/odi/tsbs/2017/MC-10142966-9999.pdf",  # NHTSA TSB: Replace Charge Port Latch Actuator Carrier
        "https://service.tesla.com/docs/ServiceBulletins/External/SB/SB-23-44-001_Inspect_and_Adjust_Charge_Port_Door_to_Ensure_Proper_Latch_Operation.pdf",  # Tesla Service Bulletin: Inspect & adjust charge port door
    ],
    symptoms=[ 
        Symptom("Charging session fails to start", SymptomSeverity.OBVIOUS),
        Symptom("Charge port door won't open/close", SymptomSeverity.MODERATE),
        Symptom("Red ring on port", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Inspect port pins for damage/bent",
        "Test latch actuator",
        "Check pilot/proximity signals",
    ],
    repair_actions=["Replace charge port assembly or latch motor"],
    repair_time_hours=2.0,
    parts_cost_low=500,
    parts_cost_high=1500,
    relative_frequency=0.6,
)


# sources: Tesla recall/Service info for battery pack contactor defects and NHTSA recall documents
TESLA_CONTACTOR_FAILURE = FailureMode(
    id="tesla_contactor_failure",
    name="Tesla HV Contactor Stuck/Welded or Precharge Failure",
    category=FailureCategory.ELECTRICAL,
    component_id="hv_contactor",
    system_id="tesla_hv_battery",
    immediate_effect="Contactors fail to close or open properly",
    cascade_effects=[
        "No READY mode",
        "Intermittent propulsion",
    ],
    expected_dtcs=[],  # Alerts: contactor seize, precharge fault
    expected_alerts=["contactor_fault", "precharge_fault"],
    references=[
        "https://www.tesla.com/support/recall-battery-pack-contactor",  # Tesla Support: Battery Pack Contactor recall
        "https://static.nhtsa.gov/odi/rcl/2025/RCLRPT-25V690-9693.pdf",  # NHTSA Recall report: Battery pack contactor (RCLRPT-25V690-9693)
    ],
    symptoms=[ 
        Symptom("Vehicle intermittently won't enter READY", SymptomSeverity.SEVERE),
        Symptom("Clicking from battery pack", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Listen for contactor engagement click",
        "Monitor precharge circuit and contactor feedback in service mode",
        "Check pyrofuse status",
    ],
    repair_actions=["Replace battery penthouse assembly (contactors integrated)"],
    repair_time_hours=6.0,
    parts_cost_low=2000,
    parts_cost_high=8000,
    relative_frequency=0.4,
)


# Exports - add to failures.py re-exports and FAILURE_REGISTRY
__all__ = [
    "TESLA_HV_ISOLATION_FAULT",
    "TESLA_PTC_HEATER_FAILURE",
    "TESLA_DRIVE_UNIT_NOISE",
    "TESLA_12V_BATTERY_FAILURE",
    "TESLA_CHARGE_PORT_FAULT",
    "TESLA_CONTACTOR_FAILURE",
]