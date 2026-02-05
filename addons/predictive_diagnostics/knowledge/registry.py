"""
Failure mode registry and utility functions.

This module provides:
- FAILURE_REGISTRY: All failure modes organized by system and component
- Utility functions for querying failures by component, system, DTC, or symptom
"""

from typing import Dict, List, Optional

from .base import FailureMode

# Import all failure modes from system-specific modules
from .failures_cooling import *
from .failures_engine import *
from .failures_fuel import *
from .failures_ignition import *
from .failures_charging import *
from .failures_starting import *
from .failures_turbo import *
from .failures_transmission import *
from .failures_brakes import *
from .failures_steering import *
from .failures_suspension import *
from .failures_hvac import *
from .failures_emissions import *
from .failures_electrical import *
from .failures_communication import *
from .failures_drivetrain import *
from .failures_tpms import *
from .failures_lighting import *
from .failures_body import *
from .failures_exhaust import *
from .failures_intake import *
from .failures_safety import *
from .failures_ev import *
from .failures_phev import *
from .failures_tesla import *


# ==============================================================================
# FAILURE MODE REGISTRY
# ==============================================================================

# All failure modes organized by system and component
FAILURE_REGISTRY: Dict[str, Dict[str, List[FailureMode]]] = {
    "cooling": {
        "thermostat": [
            THERMOSTAT_STUCK_CLOSED,
            THERMOSTAT_STUCK_OPEN,
        ],
        "water_pump": [
            WATER_PUMP_FAILURE,
            WATER_PUMP_BELT_SLIPPING,
        ],
        "radiator": [
            RADIATOR_BLOCKED_EXTERNAL,
            RADIATOR_BLOCKED_INTERNAL,
        ],
        "cooling_fan": [
            COOLING_FAN_NOT_OPERATING,
            COOLING_FAN_ALWAYS_ON,
        ],
        "pressure_cap": [
            PRESSURE_CAP_FAULTY,
        ],
        "coolant_temp_sensor": [
            ECT_SENSOR_FAILED_HIGH,
            ECT_SENSOR_FAILED_LOW,
        ],
        "cooling_system": [
            COOLANT_LEAK,
        ],
        "heater_hose": [HEATER_HOSE_LEAK],
        "water_outlet": [WATER_OUTLET_HOUSING_LEAK],
        "fan_clutch": [FAN_CLUTCH_FAILED],
    },
    
    "engine": {
        "cylinder": [LOW_COMPRESSION],
        "head_gasket": [HEAD_GASKET_FAILURE],
        "timing_chain": [TIMING_CHAIN_STRETCHED],
        "oil_pump": [OIL_PUMP_FAILURE],
        "pcv_valve": [PCV_VALVE_STUCK],
        "vvt_solenoid": [VVT_SOLENOID_STUCK],
        "cam_phaser": [CAM_PHASER_WORN],
        "timing_belt": [TIMING_BELT_WORN],
        "piston_rings": [PISTON_RING_WORN],
        "valve_seals": [VALVE_SEAL_LEAKING],
        "engine_mount": [ENGINE_MOUNT_WORN],
        "valve_cover": [OIL_LEAK_VALVE_COVER],
        "oil_pan": [OIL_LEAK_OIL_PAN],
        "rear_main_seal": [OIL_LEAK_REAR_MAIN_SEAL],
        "oil_pressure_sensor": [OIL_PRESSURE_SENSOR_FAILED],
    },
    
    "fuel": {
        "fuel_pump": [FUEL_PUMP_WEAK],
        "fuel_injector": [
            FUEL_INJECTOR_CLOGGED,
            FUEL_INJECTOR_LEAKING,
            FUEL_INJECTOR_CIRCUIT_OPEN,
        ],
        "maf_sensor": [MAF_SENSOR_CONTAMINATED, MASS_AIR_FLOW_SENSOR_FAILED],
        "o2_sensor": [O2_SENSOR_FAILED],
        "intake_manifold": [VACUUM_LEAK],
        "iat_sensor": [IAT_SENSOR_FAILED_HIGH, IAT_SENSOR_FAILED_LOW],
        "map_sensor": [MAP_SENSOR_FAILED],
        "tps_sensor": [TPS_SENSOR_FAILED],
        "app_sensor": [APP_SENSOR_FAILED],
        "fuel_pressure_regulator": [FUEL_PRESSURE_REGULATOR_FAILED],
        "fuel_filter": [FUEL_FILTER_CLOGGED],
        "fuel_tank": [FUEL_TANK_VENT_BLOCKED],
        "hpfp": [HIGH_PRESSURE_FUEL_PUMP_FAILED],
        "fuel_level_sensor": [FUEL_LEVEL_SENSOR_FAILED],
        "baro_sensor": [BAROMETRIC_PRESSURE_SENSOR_FAILED],
    },
    
    "ignition": {
        "spark_plug": [SPARK_PLUG_FOULED, SPARK_PLUG_WORN],
        "ignition_coil": [IGNITION_COIL_FAILED, IGNITION_COIL_WEAK],
        "ckp_sensor": [CRANKSHAFT_POSITION_SENSOR_FAILED],
        "cmp_sensor": [CAMSHAFT_POSITION_SENSOR_FAILED],
        "ignition_module": [IGNITION_MODULE_FAILED],
        "plug_wire": [SECONDARY_IGNITION_LEAK],
        "knock_sensor": [KNOCK_SENSOR_FAILED],
    },
    
    "charging": {
        "alternator": [ALTERNATOR_FAILING],
        "battery": [BATTERY_WEAK],
        "starter": [STARTER_FAILING],
        "battery_terminal": [BATTERY_TERMINAL_CORROSION],
        "serpentine_belt": [ALTERNATOR_BELT_SLIPPING],
    },
    
    # Electric vehicle (EV) systems
    "ev_battery": {
        "hv_battery_pack": [
            HV_BATTERY_CELL_IMBALANCE,
            BATTERY_THERMAL_RUNAWAY_RISK,
        ],
        "hv_contactor": [HV_CONTACTOR_STUCK_OPEN],
        "hv_system": [HV_ISOLATION_FAULT],
    },

    "ev_powertrain": {
        "traction_inverter": [INVERTER_FAILURE],
        "traction_motor": [TRACTION_MOTOR_RESOLVER_FAULT],
    },

    "ev_charging": {
        "onboard_charger": [ONBOARD_CHARGER_FAILURE],
        "charge_port": [CHARGE_PORT_FAULT],
    },

    "ev_thermal": {
        "battery_coolant_pump": [BATTERY_COOLANT_PUMP_FAILURE],
    },

    # Tesla-specific systems
    "tesla_hv_battery": {
        "hv_system": [
            TESLA_HV_ISOLATION_FAULT,
            TESLA_CONTACTOR_FAILURE,
        ],
        "hv_contactor": [TESLA_CONTACTOR_FAILURE],
    },

    "tesla_powertrain": {
        "drive_unit": [TESLA_DRIVE_UNIT_NOISE],
    },

    "tesla_thermal": {
        "ptc_heater": [TESLA_PTC_HEATER_FAILURE],
    },

    "tesla_auxiliary": {
        "12v_battery": [TESLA_12V_BATTERY_FAILURE],
    },

    "tesla_charging": {
        "charge_port": [TESLA_CHARGE_PORT_FAULT],
    },

    # Plug-in hybrid electric vehicle (PHEV) systems
    "phev_hybrid": {
        "hybrid_control_module": [
            PHEV_MODE_TRANSITION_FAULT,
            PHEV_REGEN_BRAKE_BLENDING_FAULT,
        ],
        "dc_dc_converter": [PHEV_DC_DC_CONVERTER_FAULT],
    },

    "phev_battery": {
        "phev_hv_battery": [PHEV_HV_BATTERY_DEGRADATION],
    },

    "phev_thermal": {
        "battery_heater": [PHEV_HV_BATTERY_HEATER_FAILURE],
    },

    "phev_powertrain": {
        "generator_clutch": [PHEV_GENERATOR_CLUTCH_FAULT],
    },

    "starting": {
        "starter_motor": [STARTER_MOTOR_FAILING],
        "starter_solenoid": [STARTER_SOLENOID_FAILED],
        "ignition_switch": [IGNITION_SWITCH_FAILED],
        "glow_plug": [GLOW_PLUG_FAILED],
    },
    
    "turbo": {
        "wastegate": [TURBO_WASTEGATE_STUCK_CLOSED, TURBO_WASTEGATE_STUCK_OPEN],
        "turbo": [TURBO_BEARING_FAILURE],
        "charge_pipe": [BOOST_LEAK],
        "intercooler": [INTERCOOLER_CLOGGED],
    },
    
    "transmission": {
        "transmission": [TRANSMISSION_FLUID_LOW, TRANS_FLUID_CONTAMINATED],
        "torque_converter": [TORQUE_CONVERTER_SHUDDER, TCC_STUCK_OFF, TCC_STUCK_ON],
        "shift_solenoid": [SHIFT_SOLENOID_FAILED],
        "valve_body": [VALVE_BODY_FAILURE],
        "speed_sensor": [TRANS_SPEED_SENSOR_FAILED],
        "vss_sensor": [VSS_SENSOR_FAILED],
        "trans_mount": [TRANS_MOUNT_WORN],
        "trans_seal": [TRANS_INPUT_SHAFT_SEAL_LEAK],
        "clutch": [CLUTCH_WORN],
        "clutch_hydraulic": [CLUTCH_HYDRAULIC_FAILURE],
    },
    
    "brakes": {
        "brake_pads": [BRAKE_PADS_WORN],
        "brake_rotor": [BRAKE_ROTOR_WARPED],
        "abs_sensor": [ABS_SENSOR_FAILED, WHEEL_SPEED_SENSOR_FAILED],
        "brake_caliper": [BRAKE_CALIPER_STICKING],
        "master_cylinder": [MASTER_CYLINDER_FAILING],
        "abs_module": [ABS_MODULE_FAILED],
        "abs_pump": [ABS_PUMP_MOTOR_FAILED],
        "brake_fluid": [BRAKE_FLUID_CONTAMINATED],
        "brake_hose": [BRAKE_HOSE_DETERIORATED],
        "parking_brake": [PARKING_BRAKE_STUCK],
    },
    
    "steering": {
        "ps_pump": [PS_PUMP_FAILING],
        "steering_rack": [RACK_WEAR],
        "steering_angle_sensor": [STEERING_ANGLE_SENSOR_FAILED],
        "eps_motor": [EPS_MOTOR_FAILING],
        "tie_rod": [TIE_ROD_WORN],
    },
    
    "suspension": {
        "shock_absorber": [SHOCK_WORN],
        "coil_spring": [SPRING_BROKEN],
        "control_arm": [CONTROL_ARM_BUSHING_WORN],
        "wheel_bearing": [WHEEL_BEARING_FAILING],
        "strut_mount": [STRUT_MOUNT_WORN],
        "sway_bar_link": [SWAY_BAR_LINK_WORN],
        "ball_joint": [BALL_JOINT_WORN],
        "strut": [STRUT_LEAKING],
    },
    
    "hvac": {
        "ac_compressor": [AC_COMPRESSOR_FAILING],
        "ac_system": [REFRIGERANT_LEAK],
        "blend_door": [BLEND_DOOR_STUCK],
        "blower_motor": [BLOWER_MOTOR_FAILING],
        "heater_core": [HEATER_CORE_CLOGGED],
        "ac_compressor_clutch": [AC_COMPRESSOR_CLUTCH_FAILED],
        "expansion_valve": [AC_EXPANSION_VALVE_STUCK],
        "evaporator": [EVAPORATOR_CORE_LEAK],
        "condenser": [CONDENSER_CLOGGED],
        "blower_resistor": [BLOWER_MOTOR_RESISTOR_FAILED],
        "cabin_filter": [CABIN_AIR_FILTER_CLOGGED],
        "ac_pressure_sensor": [AC_PRESSURE_SENSOR_FAILED],
        "ambient_temp_sensor": [AMBIENT_AIR_TEMP_SENSOR_FAILED],
    },
    
    "emissions": {
        "catalytic_converter": [CATALYTIC_CONVERTER_DEGRADED],
        "o2_sensor_upstream": [O2_SENSOR_UPSTREAM_FAILED],
        "o2_sensor_downstream": [O2_SENSOR_DOWNSTREAM_FAILED],
        "egr_valve": [EGR_VALVE_STUCK_CLOSED, EGR_VALVE_STUCK_OPEN],
        "evap_system": [EVAP_LEAK_LARGE],
        "purge_valve": [
            EVAP_PURGE_VALVE_STUCK,
            EVAP_PURGE_CIRCUIT_OPEN,
            EVAP_PURGE_CIRCUIT_SHORT,
            EVAP_PURGE_CONNECTOR_FAULT,
        ],
        "o2_heater": [O2_HEATER_CIRCUIT_FAILED],
        "ftp_sensor": [FUEL_TANK_PRESSURE_SENSOR_FAILED],
        "dpf": [DPF_CLOGGED],
        "def_system": [DEF_SYSTEM_FAULT],
    },
    
    "electrical": {
        "ground_circuit": [GROUND_CIRCUIT_POOR],
        "power_circuit": [POWER_FEED_CIRCUIT_ISSUE],
        "relay": [RELAY_FAILED],
        "fuse": [FUSE_BLOWN],
        "wiring": [WIRING_HARNESS_CHAFED],
        "connector": [CONNECTOR_CORROSION],
        "electrical_system": [PARASITIC_DRAIN],
    },
    
    "communication": {
        "can_bus": [CAN_BUS_FAILURE],
        "control_module": [MODULE_INTERNAL_FAILURE],
        "dlc": [DLC_CONNECTOR_DAMAGED],
    },
    
    "drivetrain": {
        "cv_joint": [CV_JOINT_WORN],
        "cv_boot": [CV_BOOT_TORN],
        "differential": [DIFFERENTIAL_NOISE],
        "transfer_case": [TRANSFER_CASE_FAILURE],
        "driveshaft": [DRIVESHAFT_U_JOINT_WORN],
        "axle_bearing": [AXLE_BEARING_FAILURE],
    },
    
    "tpms": {
        "tpms_sensor": [TPMS_SENSOR_BATTERY_DEAD, TPMS_SENSOR_DAMAGED],
        "tpms_module": [TPMS_MODULE_FAILURE],
    },
    
    "lighting": {
        "headlight": [HEADLIGHT_BULB_BURNED, HEADLIGHT_CIRCUIT_ISSUE],
        "taillight": [TAILLIGHT_CIRCUIT_ISSUE],
        "turn_signal": [TURN_SIGNAL_FAST_FLASH],
    },
    
    "body": {
        "door_lock": [DOOR_LOCK_ACTUATOR_FAILED],
        "window_regulator": [WINDOW_REGULATOR_FAILED],
        "window_motor": [WINDOW_MOTOR_FAILED],
    },
    
    "exhaust": {
        "exhaust_system": [EXHAUST_LEAK],
        "exhaust_manifold": [EXHAUST_MANIFOLD_CRACK],
        "flex_pipe": [FLEX_PIPE_FAILED],
        "muffler": [MUFFLER_FAILED],
    },
    
    "intake": {
        "air_filter": [AIR_FILTER_CLOGGED],
        "intake_boot": [INTAKE_BOOT_CRACKED],
        "throttle_body": [THROTTLE_BODY_CARBON],
        "intake_manifold": [INTAKE_MANIFOLD_GASKET_LEAK],
    },
    
    "safety": {
        "airbag_sensor": [AIRBAG_SENSOR_FAILED],
        "clock_spring": [AIRBAG_CLOCK_SPRING_FAILED],
        "seatbelt_switch": [SEATBELT_BUCKLE_SWITCH_FAILED],
        "backup_camera": [BACKUP_CAMERA_FAILED],
        "parking_sensor": [PARKING_SENSOR_FAILED],
    },
}


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_failure_modes_for_component(system_id: str, component_id: str) -> List[FailureMode]:
    """Get all failure modes for a specific component."""
    system_failures = FAILURE_REGISTRY.get(system_id, {})
    return system_failures.get(component_id, [])


