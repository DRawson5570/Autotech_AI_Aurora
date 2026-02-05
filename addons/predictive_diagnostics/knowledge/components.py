"""
Component models for automotive systems.

Each component model encodes:
- Component type (sensor, actuator, valve, etc.)
- Function (what it does in the system)
- Inputs and outputs (physical connections)
- Failure modes (how it can fail)
- Failure effects (what happens when it fails)

Knowledge source: Advanced Automotive Fault Diagnosis (Denton)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


class ComponentType(Enum):
    """Categories of automotive components."""
    SENSOR = "sensor"          # Measures physical quantity
    ACTUATOR = "actuator"      # Produces physical action
    VALVE = "valve"            # Controls flow
    PUMP = "pump"              # Moves fluid
    HEAT_EXCHANGER = "heat_exchanger"  # Transfers heat
    ELECTRICAL = "electrical"  # Electrical component
    MECHANICAL = "mechanical"  # Mechanical component


class SensorType(Enum):
    """Types of sensors."""
    THERMISTOR = "thermistor"      # Temperature via resistance (NTC/PTC)
    VARIABLE_RESISTOR = "variable_resistor"  # Position via resistance
    HALL_EFFECT = "hall_effect"    # Magnetic field
    INDUCTIVE = "inductive"        # Speed/position
    PIEZOELECTRIC = "piezoelectric"  # Pressure/knock
    OXYGEN = "oxygen"              # O2 concentration
    MASS_AIR_FLOW = "maf"          # Air mass flow


@dataclass
class ComponentModel:
    """
    Base class for component models.
    
    A component model encodes what a component does and how it can fail.
    """
    
    id: str
    name: str
    component_type: ComponentType
    system_id: str  # Which system this belongs to
    
    # Function description
    function: str = ""
    
    # Physical connections
    inputs: List[str] = field(default_factory=list)   # What it receives
    outputs: List[str] = field(default_factory=list)  # What it produces
    
    # Failure modes (populated from failures.py)
    failure_modes: List['FailureMode'] = field(default_factory=list)
    
    # Optional: sensor-specific info
    sensor_type: Optional[SensorType] = None
    
    # Operating characteristics
    specs: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# COOLING SYSTEM COMPONENTS
# ==============================================================================

class Thermostat(ComponentModel):
    """
    Engine thermostat - controls coolant flow to radiator.
    
    From textbook (Chapter 6.20):
    - Wax capsule type
    - Prevents water circulation until set temperature reached
    - Opens at set temperature (typically 82-95°C / 180-203°F)
    - Can fail: stuck OPEN (overcooling) or stuck CLOSED (overheating)
    """
    
    def __init__(self):
        super().__init__(
            id="thermostat",
            name="Engine Thermostat",
            component_type=ComponentType.VALVE,
            system_id="cooling",
            function="Controls coolant flow to radiator based on temperature",
            inputs=["coolant_temp"],
            outputs=["coolant_flow_to_radiator"],
            specs={
                "opening_temp_c": 82.0,     # °C when starts to open
                "fully_open_temp_c": 95.0,  # °C when fully open
                "type": "wax_capsule",
            },
        )


class WaterPump(ComponentModel):
    """
    Water pump - circulates coolant through system.
    
    From textbook:
    - V-belt or multi-V-belt driven
    - Impeller type
    - Provides forced circulation
    - Assists thermo-siphon action
    """
    
    def __init__(self):
        super().__init__(
            id="water_pump",
            name="Water Pump",
            component_type=ComponentType.PUMP,
            system_id="cooling",
            function="Circulates coolant through engine and radiator",
            inputs=["engine_rpm", "belt_tension"],
            outputs=["coolant_flow_rate"],
            specs={
                "drive_type": "belt_driven",
                "pump_type": "centrifugal_impeller",
            },
        )


class Radiator(ComponentModel):
    """
    Radiator - heat exchanger that dissipates heat from coolant.
    
    From textbook:
    - Cross-flow or down-flow design
    - Can become blocked (external: debris, internal: deposits)
    """
    
    def __init__(self):
        super().__init__(
            id="radiator",
            name="Radiator",
            component_type=ComponentType.HEAT_EXCHANGER,
            system_id="cooling",
            function="Transfers heat from coolant to ambient air",
            inputs=["coolant_flow_rate", "coolant_temp", "ambient_temp", "air_flow"],
            outputs=["radiator_outlet_temp", "heat_rejected"],
            specs={
                "type": "cross_flow",
            },
        )


class CoolingFan(ComponentModel):
    """
    Electric cooling fan - provides airflow through radiator.
    
    From textbook:
    - Electric motor driven
    - Thermal switch or ECU controlled
    - Operates when vehicle stationary or coolant temp high
    """
    
    def __init__(self):
        super().__init__(
            id="cooling_fan",
            name="Electric Cooling Fan",
            component_type=ComponentType.ACTUATOR,
            system_id="cooling",
            function="Provides airflow through radiator when vehicle speed insufficient",
            inputs=["fan_control_signal"],
            outputs=["radiator_air_flow"],
            specs={
                "control": "thermal_switch_or_ecu",
                "activation_temp_c": 95.0,  # Typical
            },
        )


class PressureCap(ComponentModel):
    """
    Radiator pressure cap - maintains system pressure.
    
    From textbook:
    - Contains pressure valve (opens at set pressure)
    - Contains vacuum valve (prevents collapse on cooling)
    - Raises coolant boiling point (~3°C per 10 kPa)
    - Typical pressure: ~100 kPa (1 bar) above atmospheric
    """
    
    def __init__(self):
        super().__init__(
            id="pressure_cap",
            name="Radiator Pressure Cap",
            component_type=ComponentType.VALVE,
            system_id="cooling",
            function="Maintains system pressure to raise coolant boiling point",
            inputs=["system_pressure"],
            outputs=["pressure_relief", "vacuum_relief"],
            specs={
                "rated_pressure_kpa": 100.0,  # ~1 bar
                "vacuum_valve": True,
            },
        )


class CoolantTempSensor(ComponentModel):
    """
    Coolant temperature sensor (CTS/ECT) - measures coolant temperature.
    
    From textbook (Chapter 4.2.5.1):
    - NTC (Negative Temperature Coefficient) thermistor
    - Resistance decreases as temperature increases
    - 5V reference voltage
    - Cold: 3-4V output, several kΩ resistance
    - Hot: lower voltage, few hundred ohms resistance
    - Typical range: ~3kΩ at 0°C to ~300Ω at 100°C
    """
    
    def __init__(self):
        super().__init__(
            id="coolant_temp_sensor",
            name="Coolant Temperature Sensor",
            component_type=ComponentType.SENSOR,
            system_id="cooling",
            sensor_type=SensorType.THERMISTOR,
            function="Measures coolant temperature for ECU",
            inputs=["coolant_temp"],
            outputs=["ect_voltage", "ect_signal"],
            specs={
                "type": "NTC_thermistor",
                "reference_voltage": 5.0,  # V
                "resistance_cold_ohms": 3000.0,  # ~3kΩ at 0°C
                "resistance_hot_ohms": 300.0,    # ~300Ω at 100°C
                "voltage_cold": 3.5,  # V at cold
                "voltage_hot": 0.5,   # V at hot
            },
        )


class FanThermalSwitch(ComponentModel):
    """
    Cooling fan thermal switch - triggers fan at temperature threshold.
    
    Simple thermal switch that closes at set temperature.
    Being replaced by ECU control on modern vehicles.
    """
    
    def __init__(self):
        super().__init__(
            id="fan_thermal_switch",
            name="Cooling Fan Thermal Switch",
            component_type=ComponentType.SENSOR,
            system_id="cooling",
            function="Activates cooling fan when coolant reaches threshold temperature",
            inputs=["coolant_temp"],
            outputs=["fan_control_signal"],
            specs={
                "activation_temp_c": 95.0,
                "deactivation_temp_c": 90.0,  # Hysteresis
            },
        )


# ==============================================================================
# FUEL SYSTEM COMPONENTS
# ==============================================================================

class FuelPump(ComponentModel):
    """Fuel pump - delivers fuel from tank to engine."""
    
    def __init__(self):
        super().__init__(
            id="fuel_pump",
            name="Fuel Pump",
            component_type=ComponentType.PUMP,
            system_id="fuel",
            function="Delivers pressurized fuel from tank to fuel rail",
            inputs=["fuel_pump_voltage"],
            outputs=["fuel_pressure", "fuel_flow_rate"],
            specs={
                "type": "electric_in_tank",
                "rated_pressure_kpa": 350.0,
                "flow_rate_lph": 120.0,
            },
        )


class FuelPressureRegulator(ComponentModel):
    """Fuel pressure regulator - maintains constant rail pressure."""
    
    def __init__(self):
        super().__init__(
            id="fuel_pressure_regulator",
            name="Fuel Pressure Regulator",
            component_type=ComponentType.VALVE,
            system_id="fuel",
            function="Maintains constant fuel rail pressure by returning excess to tank",
            inputs=["fuel_pressure", "manifold_vacuum"],
            outputs=["regulated_pressure", "return_flow"],
            specs={
                "base_pressure_kpa": 310.0,
                "vacuum_compensation": True,
            },
        )


class FuelInjector(ComponentModel):
    """Fuel injector - delivers metered fuel to cylinder."""
    
    def __init__(self, cylinder: int = 1):
        super().__init__(
            id=f"fuel_injector_{cylinder}",
            name=f"Fuel Injector #{cylinder}",
            component_type=ComponentType.ACTUATOR,
            system_id="fuel",
            function=f"Delivers metered fuel to cylinder {cylinder}",
            inputs=["fuel_pressure", "injector_pulse_width"],
            outputs=["fuel_delivered"],
            specs={
                "cylinder": cylinder,
                "type": "port_injection",
            },
        )


class OxygenSensor(ComponentModel):
    """Oxygen sensor - measures exhaust O2 for fuel control."""
    
    def __init__(self, bank: int = 1, position: int = 1):
        super().__init__(
            id=f"o2_sensor_b{bank}s{position}",
            name=f"O2 Sensor Bank {bank} Sensor {position}",
            component_type=ComponentType.SENSOR,
            system_id="fuel",
            sensor_type=SensorType.OXYGEN,
            function="Measures exhaust oxygen concentration for fuel trim control",
            inputs=["exhaust_o2_concentration"],
            outputs=["o2_voltage"],
            specs={
                "bank": bank,
                "position": position,  # 1=upstream, 2=downstream
                "type": "narrowband",
                "rich_voltage": 0.9,  # V
                "lean_voltage": 0.1,  # V
            },
        )


# ==============================================================================
# IGNITION SYSTEM COMPONENTS
# ==============================================================================

class IgnitionCoil(ComponentModel):
    """Ignition coil - generates high voltage for spark."""
    
    def __init__(self, cylinder: int = 1):
        super().__init__(
            id=f"ignition_coil_{cylinder}",
            name=f"Ignition Coil #{cylinder}",
            component_type=ComponentType.ELECTRICAL,
            system_id="ignition",
            function=f"Generates high voltage spark for cylinder {cylinder}",
            inputs=["primary_voltage", "dwell_command"],
            outputs=["secondary_voltage"],
            specs={
                "cylinder": cylinder,
                "type": "coil_on_plug",
                "secondary_voltage_kv": 40.0,
            },
        )


class SparkPlug(ComponentModel):
    """Spark plug - creates spark in cylinder."""
    
    def __init__(self, cylinder: int = 1):
        super().__init__(
            id=f"spark_plug_{cylinder}",
            name=f"Spark Plug #{cylinder}",
            component_type=ComponentType.ELECTRICAL,
            system_id="ignition",
            function=f"Creates spark for combustion in cylinder {cylinder}",
            inputs=["secondary_voltage"],
            outputs=["spark_energy"],
            specs={
                "cylinder": cylinder,
                "gap_mm": 1.0,
            },
        )


class CrankshaftPositionSensor(ComponentModel):
    """Crankshaft position sensor - provides engine speed and position."""
    
    def __init__(self):
        super().__init__(
            id="crank_position_sensor",
            name="Crankshaft Position Sensor",
            component_type=ComponentType.SENSOR,
            system_id="ignition",
            sensor_type=SensorType.INDUCTIVE,
            function="Provides crankshaft position and engine RPM to ECU",
            inputs=["crankshaft_position"],
            outputs=["crank_signal"],
            specs={
                "type": "inductive",
                "teeth": 58,  # 60-2 pattern common
            },
        )


class CamshaftPositionSensor(ComponentModel):
    """Camshaft position sensor - provides cam position for injection timing."""
    
    def __init__(self):
        super().__init__(
            id="cam_position_sensor",
            name="Camshaft Position Sensor",
            component_type=ComponentType.SENSOR,
            system_id="ignition",
            sensor_type=SensorType.HALL_EFFECT,
            function="Provides camshaft position for sequential injection timing",
            inputs=["camshaft_position"],
            outputs=["cam_signal"],
            specs={
                "type": "hall_effect",
            },
        )


# ==============================================================================
# CHARGING SYSTEM COMPONENTS
# ==============================================================================

class Alternator(ComponentModel):
    """Alternator - generates electrical power from engine rotation."""
    
    def __init__(self):
        super().__init__(
            id="alternator",
            name="Alternator",
            component_type=ComponentType.ELECTRICAL,
            system_id="charging",
            function="Generates electrical power to charge battery and power systems",
            inputs=["engine_rpm", "field_current"],
            outputs=["alternator_output_voltage", "alternator_output_current"],
            specs={
                "rated_output_a": 120.0,
                "regulated_voltage": 14.2,
            },
        )


class Battery(ComponentModel):
    """Battery - stores electrical energy."""
    
    def __init__(self):
        super().__init__(
            id="battery",
            name="Battery",
            component_type=ComponentType.ELECTRICAL,
            system_id="charging",
            function="Stores electrical energy for starting and accessory power",
            inputs=["charging_current"],
            outputs=["battery_voltage", "discharge_current"],
            specs={
                "capacity_ah": 60.0,
                "cca": 600,
                "nominal_voltage": 12.6,
            },
        )


# ==============================================================================
# TRANSMISSION SYSTEM COMPONENTS
# ==============================================================================

class TransmissionPump(ComponentModel):
    """Transmission pump - provides hydraulic pressure."""
    
    def __init__(self):
        super().__init__(
            id="trans_pump",
            name="Transmission Pump",
            component_type=ComponentType.PUMP,
            system_id="transmission",
            function="Provides hydraulic pressure for clutch operation",
            inputs=["engine_rpm"],
            outputs=["line_pressure"],
            specs={"max_pressure_psi": 200.0},
        )


class TorqueConverter(ComponentModel):
    """Torque converter - fluid coupling with torque multiplication."""
    
    def __init__(self):
        super().__init__(
            id="torque_converter",
            name="Torque Converter",
            component_type=ComponentType.MECHANICAL,
            system_id="transmission",
            function="Fluid coupling between engine and transmission",
            inputs=["engine_rpm", "trans_input_rpm"],
            outputs=["slip_percent", "torque_multiplication"],
            specs={"stall_ratio": 2.2},
        )


class ValveBody(ComponentModel):
    """Valve body - hydraulic control unit."""
    
    def __init__(self):
        super().__init__(
            id="valve_body",
            name="Valve Body",
            component_type=ComponentType.VALVE,
            system_id="transmission",
            function="Controls hydraulic pressure to clutches",
            inputs=["line_pressure", "solenoid_commands"],
            outputs=["clutch_pressures"],
            specs={},
        )


# ==============================================================================
# BRAKING SYSTEM COMPONENTS
# ==============================================================================

class MasterCylinder(ComponentModel):
    """Master cylinder - converts pedal force to hydraulic pressure."""
    
    def __init__(self):
        super().__init__(
            id="master_cylinder",
            name="Master Cylinder",
            component_type=ComponentType.PUMP,
            system_id="brakes",
            function="Converts pedal force to hydraulic pressure",
            inputs=["pedal_force"],
            outputs=["brake_pressure"],
            specs={"bore_diameter_mm": 25.4},
        )


class BrakeCaliper(ComponentModel):
    """Brake caliper - clamps pads onto rotor."""
    
    def __init__(self):
        super().__init__(
            id="brake_caliper",
            name="Brake Caliper",
            component_type=ComponentType.ACTUATOR,
            system_id="brakes",
            function="Applies brake pads to rotor",
            inputs=["brake_pressure"],
            outputs=["clamping_force"],
            specs={},
        )


class ABSModule(ComponentModel):
    """ABS module - prevents wheel lockup."""
    
    def __init__(self):
        super().__init__(
            id="abs_module",
            name="ABS Module",
            component_type=ComponentType.ELECTRICAL,
            system_id="brakes",
            function="Modulates brake pressure to prevent lockup",
            inputs=["wheel_speeds", "brake_pressure"],
            outputs=["modulated_pressure"],
            specs={},
        )


# ==============================================================================
# ENGINE MECHANICAL COMPONENTS
# ==============================================================================

class OilPump(ComponentModel):
    """Oil pump - circulates engine oil."""
    
    def __init__(self):
        super().__init__(
            id="oil_pump",
            name="Oil Pump",
            component_type=ComponentType.PUMP,
            system_id="engine",
            function="Circulates oil through engine",
            inputs=["engine_rpm"],
            outputs=["oil_pressure", "oil_flow"],
            specs={"max_pressure_psi": 80.0},
        )


class PistonRings(ComponentModel):
    """Piston rings - seal combustion chamber."""
    
    def __init__(self):
        super().__init__(
            id="piston_rings",
            name="Piston Rings",
            component_type=ComponentType.MECHANICAL,
            system_id="engine",
            function="Seal combustion gases and scrape oil",
            inputs=[],
            outputs=["compression", "oil_consumption"],
            specs={},
        )


class HeadGasket(ComponentModel):
    """Head gasket - seals cylinder head to block."""
    
    def __init__(self):
        super().__init__(
            id="head_gasket",
            name="Head Gasket",
            component_type=ComponentType.MECHANICAL,
            system_id="engine",
            function="Seals combustion chamber and coolant passages",
            inputs=[],
            outputs=["compression", "coolant_integrity"],
            specs={},
        )


# ==============================================================================
# STEERING SYSTEM COMPONENTS
# ==============================================================================

class PowerSteeringPump(ComponentModel):
    """Power steering pump - provides hydraulic assist."""
    
    def __init__(self):
        super().__init__(
            id="ps_pump",
            name="Power Steering Pump",
            component_type=ComponentType.PUMP,
            system_id="steering",
            function="Provides hydraulic pressure for steering assist",
            inputs=["engine_rpm"],
            outputs=["ps_pressure"],
            specs={"max_pressure_psi": 1500.0},
        )


class SteeringRack(ComponentModel):
    """Steering rack - converts rotation to linear motion."""
    
    def __init__(self):
        super().__init__(
            id="steering_rack",
            name="Steering Rack",
            component_type=ComponentType.MECHANICAL,
            system_id="steering",
            function="Converts steering wheel rotation to wheel movement",
            inputs=["steering_input", "ps_pressure"],
            outputs=["steering_output"],
            specs={},
        )


class TieRodEnd(ComponentModel):
    """Tie rod end - connects rack to steering knuckle."""
    
    def __init__(self):
        super().__init__(
            id="tie_rod_end",
            name="Tie Rod End",
            component_type=ComponentType.MECHANICAL,
            system_id="steering",
            function="Connects steering rack to wheel",
            inputs=["rack_movement"],
            outputs=["wheel_angle"],
            specs={},
        )


# ==============================================================================
# SUSPENSION SYSTEM COMPONENTS
# ==============================================================================

class Strut(ComponentModel):
    """Strut - combines spring and damper."""
    
    def __init__(self):
        super().__init__(
            id="strut",
            name="Strut",
            component_type=ComponentType.MECHANICAL,
            system_id="suspension",
            function="Supports vehicle weight and controls oscillation",
            inputs=["road_input"],
            outputs=["wheel_position", "body_motion"],
            specs={},
        )


class ControlArm(ComponentModel):
    """Control arm - locates wheel and allows vertical movement."""
    
    def __init__(self):
        super().__init__(
            id="control_arm",
            name="Control Arm",
            component_type=ComponentType.MECHANICAL,
            system_id="suspension",
            function="Locates wheel while allowing suspension travel",
            inputs=[],
            outputs=["wheel_location"],
            specs={},
        )


class WheelBearing(ComponentModel):
    """Wheel bearing - allows wheel rotation with low friction."""
    
    def __init__(self):
        super().__init__(
            id="wheel_bearing",
            name="Wheel Bearing",
            component_type=ComponentType.MECHANICAL,
            system_id="suspension",
            function="Allows wheel rotation with low friction",
            inputs=["vehicle_load", "wheel_rpm"],
            outputs=["friction", "heat"],
            specs={},
        )


# ==============================================================================
# HVAC SYSTEM COMPONENTS
# ==============================================================================

class ACCompressor(ComponentModel):
    """A/C compressor - compresses refrigerant."""
    
    def __init__(self):
        super().__init__(
            id="ac_compressor",
            name="A/C Compressor",
            component_type=ComponentType.PUMP,
            system_id="hvac",
            function="Compresses refrigerant in A/C system",
            inputs=["engine_rpm", "clutch_engaged"],
            outputs=["refrigerant_pressure_high"],
            specs={},
        )


class BlowerMotor(ComponentModel):
    """Blower motor - circulates air through HVAC system."""
    
    def __init__(self):
        super().__init__(
            id="blower_motor",
            name="Blower Motor",
            component_type=ComponentType.ACTUATOR,
            system_id="hvac",
            function="Moves air through HVAC ducts",
            inputs=["blower_command"],
            outputs=["airflow"],
            specs={},
        )


class BlendDoor(ComponentModel):
    """Blend door - mixes hot and cold air."""
    
    def __init__(self):
        super().__init__(
            id="blend_door",
            name="Blend Door",
            component_type=ComponentType.ACTUATOR,
            system_id="hvac",
            function="Controls mix of hot and cold air",
            inputs=["temp_command"],
            outputs=["mix_ratio"],
            specs={},
        )


class HeaterCore(ComponentModel):
    """Heater core - provides cabin heat."""
    
    def __init__(self):
        super().__init__(
            id="heater_core",
            name="Heater Core",
            component_type=ComponentType.HEAT_EXCHANGER,
            system_id="hvac",
            function="Transfers engine heat to cabin air",
            inputs=["coolant_flow", "coolant_temp"],
            outputs=["heated_air_temp"],
            specs={},
        )


# ==============================================================================
# EMISSIONS SYSTEM COMPONENTS
# ==============================================================================

class CatalyticConverter(ComponentModel):
    """Catalytic converter - reduces exhaust emissions."""
    
    def __init__(self):
        super().__init__(
            id="catalytic_converter",
            name="Catalytic Converter",
            component_type=ComponentType.MECHANICAL,
            system_id="emissions",
            function="Oxidizes HC/CO and reduces NOx",
            inputs=["exhaust_flow", "exhaust_temp"],
            outputs=["catalyst_efficiency", "downstream_o2"],
            specs={},
        )


class EGRValve(ComponentModel):
    """EGR valve - recirculates exhaust gas."""
    
    def __init__(self):
        super().__init__(
            id="egr_valve",
            name="EGR Valve",
            component_type=ComponentType.VALVE,
            system_id="emissions",
            function="Controls exhaust gas recirculation",
            inputs=["egr_command"],
            outputs=["egr_flow"],
            specs={},
        )


class EVAPCanister(ComponentModel):
    """EVAP canister - captures fuel vapors."""
    
    def __init__(self):
        super().__init__(
            id="evap_canister",
            name="EVAP Canister",
            component_type=ComponentType.MECHANICAL,
            system_id="emissions",
            function="Stores fuel vapors for purging",
            inputs=["fuel_vapors"],
            outputs=["stored_vapors", "purge_flow"],
            specs={},
        )


# ==============================================================================
# COMPONENT REGISTRY
# ==============================================================================

# All available component classes by system
COMPONENT_CLASSES = {
    "cooling": [
        Thermostat,
        WaterPump,
        Radiator,
        CoolingFan,
        PressureCap,
        CoolantTempSensor,
        FanThermalSwitch,
    ],
    "fuel": [
        FuelPump,
        FuelPressureRegulator,
        FuelInjector,
        OxygenSensor,
    ],
    "ignition": [
        IgnitionCoil,
        SparkPlug,
        CrankshaftPositionSensor,
        CamshaftPositionSensor,
    ],
    "charging": [
        Alternator,
        Battery,
    ],
    "transmission": [
        TransmissionPump,
        TorqueConverter,
        ValveBody,
    ],
    "brakes": [
        MasterCylinder,
        BrakeCaliper,
        ABSModule,
    ],
    "engine": [
        OilPump,
        PistonRings,
        HeadGasket,
    ],
    "steering": [
        PowerSteeringPump,
        SteeringRack,
        TieRodEnd,
    ],
    "suspension": [
        Strut,
        ControlArm,
        WheelBearing,
    ],
    "hvac": [
        ACCompressor,
        BlowerMotor,
        BlendDoor,
        HeaterCore,
    ],
    "emissions": [
        CatalyticConverter,
        EGRValve,
        EVAPCanister,
    ],
}


def get_components_for_system(system_id: str) -> List[ComponentModel]:
    """Get instances of all components for a system."""
    component_classes = COMPONENT_CLASSES.get(system_id, [])
    components = []
    for cls in component_classes:
        try:
            components.append(cls())
        except TypeError:
            # Some components need arguments (like cylinder number)
            # For now, create default instance
            components.append(cls())
    return components


def get_component_by_id(system_id: str, component_id: str) -> Optional[ComponentModel]:
    """Get a specific component by system and component ID."""
    for component in get_components_for_system(system_id):
        if component.id == component_id:
            return component
    return None
