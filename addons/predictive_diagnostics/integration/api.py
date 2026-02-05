"""
Diagnostic Engine API - The unified entry point

This is the culmination of the predictive diagnostics system.
Takes sensor data and returns probable causes with confidence scores.

Pipeline:
  Sensor Data → ML Inference → Bayesian Reasoning → Conclusion

Design principle: "Failures are physics, not patterns"
- ML provides initial priors from learned patterns
- Bayesian reasoning updates beliefs as evidence arrives
- Knowledge graph provides causal understanding
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge import CausalGraph
from knowledge.failures import get_all_failure_modes, get_failure_by_id
from reasoning import BayesianReasoner, BeliefState, Diagnostician, DiagnosticConclusion
from reasoning.diagnostician import quick_diagnose as reasoning_quick_diagnose

# Try to import hierarchical inference (legacy)
try:
    from ml.inference import HierarchicalInference, get_hierarchical_inference
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False

# Try to import TwoStageXGB inference (preferred - 90%+ accuracy)
try:
    from inference_engine import TwoStageXGBPredictor
    TWOSTAGE_AVAILABLE = True
except ImportError:
    try:
        from ..inference_engine import TwoStageXGBPredictor
        TWOSTAGE_AVAILABLE = True
    except ImportError:
        TWOSTAGE_AVAILABLE = False


class DiagnosticPhase(Enum):
    """Current phase of diagnosis"""
    INITIAL = "initial"           # Just started, gathering data
    INVESTIGATING = "investigating"  # Running tests
    CONFIDENT = "confident"       # High confidence diagnosis
    CONCLUDED = "concluded"       # Diagnosis complete


@dataclass
class SensorReading:
    """A single sensor reading with metadata"""
    name: str                    # e.g., "coolant_temp"
    value: float                 # Raw value
    unit: str = ""               # e.g., "°C", "psi"
    timestamp: float = 0.0       # When reading was taken
    
    def __post_init__(self):
        """Normalize sensor name"""
        self.name = self.name.lower().replace(" ", "_")


@dataclass 
class DTCCode:
    """Diagnostic Trouble Code"""
    code: str                    # e.g., "P0217"
    description: str = ""        # Human-readable description
    system: str = ""             # Which system it relates to
    
    # Known DTC mappings to evidence
    DTC_TO_EVIDENCE = {
        # =====================================================================
        # COOLING SYSTEM (P011x, P012x, P021x, P048x)
        # =====================================================================
        "P0217": "coolant_temp_high",      # Engine overtemp
        "P0128": "coolant_temp_low",       # Thermostat stuck open
        "P0480": "fan_not_running",        # Cooling fan circuit
        "P0481": "fan_not_running",        # Cooling fan 2 circuit
        "P0117": "ect_reading_low",        # ECT sensor low
        "P0118": "ect_reading_high",       # ECT sensor high
        "P0125": "coolant_temp_low",       # Insufficient temp for fuel
        "P0116": "ect_reading_erratic",    # ECT sensor range
        "P0115": "ect_circuit",            # ECT circuit malfunction
        "P0119": "ect_intermittent",       # ECT circuit intermittent
        
        # =====================================================================
        # FUEL SYSTEM (P017x, P008x, P019x, P02xx)
        # =====================================================================
        "P0171": "system_lean_bank1",      # System too lean bank 1
        "P0172": "system_rich_bank1",      # System too rich bank 1
        "P0174": "system_lean_bank2",      # System too lean bank 2
        "P0175": "system_rich_bank2",      # System too rich bank 2
        "P0170": "fuel_trim_bank1",        # Fuel trim malfunction bank 1
        "P0173": "fuel_trim_bank2",        # Fuel trim malfunction bank 2
        "P0087": "fuel_pressure_low",      # Fuel rail pressure too low
        "P0088": "fuel_pressure_high",     # Fuel rail pressure too high
        "P0089": "fuel_pressure_regulator",# Fuel pressure regulator performance
        "P0093": "fuel_system_leak",       # Fuel system leak detected
        "P0230": "fuel_pump_circuit",      # Fuel pump primary circuit
        "P0231": "fuel_pump_secondary",    # Fuel pump secondary circuit low
        "P0232": "fuel_pump_secondary_high",# Fuel pump secondary circuit high
        "P0190": "fuel_pressure_sensor",   # Fuel rail pressure sensor circuit
        "P0191": "fuel_pressure_erratic",  # Fuel rail pressure sensor range
        "P0192": "fuel_pressure_low_input",# Fuel rail pressure sensor low
        "P0193": "fuel_pressure_high_input",# Fuel rail pressure sensor high
        "P0201": "injector_circuit_cyl1",  # Injector circuit cyl 1
        "P0202": "injector_circuit_cyl2",  # Injector circuit cyl 2
        "P0203": "injector_circuit_cyl3",  # Injector circuit cyl 3
        "P0204": "injector_circuit_cyl4",  # Injector circuit cyl 4
        "P0205": "injector_circuit_cyl5",  # Injector circuit cyl 5
        "P0206": "injector_circuit_cyl6",  # Injector circuit cyl 6
        "P0207": "injector_circuit_cyl7",  # Injector circuit cyl 7
        "P0208": "injector_circuit_cyl8",  # Injector circuit cyl 8
        "P0261": "injector_low_cyl1",      # Injector circuit low cyl 1
        "P0264": "injector_low_cyl2",      # Injector circuit low cyl 2
        "P0267": "injector_low_cyl3",      # Injector circuit low cyl 3
        "P0270": "injector_low_cyl4",      # Injector circuit low cyl 4
        
        # =====================================================================
        # IGNITION/MISFIRE (P03xx)
        # =====================================================================
        "P0300": "random_misfire",         # Random/multiple cylinder misfire
        "P0301": "misfire_cyl1",           # Cylinder 1 misfire
        "P0302": "misfire_cyl2",           # Cylinder 2 misfire
        "P0303": "misfire_cyl3",           # Cylinder 3 misfire
        "P0304": "misfire_cyl4",           # Cylinder 4 misfire
        # Tesla proprietary isolation alert - map to a DTC-specific evidence type so it counts separately from numeric PID evidence
        "BMS_F035": "dtc_insulation_resistance_low",
        "P0305": "misfire_cyl5",           # Cylinder 5 misfire
        "P0306": "misfire_cyl6",           # Cylinder 6 misfire
        "P0307": "misfire_cyl7",           # Cylinder 7 misfire
        "P0308": "misfire_cyl8",           # Cylinder 8 misfire
        "P0351": "ignition_coil_a",        # Ignition coil A primary circuit
        "P0352": "ignition_coil_b",        # Ignition coil B primary circuit
        "P0353": "ignition_coil_c",        # Ignition coil C primary circuit
        "P0354": "ignition_coil_d",        # Ignition coil D primary circuit
        "P0355": "ignition_coil_e",        # Ignition coil E primary circuit
        "P0356": "ignition_coil_f",        # Ignition coil F primary circuit
        "P0357": "ignition_coil_g",        # Ignition coil G primary circuit
        "P0358": "ignition_coil_h",        # Ignition coil H primary circuit
        "P0325": "knock_sensor_1",         # Knock sensor 1 circuit
        "P0326": "knock_sensor_1_range",   # Knock sensor 1 range/performance
        "P0327": "knock_sensor_1_low",     # Knock sensor 1 low input
        "P0328": "knock_sensor_1_high",    # Knock sensor 1 high input
        "P0330": "knock_sensor_2",         # Knock sensor 2 circuit
        "P0335": "ckp_sensor",             # Crankshaft position sensor circuit
        "P0336": "ckp_sensor_range",       # CKP sensor range/performance
        "P0337": "ckp_sensor_low",         # CKP sensor low input
        "P0338": "ckp_sensor_high",        # CKP sensor high input
        "P0340": "cmp_sensor_bank1",       # Camshaft position sensor bank 1
        "P0341": "cmp_sensor_range",       # CMP sensor range/performance
        "P0345": "cmp_sensor_bank2",       # Camshaft position sensor bank 2
        
        # =====================================================================
        # AIR INTAKE/MAF/MAP (P010x, P050x)
        # =====================================================================
        "P0100": "maf_circuit",            # MAF circuit malfunction
        "P0101": "maf_range",              # MAF sensor range/performance
        "P0102": "maf_low",                # MAF sensor low input
        "P0103": "maf_high",               # MAF sensor high input
        "P0104": "maf_intermittent",       # MAF circuit intermittent
        "P0105": "map_circuit",            # MAP circuit malfunction
        "P0106": "map_range",              # MAP sensor range/performance
        "P0107": "map_low",                # MAP sensor low input
        "P0108": "map_high",               # MAP sensor high input
        "P0110": "iat_circuit",            # Intake air temp circuit
        "P0111": "iat_range",              # IAT sensor range/performance
        "P0112": "iat_low",                # IAT sensor low input
        "P0113": "iat_high",               # IAT sensor high input
        "P0505": "idle_control",           # Idle air control system
        "P0506": "idle_rpm_low",           # Idle RPM lower than expected
        "P0507": "idle_rpm_high",          # Idle RPM higher than expected
        "P0508": "iac_low",                # Idle air control low
        "P0509": "iac_high",               # Idle air control high
        
        # =====================================================================
        # THROTTLE/PEDAL POSITION (P012x, P022x)
        # =====================================================================
        "P0120": "tps_circuit",            # Throttle position sensor circuit
        "P0121": "tps_range",              # TPS range/performance
        "P0122": "tps_low",                # TPS low input
        "P0123": "tps_high",               # TPS high input
        "P0220": "tps_b_circuit",          # Throttle position sensor B circuit
        "P0221": "tps_b_range",            # TPS B range/performance
        "P0222": "tps_b_low",              # TPS B low input
        "P0223": "tps_b_high",             # TPS B high input
        "P2135": "tps_correlation",        # TPS A/B correlation
        "P2138": "app_correlation",        # Accelerator pedal position correlation
        
        # =====================================================================
        # CHARGING SYSTEM (P056x)
        # =====================================================================
        "P0562": "system_voltage_low",     # System voltage low
        "P0563": "system_voltage_high",    # System voltage high
        "P0560": "system_voltage",         # System voltage malfunction
        "P0561": "system_voltage_unstable",# System voltage unstable
        
        # =====================================================================
        # O2 SENSORS (P013x, P014x, P015x)
        # =====================================================================
        "P0130": "o2_sensor_b1s1",         # O2 sensor circuit bank 1 sensor 1
        "P0131": "o2_low_voltage_b1s1",    # O2 sensor low voltage B1S1
        "P0132": "o2_high_voltage_b1s1",   # O2 sensor high voltage B1S1
        "P0133": "o2_slow_response_b1s1",  # O2 sensor slow response B1S1
        "P0134": "o2_no_activity_b1s1",    # O2 sensor no activity B1S1
        "P0135": "o2_heater_b1s1",         # O2 heater circuit B1S1
        "P0136": "o2_sensor_b1s2",         # O2 sensor circuit bank 1 sensor 2
        "P0137": "o2_low_voltage_b1s2",    # O2 sensor low voltage B1S2
        "P0138": "o2_high_voltage_b1s2",   # O2 sensor high voltage B1S2
        "P0139": "o2_slow_response_b1s2",  # O2 sensor slow response B1S2
        "P0140": "o2_no_activity_b1s2",    # O2 sensor no activity B1S2
        "P0141": "o2_heater_b1s2",         # O2 heater circuit B1S2
        "P0150": "o2_sensor_b2s1",         # O2 sensor circuit bank 2 sensor 1
        "P0151": "o2_low_voltage_b2s1",    # O2 sensor low voltage B2S1
        "P0152": "o2_high_voltage_b2s1",   # O2 sensor high voltage B2S1
        "P0153": "o2_slow_response_b2s1",  # O2 sensor slow response B2S1
        "P0154": "o2_no_activity_b2s1",    # O2 sensor no activity B2S1
        "P0155": "o2_heater_b2s1",         # O2 heater circuit B2S1
        "P0156": "o2_sensor_b2s2",         # O2 sensor circuit bank 2 sensor 2
        "P0157": "o2_low_voltage_b2s2",    # O2 sensor low voltage B2S2
        "P0158": "o2_high_voltage_b2s2",   # O2 sensor high voltage B2S2
        
        # =====================================================================
        # CATALYST/EMISSIONS (P042x, P043x)
        # =====================================================================
        "P0420": "catalyst_efficiency_b1", # Catalyst efficiency below threshold bank 1
        "P0421": "catalyst_warmup_b1",     # Warm up catalyst efficiency below threshold bank 1
        "P0430": "catalyst_efficiency_b2", # Catalyst efficiency below threshold bank 2
        "P0431": "catalyst_warmup_b2",     # Warm up catalyst efficiency below threshold bank 2
        
        # =====================================================================
        # EVAP SYSTEM (P044x, P045x, P046x)
        # =====================================================================
        "P0440": "evap_system",            # EVAP system malfunction
        "P0441": "evap_purge_flow",        # EVAP incorrect purge flow
        "P0442": "evap_small_leak",        # EVAP small leak detected
        "P0443": "evap_purge_circuit",     # EVAP purge control circuit
        "P0444": "evap_purge_open",        # EVAP purge control circuit open
        "P0445": "evap_purge_shorted",     # EVAP purge control circuit shorted
        "P0446": "evap_vent_control",      # EVAP vent control circuit
        "P0447": "evap_vent_open",         # EVAP vent control circuit open
        "P0448": "evap_vent_shorted",      # EVAP vent control circuit shorted
        "P0449": "evap_vent_valve",        # EVAP vent valve circuit
        "P0450": "evap_pressure_sensor",   # EVAP pressure sensor
        "P0451": "evap_pressure_range",    # EVAP pressure sensor range
        "P0452": "evap_pressure_low",      # EVAP pressure sensor low
        "P0453": "evap_pressure_high",     # EVAP pressure sensor high
        "P0455": "evap_large_leak",        # EVAP large leak detected
        "P0456": "evap_very_small_leak",   # EVAP very small leak detected
        "P0457": "evap_loose_cap",         # EVAP loose fuel cap
        
        # =====================================================================
        # EGR SYSTEM (P040x)
        # =====================================================================
        "P0400": "egr_flow",               # EGR flow malfunction
        "P0401": "egr_insufficient_flow",  # EGR insufficient flow
        "P0402": "egr_excessive_flow",     # EGR excessive flow
        "P0403": "egr_circuit",            # EGR circuit malfunction
        "P0404": "egr_range",              # EGR range/performance
        "P0405": "egr_sensor_low",         # EGR sensor A low
        "P0406": "egr_sensor_high",        # EGR sensor A high
        
        # =====================================================================
        # TRANSMISSION (P07xx, P08xx)
        # =====================================================================
        "P0700": "trans_control_system",   # Transmission control system
        "P0705": "trans_range_sensor",     # Trans range sensor circuit
        "P0706": "trans_range_performance",# Trans range sensor performance
        "P0710": "trans_fluid_temp",       # Trans fluid temp sensor circuit
        "P0711": "trans_fluid_temp_range", # Trans fluid temp sensor range
        "P0715": "input_speed_sensor",     # Input/turbine speed sensor
        "P0716": "input_speed_range",      # Input speed sensor range
        "P0717": "input_speed_no_signal",  # Input speed sensor no signal
        "P0720": "output_speed_sensor",    # Output speed sensor circuit
        "P0721": "output_speed_range",     # Output speed sensor range
        "P0722": "output_speed_no_signal", # Output speed sensor no signal
        "P0725": "engine_speed_input",     # Engine speed input circuit
        "P0730": "incorrect_gear_ratio",   # Incorrect gear ratio
        "P0731": "gear_1_ratio",           # Gear 1 incorrect ratio
        "P0732": "gear_2_ratio",           # Gear 2 incorrect ratio
        "P0733": "gear_3_ratio",           # Gear 3 incorrect ratio
        "P0734": "gear_4_ratio",           # Gear 4 incorrect ratio
        "P0735": "gear_5_ratio",           # Gear 5 incorrect ratio
        "P0740": "tcc_circuit",            # Torque converter clutch circuit
        "P0741": "tcc_stuck_off",          # TCC stuck off
        "P0742": "tcc_stuck_on",           # TCC stuck on
        "P0743": "tcc_electrical",         # TCC circuit electrical
        "P0744": "tcc_intermittent",       # TCC circuit intermittent
        "P0750": "shift_solenoid_a",       # Shift solenoid A
        "P0751": "shift_solenoid_a_perf",  # Shift solenoid A performance
        "P0752": "shift_solenoid_a_stuck", # Shift solenoid A stuck on
        "P0753": "shift_solenoid_a_elec",  # Shift solenoid A electrical
        "P0755": "shift_solenoid_b",       # Shift solenoid B
        "P0756": "shift_solenoid_b_perf",  # Shift solenoid B performance
        "P0757": "shift_solenoid_b_stuck", # Shift solenoid B stuck on
        "P0758": "shift_solenoid_b_elec",  # Shift solenoid B electrical
        "P0760": "shift_solenoid_c",       # Shift solenoid C
        "P0765": "shift_solenoid_d",       # Shift solenoid D
        "P0770": "shift_solenoid_e",       # Shift solenoid E
        "P0780": "shift_malfunction",      # Shift malfunction
        "P0781": "1_2_shift",              # 1-2 shift malfunction
        "P0782": "2_3_shift",              # 2-3 shift malfunction
        "P0783": "3_4_shift",              # 3-4 shift malfunction
        "P0784": "4_5_shift",              # 4-5 shift malfunction
        
        # =====================================================================
        # VVT/VARIABLE VALVE TIMING (P001x, P0010-P0025)
        # =====================================================================
        "P0010": "vvt_solenoid_a_bank1",   # Intake camshaft position actuator bank 1
        "P0011": "vvt_overadvanced_a_b1",  # Intake cam timing over-advanced bank 1
        "P0012": "vvt_retarded_a_b1",      # Intake cam timing retarded bank 1
        "P0013": "vvt_solenoid_b_bank1",   # Exhaust camshaft position actuator bank 1
        "P0014": "vvt_overadvanced_b_b1",  # Exhaust cam timing over-advanced bank 1
        "P0015": "vvt_retarded_b_b1",      # Exhaust cam timing retarded bank 1
        "P0020": "vvt_solenoid_a_bank2",   # Intake camshaft position actuator bank 2
        "P0021": "vvt_overadvanced_a_b2",  # Intake cam timing over-advanced bank 2
        "P0022": "vvt_retarded_a_b2",      # Intake cam timing retarded bank 2
        "P0023": "vvt_solenoid_b_bank2",   # Exhaust camshaft position actuator bank 2
        "P0024": "vvt_overadvanced_b_b2",  # Exhaust cam timing over-advanced bank 2
        "P0025": "vvt_retarded_b_b2",      # Exhaust cam timing retarded bank 2
        
        # =====================================================================
        # ENGINE MECHANICAL/TURBO
        # =====================================================================
        "P0299": "turbo_underboost",       # Turbo/supercharger underboost
        "P0234": "turbo_overboost",        # Turbo/supercharger overboost
        
        # =====================================================================
        # STARTER SYSTEM (P061x)
        # =====================================================================
        "P0615": "starter_circuit",        # Starter relay circuit
        "P0616": "starter_circuit_low",    # Starter relay circuit low
        "P0617": "starter_circuit_high",   # Starter relay circuit high
        
        # =====================================================================
        # ABS/TRACTION (C0xxx - Chassis codes)
        # =====================================================================
        "C0035": "abs_lf_sensor",          # Left front wheel speed sensor
        "C0040": "abs_rf_sensor",          # Right front wheel speed sensor
        "C0045": "abs_lr_sensor",          # Left rear wheel speed sensor
        "C0050": "abs_rr_sensor",          # Right rear wheel speed sensor
        "C0055": "abs_rear_sensor",        # Rear wheel speed sensor (single)
        "C0060": "abs_lf_motor",           # Left front ABS motor circuit
        "C0065": "abs_rf_motor",           # Right front ABS motor circuit
        "C0070": "abs_lr_motor",           # Left rear ABS motor circuit
        "C0075": "abs_rr_motor",           # Right rear ABS motor circuit
        "C0080": "abs_solenoid",           # ABS solenoid circuit
        "C0110": "abs_pump_motor",         # ABS pump motor circuit
        "C0121": "traction_valve",         # Traction control valve circuit
        "C0161": "abs_brake_switch",       # ABS/TCS brake switch circuit
        "C0265": "ebcm_relay",             # EBCM relay circuit
        
        # =====================================================================
        # STEERING (C0xxx)
        # =====================================================================
        "C0455": "steering_sensor",        # Steering wheel position sensor
        "C0460": "steering_sensor_range",  # Steering sensor range/performance
        "C0545": "eps_motor",              # EPS motor circuit
        "C0550": "eps_control",            # EPS control module
        
        # =====================================================================
        # NETWORK/COMMUNICATION (U0xxx)
        # =====================================================================
        "U0100": "lost_comm_ecm",          # Lost communication with ECM/PCM
        "U0101": "lost_comm_tcm",          # Lost communication with TCM
        "U0121": "lost_comm_abs",          # Lost communication with ABS
        "U0140": "lost_comm_bcm",          # Lost communication with BCM
        "U0155": "lost_comm_cluster",      # Lost communication with instrument cluster
        "U0401": "invalid_data_ecm",       # Invalid data received from ECM
        "U0402": "invalid_data_tcm",       # Invalid data received from TCM
    }
    
    # DTC to system mapping for routing
    DTC_TO_SYSTEM = {
        # Cooling
        "P0217": "cooling", "P0128": "cooling", "P0480": "cooling", 
        "P0481": "cooling", "P0117": "cooling", "P0118": "cooling",
        "P0125": "cooling", "P0116": "cooling", "P0115": "cooling",
        "P0119": "cooling",
        # Fuel
        "P0171": "fuel", "P0172": "fuel", "P0174": "fuel", "P0175": "fuel",
        "P0170": "fuel", "P0173": "fuel",
        "P0087": "fuel", "P0088": "fuel", "P0089": "fuel", "P0093": "fuel",
        "P0230": "fuel", "P0231": "fuel", "P0232": "fuel",
        "P0190": "fuel", "P0191": "fuel", "P0192": "fuel", "P0193": "fuel",
        "P0201": "fuel", "P0202": "fuel", "P0203": "fuel", "P0204": "fuel",
        "P0205": "fuel", "P0206": "fuel", "P0207": "fuel", "P0208": "fuel",
        "P0261": "fuel", "P0264": "fuel", "P0267": "fuel", "P0270": "fuel",
        # Ignition
        "P0300": "ignition", "P0301": "ignition", "P0302": "ignition",
        "P0303": "ignition", "P0304": "ignition", "P0305": "ignition", 
        "P0306": "ignition", "P0307": "ignition", "P0308": "ignition",
        "P0351": "ignition", "P0352": "ignition", "P0353": "ignition", 
        "P0354": "ignition", "P0355": "ignition", "P0356": "ignition",
        "P0357": "ignition", "P0358": "ignition",
        "P0325": "ignition", "P0326": "ignition", "P0327": "ignition", "P0328": "ignition",
        "P0330": "ignition",
        "P0335": "ignition", "P0336": "ignition", "P0337": "ignition", "P0338": "ignition",
        "P0340": "ignition", "P0341": "ignition", "P0345": "ignition",
        # Air/MAF (routes to fuel)
        "P0100": "fuel", "P0101": "fuel", "P0102": "fuel", "P0103": "fuel", "P0104": "fuel",
        "P0105": "fuel", "P0106": "fuel", "P0107": "fuel", "P0108": "fuel",
        "P0110": "fuel", "P0111": "fuel", "P0112": "fuel", "P0113": "fuel",
        "P0505": "fuel", "P0506": "fuel", "P0507": "fuel", "P0508": "fuel", "P0509": "fuel",
        # Throttle (routes to fuel)
        "P0120": "fuel", "P0121": "fuel", "P0122": "fuel", "P0123": "fuel",
        "P0220": "fuel", "P0221": "fuel", "P0222": "fuel", "P0223": "fuel",
        "P2135": "fuel", "P2138": "fuel",
        # Charging
        "P0562": "charging", "P0563": "charging", "P0560": "charging", "P0561": "charging",
        # O2 sensors (routes to fuel/emissions)
        "P0130": "fuel", "P0131": "fuel", "P0132": "fuel", "P0133": "fuel",
        "P0134": "fuel", "P0135": "fuel", "P0136": "fuel", "P0137": "fuel",
        "P0138": "fuel", "P0139": "fuel", "P0140": "fuel", "P0141": "fuel",
        "P0150": "fuel", "P0151": "fuel", "P0152": "fuel", "P0153": "fuel",
        "P0154": "fuel", "P0155": "fuel", "P0156": "fuel", "P0157": "fuel", "P0158": "fuel",
        # Catalyst/Emissions
        "P0420": "emissions", "P0421": "emissions", "P0430": "emissions", "P0431": "emissions",
        # EVAP
        "P0440": "emissions", "P0441": "emissions", "P0442": "emissions", "P0443": "emissions",
        "P0444": "emissions", "P0445": "emissions", "P0446": "emissions", "P0447": "emissions",
        "P0448": "emissions", "P0449": "emissions", "P0450": "emissions", "P0451": "emissions",
        "P0452": "emissions", "P0453": "emissions", "P0455": "emissions", "P0456": "emissions",
        "P0457": "emissions",
        # EGR
        "P0400": "emissions", "P0401": "emissions", "P0402": "emissions", "P0403": "emissions",
        "P0404": "emissions", "P0405": "emissions", "P0406": "emissions",
        # Transmission
        "P0700": "transmission", "P0705": "transmission", "P0706": "transmission",
        "P0710": "transmission", "P0711": "transmission",
        "P0715": "transmission", "P0716": "transmission", "P0717": "transmission",
        "P0720": "transmission", "P0721": "transmission", "P0722": "transmission",
        "P0725": "transmission", "P0730": "transmission",
        "P0731": "transmission", "P0732": "transmission", "P0733": "transmission",
        "P0734": "transmission", "P0735": "transmission",
        "P0740": "transmission", "P0741": "transmission", "P0742": "transmission",
        "P0743": "transmission", "P0744": "transmission",
        "P0750": "transmission", "P0751": "transmission", "P0752": "transmission", "P0753": "transmission",
        "P0755": "transmission", "P0756": "transmission", "P0757": "transmission", "P0758": "transmission",
        "P0760": "transmission", "P0765": "transmission", "P0770": "transmission",
        "P0780": "transmission", "P0781": "transmission", "P0782": "transmission",
        "P0783": "transmission", "P0784": "transmission",
        # VVT (routes to engine)
        "P0010": "engine", "P0011": "engine", "P0012": "engine",
        "P0013": "engine", "P0014": "engine", "P0015": "engine",
        "P0020": "engine", "P0021": "engine", "P0022": "engine",
        "P0023": "engine", "P0024": "engine", "P0025": "engine",
        # Turbo
        "P0299": "turbo", "P0234": "turbo",
        # Starter
        "P0615": "starting", "P0616": "starting", "P0617": "starting",
        # ABS
        "C0035": "brakes", "C0040": "brakes", "C0045": "brakes", "C0050": "brakes",
        "C0055": "brakes", "C0060": "brakes", "C0065": "brakes", "C0070": "brakes",
        "C0075": "brakes", "C0080": "brakes", "C0110": "brakes", "C0121": "brakes",
        "C0161": "brakes", "C0265": "brakes",
        # Steering
        "C0455": "steering", "C0460": "steering", "C0545": "steering", "C0550": "steering",
        # Network (generic routing)
        "U0100": "engine", "U0101": "transmission", "U0121": "brakes",
        "U0140": "engine", "U0155": "engine", "U0401": "engine", "U0402": "transmission",
    }
    
    def to_evidence(self) -> Optional[str]:
        """Convert DTC to evidence type for reasoning"""
        return self.DTC_TO_EVIDENCE.get(self.code.upper())
    
    def to_system(self) -> Optional[str]:
        """Get the system this DTC relates to"""
        return self.DTC_TO_SYSTEM.get(self.code.upper())


@dataclass
class DiagnosticResult:
    """Complete diagnostic result"""
    # Top diagnosis
    primary_failure: str
    confidence: float
    
    # Alternatives
    alternatives: List[Tuple[str, float]]  # (failure, confidence)
    
    # Recommended actions
    repair_actions: List[str]
    
    # Discriminating tests to confirm diagnosis
    discriminating_tests: List[str] = field(default_factory=list)
    
    # Repair estimate
    repair_estimate: Optional[str] = None
    
    # Recommended next test (if confidence < threshold)
    recommended_test: Optional[str] = None
    test_reason: Optional[str] = None
    
    # Reasoning trace
    reasoning_explanation: str = ""
    
    # Session info
    phase: DiagnosticPhase = DiagnosticPhase.INITIAL
    evidence_used: List[str] = field(default_factory=list)
    
    # ML confidence breakdown (for transparency)
    ml_system_scores: Dict[str, float] = field(default_factory=dict)  # system -> confidence
    ml_failure_scores: Dict[str, float] = field(default_factory=dict)  # failure -> confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "diagnosis": {
                "failure": self.primary_failure,
                "confidence": round(self.confidence * 100, 1),
                "confidence_pct": f"{self.confidence * 100:.1f}%"
            },
            "alternatives": [
                {"failure": f, "confidence": round(c * 100, 1)}
                for f, c in self.alternatives
            ],
            "repair_actions": self.repair_actions,
            "discriminating_tests": self.discriminating_tests,
            "repair_estimate": self.repair_estimate,
            "next_test": {
                "test": self.recommended_test,
                "reason": self.test_reason
            } if self.recommended_test else None,
            "phase": self.phase.value,
            "evidence_count": len(self.evidence_used),
            "reasoning": self.reasoning_explanation,
            "ml_scores": {
                "systems": self.ml_system_scores,
                "failures": self.ml_failure_scores
            }
        }


class DiagnosticEngine:
    """
    The main diagnostic engine - unified API for the system.
    
    Usage:
        engine = DiagnosticEngine()
        
        # Quick diagnosis from sensors
        result = engine.diagnose(
            sensors=[
                SensorReading("coolant_temp", 115, "°C"),
                SensorReading("oil_pressure", 45, "psi")
            ],
            dtcs=["P0217"],
            symptoms=["overheating", "steam from hood"]
        )
        
        # Interactive diagnosis
        session = engine.start_session()
        session.add_observation("coolant_temp_high")
        session.add_observation("fan_running")
        result = session.get_diagnosis()
    """
    
    # Sensor thresholds for converting readings to evidence
    SENSOR_THRESHOLDS = {
        "coolant_temp": {
            "high": (105, "coolant_temp_high"),      # > 105°C = overheating
            "low": (70, "coolant_temp_low"),         # < 70°C = thermostat stuck open
            "normal": (85, 100)                       # Normal range
        },
        "oil_pressure": {
            "low": (20, "oil_pressure_low"),         # < 20 psi at idle = low
            "high": (80, "oil_pressure_high"),       # > 80 psi = high (relief valve?)
        },
        "oil_temp": {
            "high": (130, "oil_temp_high"),          # > 130°C = overheating
        },
        "trans_temp": {
            "high": (120, "trans_temp_high"),        # > 120°C = overheating
        },
        "intake_temp": {
            "high": (60, "intake_temp_high"),        # > 60°C = hot intake
        },
        "battery_voltage": {
            "low": (12.0, "voltage_low"),            # < 12V = charging issue
            "high": (15.0, "voltage_high"),          # > 15V = overcharging
        },
        "fuel_pressure": {
            "low": (35, "fuel_pressure_low"),        # < 35 psi = low fuel pressure
        },
        # Fuel trim / MAF / O2 support evidence
        "short_term_fuel_trim_b1": {
            "high": (10, "stft_high"),               # >10% = elevated short term trim
        },
        "long_term_fuel_trim_b1": {
            "high": (10, "ltft_high"),               # >10% = elevated long term trim
        },
        "maf": {
            "low": (1.5, "maf_low"),                 # <1.5 g/s at idle = low
            "high": (4.0, "maf_high"),               # >4.0 g/s at idle = high
        },
        "o2_b1s1": {
            "low": (0.2, "o2_lean"),                 # <0.2V = O2 indicates lean
        },
        # High-voltage isolation / insulation resistance (MΩ)
        "insulation_resistance": {
            "low": (1.0, "insulation_resistance_low"),  # <1 MΩ = potential isolation fault
        },
        "isolation_resistance": {
            "low": (1.0, "insulation_resistance_low"),  # synonym mapping
        }
    }
    
    # Symptom to evidence mapping
    SYMPTOM_TO_EVIDENCE = {
        # Temperature symptoms
        "overheating": "coolant_temp_high",
        "running hot": "coolant_temp_high", 
        "temp gauge high": "coolant_temp_high",
        "steam from hood": "coolant_temp_high",
        "running cold": "coolant_temp_low",
        "no heat": "coolant_temp_low",
        "slow to warm up": "coolant_temp_low",
        "heater not working": "coolant_temp_low",
        
        # Fan symptoms
        "fan not running": "fan_not_running",
        "fan always on": "fan_always_on",
        "cooling fan not working": "fan_not_running",
        
        # Coolant symptoms
        "coolant leak": "coolant_level_low",
        "losing coolant": "coolant_level_low",
        "low coolant": "coolant_level_low",
        "coolant puddle": "coolant_level_low",
        "milky oil": "coolant_in_oil",
        "white smoke": "coolant_in_combustion",
        
        # Pressure symptoms
        "hoses hard": "system_pressure_high",
        "overflow bubbling": "system_pressure_high",
        
        # General
        "check engine light": "cel_on",
        "temperature warning": "temp_warning_light",
    }
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize the diagnostic engine.
        
        Args:
            confidence_threshold: Confidence level to consider diagnosis "confident"
        """
        self.confidence_threshold = confidence_threshold
        self.causal_graph = CausalGraph()
        self.diagnostician = Diagnostician()
        
        # Build failure descriptions from knowledge base
        self.failure_descriptions = {}
        for failure in get_all_failure_modes():
            self.failure_descriptions[failure.id] = failure.name
        
        # Initialize hierarchical ML model if available
        # Initialize TwoStageXGB ML model (preferred - 90%+ accuracy)
        self._twostage_ml = None
        if TWOSTAGE_AVAILABLE:
            try:
                model_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "models", "twostage_xgb.pkl"
                )
                if os.path.exists(model_path):
                    self._twostage_ml = TwoStageXGBPredictor(model_path)
                    print(f"Loaded TwoStageXGB model (90%+ accuracy)")
            except Exception as e:
                print(f"Warning: Could not load TwoStageXGB model: {e}")
        
        # Initialize hierarchical ML model as fallback
        self._hierarchical_ml = None
        if HIERARCHICAL_AVAILABLE and self._twostage_ml is None:
            try:
                self._hierarchical_ml = get_hierarchical_inference()
                if self._hierarchical_ml._load_models():
                    print(f"Loaded legacy ML models for systems: {self._hierarchical_ml.available_systems}")
            except Exception as e:
                print(f"Warning: Could not load hierarchical ML models: {e}")
    
    def diagnose(
        self,
        sensors: Optional[List[SensorReading]] = None,
        dtcs: Optional[List[str]] = None,
        symptoms: Optional[List[str]] = None,
        additional_evidence: Optional[List[str]] = None
    ) -> DiagnosticResult:
        """
        Perform diagnosis from available data.
        
        This is the main entry point - give it what you have and it
        returns the most likely causes.
        
        Args:
            sensors: Raw sensor readings
            dtcs: Diagnostic trouble codes (e.g., ["P0217", "P0128"])
            symptoms: Customer complaints / observations
            additional_evidence: Direct evidence strings
            
        Returns:
            DiagnosticResult with diagnosis, confidence, and recommendations
        """
        # Convert all inputs to evidence
        evidence_list = []
        
        # Process sensor readings
        stft_val = None
        ltft_val = None
        if sensors:
            for sensor in sensors:
                evidence = self._sensor_to_evidence(sensor)
                if evidence:
                    evidence_list.append(evidence)
                # capture STFT/LTFT values if present for combined check
                name = sensor.name.lower()
                if "short_term_fuel_trim" in name or name.startswith("stft"):
                    try:
                        stft_val = float(sensor.value)
                    except Exception:
                        pass
                if "long_term_fuel_trim" in name or name.startswith("ltft"):
                    try:
                        ltft_val = float(sensor.value)
                    except Exception:
                        pass

        # Combined fuel trim evidence
        try:
            if stft_val is not None and ltft_val is not None:
                total_trim = abs(stft_val) + abs(ltft_val)
                if total_trim >= 25:
                    evidence_list.append("high_total_fuel_trim")
                elif total_trim >= 18:
                    evidence_list.append("moderate_total_fuel_trim")
        except Exception:
            pass
        
        # Process DTCs
        if dtcs:
            for dtc_code in dtcs:
                dtc = DTCCode(code=dtc_code)
                evidence = dtc.to_evidence()
                if evidence:
                    evidence_list.append(evidence)
        
        # Process symptoms
        if symptoms:
            for symptom in symptoms:
                evidence = self._symptom_to_evidence(symptom)
                if evidence:
                    evidence_list.append(evidence)
        
        # Add direct evidence
        if additional_evidence:
            evidence_list.extend(additional_evidence)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_evidence = []
        for e in evidence_list:
            if e not in seen:
                seen.add(e)
                unique_evidence.append(e)
        
        # ML-based diagnosis if we have sensor readings and TwoStageXGB model
        ml_result = None
        ml_failure_scores = {}
        if sensors and self._twostage_ml:
            try:
                # Default "normal" values for all sensors the model expects
                # These represent a healthy vehicle at idle
                DEFAULT_SENSOR_VALUES = {
                    'rpm': 750, 'speed_kmh': 0, 'throttle_pct': 5, 'engine_torque_nm': 50,
                    'engine_load': 20, 'coolant_temp': 90, 'stft_b1': 0, 'stft_b2': 0,
                    'ltft_b1': 0, 'ltft_b2': 0, 'fuel_pressure': 45, 'tire_pressure': 32,
                    'wheel_slip_events': 0, 'tire_wear_index': 0.3, 'brake_temp': 30,
                    'decel_rate': 0, 'brake_pedal_travel': 0, 'trans_slip_ratio': 0,
                    'trans_temp': 60, 'shift_quality': 1.0,
                }
                
                # Start with defaults
                features = {}
                for sensor_name, default_val in DEFAULT_SENSOR_VALUES.items():
                    features[f"{sensor_name}_mean"] = default_val
                    features[f"{sensor_name}_final"] = default_val
                    features[f"{sensor_name}_min"] = default_val
                    features[f"{sensor_name}_max"] = default_val
                    features[f"{sensor_name}_std"] = 0.0
                    features[f"{sensor_name}_range"] = 0.0
                    features[f"{sensor_name}_delta"] = 0.0
                    features[f"{sensor_name}_rate_max"] = 0.0
                
                # Override with actual sensor readings
                for s in sensors:
                    sensor_name = s.name.lower().replace(" ", "_")
                    value = float(s.value)
                    features[f"{sensor_name}_mean"] = value
                    features[f"{sensor_name}_final"] = value
                    features[f"{sensor_name}_min"] = value
                    features[f"{sensor_name}_max"] = value
                
                ml_predictions = self._twostage_ml.predict(features, top_k=5)
                if ml_predictions:
                    ml_result = ml_predictions[0]  # (failure_mode, probability, system)
                    ml_failure_scores = {p[0]: p[1] for p in ml_predictions}
            except Exception as e:
                print(f"ML prediction failed: {e}")
        
        # Use diagnostician for reasoning - build observations dict
        observations = {e: True for e in unique_evidence}
        symptom_strs = symptoms if symptoms else []
        conclusion = reasoning_quick_diagnose(symptom_strs, observations)
        
        # If ML has very high confidence (85%+), prefer ML but validate against evidence
        # The ML model is still being trained - will improve after 45K sample generation
        if ml_result and ml_result[1] > 0.85 and len(unique_evidence) == 0:
            # Only use pure ML when no other evidence (symptoms/DTCs) is provided
            ml_failure = ml_result[0]
            ml_confidence = ml_result[1]
            
            # Build combined result
            conclusion = DiagnosticConclusion(
                primary_diagnosis=ml_failure,
                confidence=ml_confidence,
                alternatives=[(f, p) for f, p in ml_failure_scores.items() if f != ml_failure][:3],
                recommended_actions=conclusion.recommended_actions,
                explanation=f"ML model ({ml_confidence*100:.0f}% confidence) + Bayesian reasoning"
            )
        
        # Build result
        return self._build_result(conclusion, unique_evidence, ml_failure_scores=ml_failure_scores)
    
    def start_session(self) -> 'DiagnosticSession':
        """
        Start an interactive diagnostic session.
        
        Use this for step-by-step diagnosis where you want to:
        - Add evidence incrementally
        - Get test recommendations
        - Track reasoning over time
        
        Returns:
            DiagnosticSession for interactive diagnosis
        """
        return DiagnosticSession(self)
    
    def _sensor_to_evidence(self, sensor: SensorReading) -> Optional[str]:
        """Convert a sensor reading to evidence"""
        thresholds = self.SENSOR_THRESHOLDS.get(sensor.name)
        if not thresholds:
            return None
        
        # Check high threshold
        if "high" in thresholds:
            threshold, evidence = thresholds["high"]
            if sensor.value > threshold:
                return evidence
        
        # Check low threshold
        if "low" in thresholds:
            threshold, evidence = thresholds["low"]
            if sensor.value < threshold:
                return evidence
        
        return None
    
    def _symptom_to_evidence(self, symptom: str) -> Optional[str]:
        """Convert a symptom description to evidence"""
        # Normalize
        symptom_lower = symptom.lower().strip()
        
        # Direct match
        if symptom_lower in self.SYMPTOM_TO_EVIDENCE:
            return self.SYMPTOM_TO_EVIDENCE[symptom_lower]
        
        # Partial match
        for key, evidence in self.SYMPTOM_TO_EVIDENCE.items():
            if key in symptom_lower or symptom_lower in key:
                return evidence
        
        return None
    
    def _build_result(
        self, 
        conclusion: DiagnosticConclusion,
        evidence: List[str],
        session = None,
        ml_failure_scores: Dict[str, float] = None
    ) -> DiagnosticResult:
        """Build DiagnosticResult from conclusion"""
        
        # Determine phase based on confidence
        if conclusion.confidence >= self.confidence_threshold:
            phase = DiagnosticPhase.CONFIDENT
        elif len(evidence) == 0:
            phase = DiagnosticPhase.INITIAL
        else:
            phase = DiagnosticPhase.INVESTIGATING
        
        # Get recommended test if not confident (only if we have a session)
        recommended_test = None
        test_reason = None
        if conclusion.confidence < self.confidence_threshold and session is not None:
            test_info = self.diagnostician.recommend_test(session)
            if test_info:
                recommended_test = test_info.get("test")
                gain = test_info.get("information_gain", 0)
                test_reason = f"Expected information gain: {gain:.3f} bits"
        
        # Get discriminating tests and repair estimate from knowledge base
        discriminating_tests = []
        repair_estimate = None
        failure_info = get_failure_by_id(conclusion.primary_diagnosis)
        if failure_info:
            discriminating_tests = failure_info.discriminating_tests or []
            repair_estimate = failure_info.get_repair_estimate()
        
        return DiagnosticResult(
            primary_failure=conclusion.primary_diagnosis,
            confidence=conclusion.confidence,
            alternatives=conclusion.alternatives,
            repair_actions=conclusion.recommended_actions,
            discriminating_tests=discriminating_tests,
            repair_estimate=repair_estimate,
            recommended_test=recommended_test,
            test_reason=test_reason,
            reasoning_explanation=conclusion.explanation,
            phase=phase,
            evidence_used=evidence,
            ml_failure_scores=ml_failure_scores or {}
        )
    
    def get_failure_description(self, failure: str) -> str:
        """Get human-readable description of a failure mode"""
        return self.failure_descriptions.get(
            failure, 
            failure.replace("_", " ").title()
        )
    
    def diagnose_with_ml(
        self,
        system_id: str,
        sensor_time_series: Dict[str, List[float]],
        symptoms: Optional[List[str]] = None,
    ) -> DiagnosticResult:
        """
        Diagnose using the trained hierarchical ML model.
        
        This method uses the physics-trained ML models for more accurate
        diagnosis based on sensor time series data.
        
        Args:
            system_id: System to diagnose (cooling, fuel, ignition, etc.)
            sensor_time_series: Dict mapping sensor names to time series values
            symptoms: Optional symptoms for additional context
            
        Returns:
            DiagnosticResult with ML-based diagnosis
        """
        if not self._hierarchical_ml:
            return DiagnosticResult(
                primary_failure="error",
                confidence=0.0,
                alternatives=[],
                repair_actions=["ML models not available - use symptom-based diagnosis"],
                reasoning_explanation="Hierarchical ML models not loaded",
                phase=DiagnosticPhase.INITIAL,
            )
        
        # Get ML prediction
        ml_result = self._hierarchical_ml.predict(system_id, sensor_time_series, top_k=5)
        
        if not ml_result.hypotheses:
            return DiagnosticResult(
                primary_failure="unknown",
                confidence=0.0,
                alternatives=[],
                repair_actions=["Could not determine failure - check sensor data"],
                reasoning_explanation="ML model returned no predictions",
                phase=DiagnosticPhase.INITIAL,
            )
        
        # Get top hypothesis
        top_hyp = ml_result.hypotheses[0]
        primary_failure = top_hyp["failure_id"]
        confidence = top_hyp["probability"]
        
        # Build alternatives
        alternatives = [
            (h["failure_id"], h["probability"])
            for h in ml_result.hypotheses[1:]
        ]
        
        # Get repair actions from knowledge base
        repair_actions = self._get_repair_actions(primary_failure)
        
        # Get discriminating tests and repair estimate from knowledge base
        discriminating_tests = []
        repair_estimate = None
        failure_info = get_failure_by_id(primary_failure)
        if failure_info:
            discriminating_tests = failure_info.discriminating_tests or []
            repair_estimate = failure_info.get_repair_estimate()
        
        # Determine phase
        if confidence >= self.confidence_threshold:
            phase = DiagnosticPhase.CONFIDENT
        else:
            phase = DiagnosticPhase.INVESTIGATING
        
        # Build explanation
        explanation = f"ML model diagnosed {primary_failure.replace('_', ' ')} "
        explanation += f"with {confidence:.1%} confidence based on {system_id} sensor data."
        if ml_result.is_ambiguous:
            explanation += " Diagnosis is ambiguous - consider additional testing."
        
        # Get ML scores for transparency
        ml_system_scores = {system_id: ml_result.system_confidence} if hasattr(ml_result, 'system_confidence') else {}
        ml_failure_scores = {h["failure_id"]: h["probability"] for h in ml_result.hypotheses}
        
        return DiagnosticResult(
            primary_failure=primary_failure,
            confidence=confidence,
            alternatives=alternatives,
            repair_actions=repair_actions,
            discriminating_tests=discriminating_tests,
            repair_estimate=repair_estimate,
            recommended_test=ml_result.recommended_tests[0] if ml_result.recommended_tests else None,
            test_reason="Discriminating test to confirm diagnosis" if ml_result.recommended_tests else None,
            reasoning_explanation=explanation,
            phase=phase,
            evidence_used=[f"sensor_data:{system_id}"],
            ml_system_scores=ml_system_scores,
            ml_failure_scores=ml_failure_scores,
        )
    
    def _get_repair_actions(self, failure_id: str) -> List[str]:
        """Get repair actions for a failure from knowledge base."""
        failure = get_failure_by_id(failure_id)
        if failure and failure.repair_actions:
            return failure.repair_actions
        
        # Default actions
        return [f"Diagnose and repair: {failure_id.replace('_', ' ')}"]
    
    def get_supported_sensors(self) -> List[str]:
        """List sensors the engine can interpret"""
        return list(self.SENSOR_THRESHOLDS.keys())
    
    def get_supported_symptoms(self) -> List[str]:
        """List symptoms the engine recognizes"""
        return list(self.SYMPTOM_TO_EVIDENCE.keys())


