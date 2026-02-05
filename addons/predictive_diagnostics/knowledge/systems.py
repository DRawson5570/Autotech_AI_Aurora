"""
System models for automotive systems.

Each system model encodes:
- State variables (physical quantities)
- Physics equations (how variables relate)
- Components (parts that can fail)
- Normal operating ranges
- Observable outputs (PIDs we can read)

Knowledge source: Advanced Automotive Fault Diagnosis (Denton)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .components import ComponentModel


class SystemType(Enum):
    """Categories of automotive systems."""
    COOLING = "cooling"
    FUEL = "fuel"
    IGNITION = "ignition"
    CHARGING = "charging"
    TRANSMISSION = "transmission"
    BRAKES = "brakes"
    ENGINE = "engine"
    STEERING = "steering"
    SUSPENSION = "suspension"
    HVAC = "hvac"
    EMISSIONS = "emissions"
    INTAKE_EXHAUST = "intake_exhaust"
    LUBRICATION = "lubrication"
    STARTING = "starting"


@dataclass
class PhysicsEquation:
    """
    A physics equation relating system variables.
    
    Examples:
    - heat_rejected = coolant_flow * specific_heat * delta_temp
    - pressure = force / area
    """
    name: str
    description: str
    formula: str  # Human-readable formula
    inputs: List[str]  # Variable names
    output: str  # Variable name
    
    def compute(self, state: Dict[str, float]) -> float:
        """
        Compute output given current state.
        Override in subclasses for actual computation.
        """
        raise NotImplementedError("Subclass must implement compute()")


@dataclass
class OperatingRange:
    """Normal operating range for a state variable."""
    variable: str
    min_value: float
    max_value: float
    unit: str
    description: str = ""
    
    def is_normal(self, value: float) -> bool:
        """Check if value is within normal range."""
        return self.min_value <= value <= self.max_value
    
    def deviation(self, value: float) -> float:
        """Return how far outside normal range (0 if normal)."""
        if value < self.min_value:
            return self.min_value - value
        elif value > self.max_value:
            return value - self.max_value
        return 0.0


@dataclass
class SystemModel:
    """
    Base class for automotive system models.
    
    A system model encodes the physics of how a vehicle system works,
    enabling simulation of failures and their effects on observables.
    """
    
    id: str
    name: str
    system_type: SystemType
    description: str = ""
    
    # State variables (physical quantities in this system)
    state_variables: List[str] = field(default_factory=list)
    
    # Physics equations relating variables
    physics_equations: List[PhysicsEquation] = field(default_factory=list)
    
    # Components in this system
    components: List['ComponentModel'] = field(default_factory=list)
    
    # Observable outputs (PIDs we can read via OBD2)
    observables: Dict[str, str] = field(default_factory=dict)  # pid_name -> variable
    
    # Normal operating ranges
    normal_ranges: List[OperatingRange] = field(default_factory=list)
    
    def get_normal_range(self, variable: str) -> Optional[OperatingRange]:
        """Get the normal operating range for a variable."""
        for r in self.normal_ranges:
            if r.variable == variable:
                return r
        return None
    
    def get_component(self, component_id: str) -> Optional['ComponentModel']:
        """Get a component by ID."""
        for c in self.components:
            if c.id == component_id:
                return c
        return None
    
    def get_all_failure_modes(self) -> List[Tuple[str, str]]:
        """Get all (component_id, failure_mode_id) pairs for this system."""
        failures = []
        for component in self.components:
            for failure in component.failure_modes:
                failures.append((component.id, failure.id))
        return failures


# ==============================================================================
# COOLING SYSTEM
# ==============================================================================

class CoolingSystem(SystemModel):
    """
    Engine cooling system model.
    
    Physics from textbook:
    - Water-cooled system: water jacket, water pump, thermostat, radiator, cooling fan
    - Thermostat: wax capsule type, prevents water circulation until set temperature
    - Water pump: V-belt or multi-V-belt driven, impeller type
    - Sealed systems: operate at ~100 N/m² over atmospheric, raises boiling point to 126.6°C
    - Pressure cap: contains pressure valve (opens at set pressure) and vacuum valve
    
    Key physics:
    - Heat rejected = coolant_flow_rate × specific_heat × (T_engine - T_radiator_outlet)
    - Coolant boiling point rises with pressure (~3°C per 10 kPa)
    - Thermostat opens at set temperature (typically 82-95°C / 180-203°F)
    """
    
    def __init__(self):
        super().__init__(
            id="cooling",
            name="Engine Cooling System",
            system_type=SystemType.COOLING,
            description="Maintains engine at optimal operating temperature through liquid cooling",
            
            # State variables
            state_variables=[
                "coolant_temp",           # °C - Coolant temperature at ECT sensor
                "coolant_flow_rate",      # L/min - Flow through system
                "radiator_outlet_temp",   # °C - Coolant temp leaving radiator
                "system_pressure",        # kPa - Cooling system pressure
                "thermostat_position",    # 0-1 - 0=closed, 1=fully open
                "fan_state",              # 0 or 1 - Off or On
                "coolant_level",          # 0-1 - Fraction of full
                "ambient_temp",           # °C - Outside air temperature
            ],
            
            # Observable via OBD2
            observables={
                "coolant_temp": "coolant_temp",          # PID 05
                "engine_load": "engine_heat_generation", # Indirect
            },
            
            # Normal operating ranges (from textbook)
            normal_ranges=[
                OperatingRange(
                    variable="coolant_temp",
                    min_value=82.0,   # 180°F
                    max_value=105.0,  # 220°F
                    unit="°C",
                    description="Normal operating temperature range"
                ),
                OperatingRange(
                    variable="system_pressure",
                    min_value=90.0,   # ~0.9 bar
                    max_value=120.0,  # ~1.2 bar
                    unit="kPa",
                    description="Normal system pressure (sealed system ~100 N/m² over atmospheric)"
                ),
                OperatingRange(
                    variable="coolant_level",
                    min_value=0.7,
                    max_value=1.0,
                    unit="fraction",
                    description="Normal coolant level"
                ),
            ],
        )
        
        # Initialize components (will be populated by components.py)
        self.components = []


# ==============================================================================
# FUEL SYSTEM
# ==============================================================================

class FuelSystem(SystemModel):
    """
    Fuel delivery system model.
    
    Key physics:
    - Fuel pressure maintained by pump vs regulator
    - Injector pulse width determines fuel quantity
    - Fuel trims indicate ECU compensation
    """
    
    def __init__(self):
        super().__init__(
            id="fuel",
            name="Fuel Delivery System",
            system_type=SystemType.FUEL,
            description="Delivers precise fuel quantity to engine",
            
            state_variables=[
                "fuel_pressure",      # kPa - Rail pressure
                "fuel_flow_rate",     # cc/min - Total flow
                "injector_pw",        # ms - Injector pulse width
                "fuel_level",         # 0-1 - Tank level
                "stft",               # % - Short term fuel trim
                "ltft",               # % - Long term fuel trim
            ],
            
            observables={
                "fuel_pressure": "fuel_pressure",  # PID 0A (some vehicles)
                "stft_bank1": "stft",              # PID 06
                "ltft_bank1": "ltft",              # PID 07
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="fuel_pressure",
                    min_value=270.0,  # ~40 psi
                    max_value=380.0,  # ~55 psi
                    unit="kPa",
                    description="Normal fuel rail pressure"
                ),
                OperatingRange(
                    variable="stft",
                    min_value=-10.0,
                    max_value=10.0,
                    unit="%",
                    description="Normal short-term fuel trim range"
                ),
                OperatingRange(
                    variable="ltft",
                    min_value=-10.0,
                    max_value=10.0,
                    unit="%",
                    description="Normal long-term fuel trim range"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# IGNITION SYSTEM
# ==============================================================================

class IgnitionSystem(SystemModel):
    """
    Ignition system model.
    
    Key physics:
    - Spark timing relative to TDC
    - Coil dwell time determines spark energy
    - Misfire detection via crankshaft acceleration
    """
    
    def __init__(self):
        super().__init__(
            id="ignition",
            name="Ignition System",
            system_type=SystemType.IGNITION,
            description="Provides timed spark for combustion",
            
            state_variables=[
                "spark_timing",       # °BTDC - Spark advance
                "dwell_time",         # ms - Coil charge time
                "secondary_voltage",  # kV - Spark voltage
                "misfire_count",      # Count per 1000 revs
            ],
            
            observables={
                "timing_advance": "spark_timing",  # PID 0E
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="spark_timing",
                    min_value=5.0,
                    max_value=45.0,
                    unit="°BTDC",
                    description="Normal ignition timing range"
                ),
                OperatingRange(
                    variable="misfire_count",
                    min_value=0.0,
                    max_value=2.0,
                    unit="count/1000",
                    description="Acceptable misfire rate"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# CHARGING SYSTEM
# ==============================================================================

class ChargingSystem(SystemModel):
    """
    Charging system model.
    
    Key physics:
    - Alternator output vs RPM and load
    - Battery state of charge
    - Voltage regulation
    """
    
    def __init__(self):
        super().__init__(
            id="charging",
            name="Charging System",
            system_type=SystemType.CHARGING,
            description="Maintains battery charge and powers electrical systems",
            
            state_variables=[
                "battery_voltage",     # V
                "alternator_output",   # A
                "battery_soc",         # % - State of charge
                "charging_current",    # A - Into battery
            ],
            
            observables={
                "control_module_voltage": "battery_voltage",  # PID 42
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="battery_voltage",
                    min_value=13.5,
                    max_value=14.5,
                    unit="V",
                    description="Normal charging voltage (engine running)"
                ),
                OperatingRange(
                    variable="battery_soc",
                    min_value=80.0,
                    max_value=100.0,
                    unit="%",
                    description="Normal battery state of charge"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# TRANSMISSION SYSTEM
# ==============================================================================

class TransmissionSystem(SystemModel):
    """
    Automatic transmission system model.
    
    Key physics:
    - Hydraulic line pressure controls clutch engagement
    - Torque converter slip affects efficiency
    - Fluid temperature affects viscosity and shift quality
    """
    
    def __init__(self):
        super().__init__(
            id="transmission",
            name="Transmission System",
            system_type=SystemType.TRANSMISSION,
            description="Transfers power from engine to wheels with variable ratios",
            
            state_variables=[
                "trans_temp",      # °C - Fluid temperature
                "line_pressure",   # psi - Hydraulic pressure
                "slip_percent",    # % - Torque converter slip
                "shift_time",      # ms - Shift duration
            ],
            
            observables={
                "trans_fluid_temp": "trans_temp",  # PID for trans temp
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="trans_temp",
                    min_value=60.0,
                    max_value=120.0,
                    unit="°C",
                    description="Normal transmission fluid temperature"
                ),
                OperatingRange(
                    variable="line_pressure",
                    min_value=140.0,
                    max_value=180.0,
                    unit="psi",
                    description="Normal line pressure"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# BRAKING SYSTEM
# ==============================================================================

class BrakingSystem(SystemModel):
    """
    Hydraulic braking system model.
    
    Key physics:
    - Hydraulic pressure converts pedal force to brake force
    - Brake pad friction converts kinetic energy to heat
    - ABS modulates pressure to prevent lockup
    """
    
    def __init__(self):
        super().__init__(
            id="brakes",
            name="Braking System",
            system_type=SystemType.BRAKES,
            description="Hydraulic braking with ABS",
            
            state_variables=[
                "brake_pressure",    # psi - Hydraulic pressure
                "rotor_temp",        # °C - Brake rotor temperature
                "pad_thickness",     # mm - Brake pad remaining
                "pedal_travel",      # % - Pedal position
            ],
            
            observables={},
            
            normal_ranges=[
                OperatingRange(
                    variable="brake_pressure",
                    min_value=800.0,
                    max_value=2000.0,
                    unit="psi",
                    description="Normal brake line pressure under braking"
                ),
                OperatingRange(
                    variable="pad_thickness",
                    min_value=3.0,
                    max_value=12.0,
                    unit="mm",
                    description="Normal brake pad thickness"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# ENGINE MECHANICAL SYSTEM
# ==============================================================================

class EngineSystem(SystemModel):
    """
    Engine mechanical system model.
    
    Key physics:
    - Oil pressure depends on pump output and oil viscosity
    - Compression depends on ring/valve seal
    - Manifold vacuum indicates engine load
    """
    
    def __init__(self):
        super().__init__(
            id="engine",
            name="Engine Mechanical",
            system_type=SystemType.ENGINE,
            description="Internal combustion engine mechanical systems",
            
            state_variables=[
                "oil_pressure",          # psi
                "manifold_vacuum",       # inHg
                "compression_variation", # % deviation between cylinders
                "blow_by_pressure",      # inH2O
            ],
            
            observables={
                "intake_manifold_pressure": "manifold_vacuum",
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="oil_pressure",
                    min_value=25.0,
                    max_value=65.0,
                    unit="psi",
                    description="Normal oil pressure at operating temp"
                ),
                OperatingRange(
                    variable="manifold_vacuum",
                    min_value=16.0,
                    max_value=22.0,
                    unit="inHg",
                    description="Normal manifold vacuum at idle"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# STEERING SYSTEM
# ==============================================================================

class SteeringSystem(SystemModel):
    """
    Power steering system model.
    
    Key physics:
    - Hydraulic/electric assist reduces steering effort
    - Steering rack converts rotation to lateral movement
    - Tie rods connect rack to wheels
    """
    
    def __init__(self):
        super().__init__(
            id="steering",
            name="Steering System",
            system_type=SystemType.STEERING,
            description="Steering mechanism with power assist",
            
            state_variables=[
                "steering_assist",   # % - Power assist level
                "ps_pressure",       # psi - Power steering pressure
                "steering_effort",   # Nm - Driver input torque
                "steering_play",     # ° - Free play at wheel
            ],
            
            observables={},
            
            normal_ranges=[
                OperatingRange(
                    variable="steering_effort",
                    min_value=1.0,
                    max_value=5.0,
                    unit="Nm",
                    description="Normal steering effort with power assist"
                ),
                OperatingRange(
                    variable="steering_play",
                    min_value=0.0,
                    max_value=2.0,
                    unit="°",
                    description="Acceptable steering wheel play"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# SUSPENSION SYSTEM
# ==============================================================================

class SuspensionSystem(SystemModel):
    """
    Suspension system model.
    
    Key physics:
    - Springs support vehicle weight
    - Dampers (shocks/struts) control oscillation
    - Bushings isolate noise and vibration
    """
    
    def __init__(self):
        super().__init__(
            id="suspension",
            name="Suspension System",
            system_type=SystemType.SUSPENSION,
            description="Springs, dampers, and linkages",
            
            state_variables=[
                "ride_height",          # inches - Vehicle height
                "damping_coefficient",  # 0-1 - Damper effectiveness
                "body_roll",            # ° - Roll angle in turns
                "bounce_count",         # Count of oscillations after bump
            ],
            
            observables={},
            
            normal_ranges=[
                OperatingRange(
                    variable="ride_height",
                    min_value=-1.0,
                    max_value=1.0,
                    unit="inches",
                    description="Ride height deviation from nominal"
                ),
                OperatingRange(
                    variable="bounce_count",
                    min_value=1.0,
                    max_value=2.0,
                    unit="bounces",
                    description="Oscillations after bump (1-2 is normal)"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# HVAC SYSTEM
# ==============================================================================

class HVACSystem(SystemModel):
    """
    HVAC (Heating, Ventilation, Air Conditioning) system model.
    
    Key physics:
    - Refrigerant cycle provides cooling
    - Heater core uses engine coolant for heat
    - Blend door mixes hot/cold air
    """
    
    def __init__(self):
        super().__init__(
            id="hvac",
            name="HVAC System",
            system_type=SystemType.HVAC,
            description="Climate control for passenger comfort",
            
            state_variables=[
                "vent_temp",                # °C - Air temp at vents
                "refrigerant_pressure_high", # psi - High side pressure
                "refrigerant_pressure_low",  # psi - Low side pressure
                "blower_speed",             # % - Fan speed
            ],
            
            observables={},
            
            normal_ranges=[
                OperatingRange(
                    variable="vent_temp",
                    min_value=5.0,
                    max_value=60.0,
                    unit="°C",
                    description="Normal vent temperature range"
                ),
                OperatingRange(
                    variable="refrigerant_pressure_high",
                    min_value=150.0,
                    max_value=300.0,
                    unit="psi",
                    description="Normal high side pressure (A/C on)"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# EMISSIONS SYSTEM
# ==============================================================================

class EmissionsSystem(SystemModel):
    """
    Emissions control system model.
    
    Key physics:
    - Catalytic converter oxidizes HC/CO
    - EGR dilutes intake charge to reduce NOx
    - EVAP system captures fuel vapors
    """
    
    def __init__(self):
        super().__init__(
            id="emissions",
            name="Emissions Control",
            system_type=SystemType.EMISSIONS,
            description="Exhaust emissions reduction systems",
            
            state_variables=[
                "catalyst_efficiency",  # % - Cat converter efficiency
                "o2_upstream_mv",       # mV - Pre-cat O2 sensor
                "o2_downstream_mv",     # mV - Post-cat O2 sensor
                "egr_flow",             # % - EGR valve position
            ],
            
            observables={
                "catalyst_temp": "catalyst_efficiency",
            },
            
            normal_ranges=[
                OperatingRange(
                    variable="catalyst_efficiency",
                    min_value=90.0,
                    max_value=100.0,
                    unit="%",
                    description="Healthy catalyst efficiency"
                ),
                OperatingRange(
                    variable="o2_downstream_mv",
                    min_value=400.0,
                    max_value=600.0,
                    unit="mV",
                    description="Post-cat O2 steady when cat working"
                ),
            ],
        )
        self.components = []


# ==============================================================================
# REGISTRY
# ==============================================================================

# All available system models
SYSTEM_REGISTRY: Dict[str, SystemModel] = {}


def register_system(system: SystemModel) -> None:
    """Register a system model."""
    SYSTEM_REGISTRY[system.id] = system


def get_system(system_id: str) -> Optional[SystemModel]:
    """Get a system model by ID."""
    return SYSTEM_REGISTRY.get(system_id)


def get_all_systems() -> List[SystemModel]:
    """Get all registered system models."""
    return list(SYSTEM_REGISTRY.values())


# Register default systems
def _init_systems():
    """Initialize and register all system models."""
    register_system(CoolingSystem())
    register_system(FuelSystem())
    register_system(IgnitionSystem())
    register_system(ChargingSystem())
    register_system(TransmissionSystem())
    register_system(BrakingSystem())
    register_system(EngineSystem())
    register_system(SteeringSystem())
    register_system(SuspensionSystem())
    register_system(HVACSystem())
    register_system(EmissionsSystem())


_init_systems()
