"""
Physics-Based Diagnostic Models

This module implements first-principles physics models for automotive systems.
Instead of pattern matching (symptom → likely cause), these models:

1. Simulate expected behavior from physics equations
2. Compare to actual sensor readings
3. Identify which fault produces the observed deviation

"Diagnosis becomes natural because the AI thinks like the system itself."

Systems implemented:
- Cooling: Heat transfer, thermostat hysteresis, pump flow curves
- Fuel: Pump pressure-flow, injector dynamics, AFR/fuel trims
- Ignition: Coil energy, spark breakdown voltage, timing advance
- Charging: Battery OCV/resistance, alternator output, voltage regulation
- Emission: Catalyst efficiency, EGR flow, EVAP leak detection, O2 sensors
- Transmission: Torque converter, clutch packs, planetary gears, shift quality
- Braking: ABS modulation, wheel speed sensors, brake torque
"""

from .cooling_system import (
    CoolingSystemModel,
    CoolingSystemState,
    ThermostatModel,
    RadiatorModel,
    WaterPumpModel,
)

from .fuel_system import (
    FuelSystemModel,
    FuelPumpModel,
    FuelInjectorModel,
    MAFSensorModel,
    O2SensorModel,
)

from .ignition_system import (
    IgnitionSystemModel,
    IgnitionCoilModel,
    SparkPlugModel,
    CrankshaftPositionModel,
)

from .charging_system import (
    ChargingSystemModel,
    BatteryModel,
    AlternatorModel,
)

from .emission_system import (
    EmissionSystemModel,
    CatalyticConverterModel,
    EGRModel,
    EVAPModel,
    O2SensorModel as EmissionO2SensorModel,
)

from .transmission_system import (
    TransmissionModel,
    TorqueConverterModel,
    ClutchPackModel,
    PlanetaryGearSet,
)

from .braking_system import (
    BrakingSystemModel,
    WheelSpeedSensor,
    BrakeCornerModel,
    ABSModulator,
)

from .obd_integration import (
    OBDInterface,
    OBDAdapter,
    ELM327Adapter,
    SimulatedAdapter,
    VehicleData,
    OBDReading,
)

from .diagnostic_engine import (
    DiagnosticEngine,
    DiagnosticCandidate,
)

from .model_based_diagnosis import (
    ModelBasedDiagnostics,
    DiagnosticHypothesis,
    PhysicsTrace,
)

__all__ = [
    # Cooling system
    'CoolingSystemModel',
    'CoolingSystemState', 
    'ThermostatModel',
    'RadiatorModel',
    'WaterPumpModel',
    # Fuel system
    'FuelSystemModel',
    'FuelPumpModel',
    'FuelInjectorModel',
    'MAFSensorModel',
    'O2SensorModel',
    # Ignition system
    'IgnitionSystemModel',
    'IgnitionCoilModel',
    'SparkPlugModel',
    'CrankshaftPositionModel',
    # Charging system
    'ChargingSystemModel',
    'BatteryModel',
    'AlternatorModel',
    # Emission system
    'EmissionSystemModel',
    'CatalyticConverterModel',
    'EGRModel',
    'EVAPModel',
    'EmissionO2SensorModel',
    # Transmission system
    'TransmissionModel',
    'TorqueConverterModel',
    'ClutchPackModel',
    'PlanetaryGearSet',
    # Braking system
    'BrakingSystemModel',
    'WheelSpeedSensor',
    'BrakeCornerModel',
    'ABSModulator',
    # OBD-II integration
    'OBDInterface',
    'OBDAdapter',
    'ELM327Adapter',
    'SimulatedAdapter',
    'VehicleData',
    'OBDReading',
    # Diagnostic engine
    'DiagnosticEngine',
    'DiagnosticCandidate',
    # Legacy
    'ModelBasedDiagnostics',
    'DiagnosticHypothesis',
    'PhysicsTrace',
]