class DiagnosticSession:
    """
    Interactive diagnostic session for step-by-step diagnosis.
    
    Allows incremental evidence addition and test recommendations.
    """
    
    def __init__(self, engine: DiagnosticEngine):
        self.engine = engine
        self._diag_session = engine.diagnostician.start_session()
        self.sensors: List[SensorReading] = []
        self.dtcs: List[str] = []
        self.symptoms: List[str] = []
        self.raw_evidence: List[str] = []
    
    def add_sensor(self, sensor: SensorReading) -> Optional[str]:
        """
        Add a sensor reading.
        
        Returns:
            Evidence string if sensor triggered threshold, None otherwise
        """
        self.sensors.append(sensor)
        evidence = self.engine._sensor_to_evidence(sensor)
        if evidence:
            self.engine.diagnostician.record_observation(self._diag_session, evidence, True)
            self.raw_evidence.append(evidence)
        return evidence
    
    def add_dtc(self, dtc_code: str) -> Optional[str]:
        """
        Add a diagnostic trouble code.
        
        Returns:
            Evidence string if DTC was recognized, None otherwise
        """
        self.dtcs.append(dtc_code)
        dtc = DTCCode(code=dtc_code)
        evidence = dtc.to_evidence()
        if evidence:
            self.engine.diagnostician.record_observation(self._diag_session, evidence, True)
            self.raw_evidence.append(evidence)
        return evidence
    
    def add_symptom(self, symptom: str) -> Optional[str]:
        """
        Add a symptom/customer complaint.
        
        Returns:
            Evidence string if symptom was recognized, None otherwise
        """
        self.symptoms.append(symptom)
        evidence = self.engine._symptom_to_evidence(symptom)
        if evidence:
            self.engine.diagnostician.record_observation(self._diag_session, evidence, True)
            self.raw_evidence.append(evidence)
        return evidence
    
    def add_observation(self, evidence: str):
        """Add direct evidence observation"""
        self.engine.diagnostician.record_observation(self._diag_session, evidence, True)
        self.raw_evidence.append(evidence)
    
    def add_test_result(self, test: str, result: str):
        """
        Add result of a diagnostic test.
        
        Args:
            test: Test that was performed (e.g., "check_upper_hose")
            result: Result observation (e.g., "upper_hose_hot_no_flow")
        """
        self.engine.diagnostician.record_observation(self._diag_session, result, True)
        self.raw_evidence.append(result)
    
    def get_beliefs(self) -> Dict[str, float]:
        """Get current probability beliefs for all failures"""
        state = self.engine.diagnostician.get_current_state(self._diag_session)
        return dict(state.probabilities)
    
    def get_top_suspects(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get top N most likely failures"""
        beliefs = self.get_beliefs()
        sorted_beliefs = sorted(beliefs.items(), key=lambda x: -x[1])
        return sorted_beliefs[:n]
    
    def recommend_test(self) -> Optional[Tuple[str, float, str]]:
        """
        Get recommended next test.
        
        Returns:
            Tuple of (test_name, information_gain, description) or None
        """
        result = self.engine.diagnostician.recommend_test(self._diag_session)
        if result:
            test = result.get("test")
            gain = result.get("expected_info_gain", 0)
            # Generate description
            descriptions = {
                "coolant_temp_high": "Check if coolant temperature is above normal",
                "fan_running": "Verify cooling fan is operating",
                "upper_hose_hot_no_flow": "Check upper radiator hose - should be hot with flow",
                "lower_hose_cool": "Check lower radiator hose temperature",
                "coolant_level_low": "Check coolant level in reservoir",
                "oil_pressure_low": "Check oil pressure at idle",
                "temp_rises_at_idle": "Monitor if temp rises when idling",
            }
            desc = descriptions.get(test, f"Check for {test.replace('_', ' ')}")
            return (test, gain, desc)
        return None
    
    def get_diagnosis(self) -> DiagnosticResult:
        """Get current diagnosis based on evidence so far"""
        conclusion = self.engine.diagnostician.force_conclusion(self._diag_session)
        return self.engine._build_result(conclusion, self.raw_evidence, self._diag_session)
    
    def conclude(self) -> DiagnosticResult:
        """Force conclusion and finalize session"""
        conclusion = self.engine.diagnostician.force_conclusion(self._diag_session)
        result = self.engine._build_result(conclusion, self.raw_evidence, self._diag_session)
        result.phase = DiagnosticPhase.CONCLUDED
        return result
    
    def get_reasoning_trace(self) -> str:
        """Get full reasoning explanation"""
        return self.engine.diagnostician.explain_reasoning(self._diag_session)
    
    def get_uncertainty(self) -> float:
        """Get current uncertainty (entropy) in bits"""
        state = self.engine.diagnostician.get_current_state(self._diag_session)
        return state.get_entropy()