def get_failure_modes_for_system(system_id: str) -> List[FailureMode]:
    """Get all failure modes for a system."""
    system_failures = FAILURE_REGISTRY.get(system_id, {})
    all_failures = []
    for component_failures in system_failures.values():
        all_failures.extend(component_failures)
    return all_failures


def get_all_failure_modes() -> List[FailureMode]:
    """Get all registered failure modes."""
    all_failures = []
    for system_failures in FAILURE_REGISTRY.values():
        for component_failures in system_failures.values():
            all_failures.extend(component_failures)
    return all_failures


def get_failure_by_id(failure_id: str) -> Optional[FailureMode]:
    """Get a failure mode by its ID."""
    for failure in get_all_failure_modes():
        if failure.id == failure_id:
            return failure
    return None


def get_failures_for_dtc(dtc: str) -> List[FailureMode]:
    """Get all failure modes that can cause a specific DTC."""
    matching = []
    for failure in get_all_failure_modes():
        if dtc in failure.expected_dtcs:
            matching.append(failure)
    return matching


def get_failures_for_symptom(symptom_keyword: str) -> List[FailureMode]:
    """Get failure modes matching a symptom keyword."""
    keyword = symptom_keyword.lower()
    matching = []
    for failure in get_all_failure_modes():
        for symptom in failure.symptoms:
            if keyword in symptom.description.lower():
                matching.append(failure)
                break
    return matching
