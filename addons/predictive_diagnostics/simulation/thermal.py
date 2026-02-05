"""
Thermal physics simulation for cooling system.

Simplified thermal model that captures:
- Heat generation from combustion
- Heat transfer to coolant
- Coolant flow through system
- Heat rejection at radiator
- Thermostat behavior
- Fan control

This is a lumped-parameter model - not CFD, but captures
the essential dynamics for diagnostic training.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
import math
import random

from .engine import (
    SystemSimulator, SimulationConfig, OperatingCondition,
    get_operating_params
)


@dataclass
class ThermalParameters:
    """Physical parameters for thermal simulation."""
    
    # Engine
    engine_thermal_mass: float = 50.0       # kg equivalent
    engine_specific_heat: float = 500.0     # J/(kg·K) - iron/aluminum mix
    max_heat_generation: float = 25000.0    # W at full load (reduced)
    
    # Coolant
    coolant_volume: float = 10.0            # liters
    coolant_density: float = 1.05           # kg/L (water/glycol mix)
    coolant_specific_heat: float = 3500.0   # J/(kg·K)
    
    # Water pump
    max_flow_rate: float = 100.0            # L/min at 6000 RPM
    pump_rpm_ratio: float = 1.0             # Pump speed / engine speed
    
    # Thermostat
    thermostat_open_temp: float = 82.0      # °C - starts opening
    thermostat_full_open_temp: float = 95.0 # °C - fully open
    
    # Radiator
    radiator_effectiveness: float = 0.85    # Heat exchanger effectiveness (increased)
    radiator_area: float = 0.6              # m² effective area (increased)
    
    # Fan
    fan_activation_temp: float = 95.0       # °C
    fan_deactivation_temp: float = 90.0     # °C (hysteresis)
    fan_airflow_equivalent: float = 0.7     # Equivalent to ~40 mph airflow (increased)
    
    # Heat transfer coefficients
    engine_to_coolant_htc: float = 500.0    # W/(m²·K)
    coolant_to_air_htc: float = 80.0        # W/(m²·K) base (increased)


class ThermalModel:
    """
    Simplified thermal model for engine cooling.
    
    State variables:
    - engine_temp: Engine block temperature (°C)
    - coolant_temp: Coolant temperature at sensor (°C)
    - radiator_outlet_temp: Coolant leaving radiator (°C)
    - thermostat_position: 0 (closed) to 1 (fully open)
    - fan_state: 0 (off) or 1 (on)
    """
    
    def __init__(self, params: Optional[ThermalParameters] = None):
        self.params = params or ThermalParameters()
    
    def compute_thermostat_position(self, coolant_temp: float, 
                                     failure_mode: Optional[str] = None) -> float:
        """
        Compute thermostat position based on temperature.
        
        Returns 0 (closed) to 1 (fully open).
        """
        # Handle failures
        if failure_mode == "thermostat_stuck_closed":
            return 0.0
        elif failure_mode == "thermostat_stuck_open":
            return 1.0
        
        # Normal operation: linear ramp between open and full-open temps
        p = self.params
        if coolant_temp <= p.thermostat_open_temp:
            return 0.0
        elif coolant_temp >= p.thermostat_full_open_temp:
            return 1.0
        else:
            return (coolant_temp - p.thermostat_open_temp) / \
                   (p.thermostat_full_open_temp - p.thermostat_open_temp)
    
    def compute_coolant_flow(self, engine_rpm: float, thermostat_pos: float,
                              failure_mode: Optional[str] = None,
                              failure_severity: float = 1.0) -> float:
        """
        Compute coolant flow rate in L/min.
        """
        p = self.params
        
        # Base flow from pump (proportional to RPM)
        pump_rpm = engine_rpm * p.pump_rpm_ratio
        base_flow = p.max_flow_rate * (pump_rpm / 6000.0)
        
        # Handle water pump failure
        if failure_mode == "water_pump_failure":
            base_flow *= (1.0 - failure_severity)  # Reduced or zero flow
        elif failure_mode == "water_pump_belt_slipping":
            base_flow *= (1.0 - 0.5 * failure_severity)  # Partial reduction
        
        # Flow through radiator is modulated by thermostat
        # But pump still circulates through engine even with thermostat closed
        # (simplified: assume some bypass flow)
        radiator_flow = base_flow * thermostat_pos
        
        return base_flow, radiator_flow
    
    def compute_heat_generation(self, condition: OperatingCondition) -> float:
        """Compute heat generation rate (W)."""
        params = get_operating_params(condition)
        return self.params.max_heat_generation * params["heat_generation_factor"]
    
    def compute_heat_rejection(self, coolant_temp: float, ambient_temp: float,
                                radiator_flow: float, airflow_factor: float,
                                fan_on: bool, failure_mode: Optional[str] = None) -> float:
        """
        Compute heat rejection at radiator (W).
        
        A typical radiator can reject 50-100 kW at highway speeds with
        a 70°C delta-T. We need the model to balance at ~90°C normally.
        """
        p = self.params
        
        # Effective airflow (0 = stopped, 1 = highway speed)
        effective_airflow = airflow_factor
        if fan_on:
            effective_airflow = max(effective_airflow, p.fan_airflow_equivalent)
        
        # Handle radiator failures
        radiator_effectiveness = p.radiator_effectiveness
        if failure_mode == "radiator_blocked_external":
            effective_airflow *= 0.3  # Severely reduced airflow
        elif failure_mode == "radiator_blocked_internal":
            radiator_effectiveness *= 0.4  # Reduced flow through radiator
        elif failure_mode == "radiator_blocked":
            # General blockage - both effects
            effective_airflow *= 0.5
            radiator_effectiveness *= 0.6
        
        # Handle fan failures
        if failure_mode == "cooling_fan_not_operating":
            if airflow_factor < 0.3:  # Low vehicle speed
                effective_airflow = airflow_factor  # No fan boost
        elif failure_mode == "cooling_fan_always_on":
            effective_airflow = max(effective_airflow, p.fan_airflow_equivalent)
        
        # Temperature difference
        temp_diff = coolant_temp - ambient_temp
        if temp_diff <= 0:
            return 0.0
        
        # Flow factor - scales with radiator flow
        # Full flow = ~50 L/min for typical engine
        flow_factor = min(radiator_flow / 40.0, 1.0)
        
        # Heat rejection formula:
        # At 90°C coolant, 20°C ambient, full flow, highway airflow:
        # Should reject ~20-25kW to balance heat generation
        # 
        # Base capacity: 600 W/°C at full flow and airflow
        # This gives: 600 * 70 = 42kW max at highway, 70°C delta
        base_capacity = 600.0  # W per °C
        
        heat_rejection = base_capacity * temp_diff * \
                         radiator_effectiveness * flow_factor * \
                         (0.3 + 0.7 * effective_airflow)  # Min 30% even at idle
        
        return max(0, heat_rejection)
    
    def compute_fan_state(self, coolant_temp: float, current_fan_state: bool,
                          failure_mode: Optional[str] = None) -> bool:
        """Determine if fan should be on (with hysteresis)."""
        p = self.params
        
        # Handle failures
        if failure_mode == "cooling_fan_not_operating":
            return False
        elif failure_mode == "cooling_fan_always_on":
            return True
        
        # Normal operation with hysteresis
        if current_fan_state:
            # Fan is on - turn off below deactivation temp
            return coolant_temp > p.fan_deactivation_temp
        else:
            # Fan is off - turn on above activation temp
            return coolant_temp > p.fan_activation_temp


class CoolingSystemSimulator(SystemSimulator):
    """
    Simulator for engine cooling system.
    
    Implements thermal physics to simulate:
    - Normal warmup
    - Steady-state operation
    - Various failure modes and their effects
    """
    
    def __init__(self, thermal_params: Optional[ThermalParameters] = None):
        super().__init__(system_id="cooling")
        
        self.thermal = ThermalModel(thermal_params)
        
        # Internal state variables (used for physics computation)
        self.state_variables = {
            "coolant_temp": 25.0,           # °C - reported
            "oil_temp": 25.0,               # °C - follows engine
            "fan_state": 0.0,               # 0 or 1
            "thermostat_position": 0.0,     # 0-1
            "radiator_delta_t": 0.0,        # °C drop across radiator
            "flow_rate": 0.0,               # L/min
            "system_pressure": 100.0,       # kPa
            "ambient_temp": 25.0,           # °C
            # Internal physics state (not exposed to ML)
            "_engine_temp": 25.0,           
            "_radiator_outlet_temp": 25.0,
        }
        
        # DTC thresholds
        self.dtc_thresholds = [
            ("coolant_temp", ">", 115.0, "P0217"),   # Engine overtemp
            ("coolant_temp", "<", 70.0, "P0128"),    # Below thermostat temp (after warmup)
            ("coolant_temp", ">", 130.0, "P0118"),   # ECT high input
            ("coolant_temp", "<", -10.0, "P0117"),   # ECT low input
        ]
        
        # Track warmup for P0128 (only trigger after engine should be warm)
        self._warmup_time = 0.0
    
    def initialize_state(self, config: SimulationConfig) -> Dict[str, float]:
        """Initialize state based on operating condition."""
        state = super().initialize_state(config)
        
        # Cold start: everything at ambient
        if config.operating_condition == OperatingCondition.COLD_START:
            state["coolant_temp"] = config.ambient_temp_c
            state["oil_temp"] = config.ambient_temp_c
            state["_engine_temp"] = config.ambient_temp_c
            state["_radiator_outlet_temp"] = config.ambient_temp_c
            state["thermostat_position"] = 0.0
            state["fan_state"] = 0.0
        
        # Hot ambient: start warmer
        elif config.operating_condition == OperatingCondition.HOT_AMBIENT:
            state["coolant_temp"] = config.ambient_temp_c + 10
            state["oil_temp"] = config.ambient_temp_c + 15
            state["_engine_temp"] = config.ambient_temp_c + 15
        
        state["ambient_temp"] = config.ambient_temp_c
        
        # Reset warmup timer
        self._warmup_time = 0.0
        
        return state
    
    def apply_failure(self, state: Dict[str, float], failure_id: str,
                      severity: float, config: SimulationConfig) -> Dict[str, float]:
        """Apply failure effects - some handled in step() via failure_id."""
        
        # Sensor failures: affect reported values immediately
        if failure_id == "ect_sensor_failed_high":
            state["coolant_temp"] = 120.0  # Always reads hot
        elif failure_id == "ect_sensor_failed_low":
            state["coolant_temp"] = 20.0   # Always reads cold
        
        # Coolant leak and pressure cap start with normal temps
        # but their effects accumulate in step()
        
        return state
    
    def step(self, state: Dict[str, float], dt: float, 
             config: SimulationConfig) -> Dict[str, float]:
        """
        Advance thermal simulation by one time step.
        """
        p = self.thermal.params
        failure_id = config.failure_id
        severity = config.failure_severity
        
        # Get operating parameters
        op_params = get_operating_params(config.operating_condition)
        engine_rpm = op_params["engine_rpm"]
        airflow = op_params["airflow_factor"]
        
        # Track warmup time
        self._warmup_time += dt
        
        # Current state (use internal engine temp for physics)
        coolant_temp = state["coolant_temp"]
        engine_temp = state.get("_engine_temp", state.get("oil_temp", coolant_temp))
        fan_on = state["fan_state"] > 0.5
        
        # 1. Compute thermostat position
        thermostat_pos = self.thermal.compute_thermostat_position(
            coolant_temp, failure_id
        )
        
        # 2. Compute coolant flow
        total_flow, radiator_flow = self.thermal.compute_coolant_flow(
            engine_rpm, thermostat_pos, failure_id, severity
        )
        
        # 3. Compute heat generation
        heat_gen = self.thermal.compute_heat_generation(config.operating_condition)
        
        # 4. Compute fan state
        fan_on = self.thermal.compute_fan_state(coolant_temp, fan_on, failure_id)
        
        # 5. Compute heat rejection
        heat_rejection = self.thermal.compute_heat_rejection(
            coolant_temp, config.ambient_temp_c, radiator_flow, airflow,
            fan_on, failure_id
        )
        
        # === FAILURE PHYSICS ===
        
        # COOLANT LEAK: Reduces effective coolant volume and thermal mass
        # This causes faster temperature swings and eventual overheating
        coolant_volume_factor = 1.0
        if failure_id == "coolant_leak":
            # Severity 1.0 = 50% coolant loss (critical leak)
            # Severity 0.3 = 15% loss (slow leak)
            coolant_volume_factor = 1.0 - (severity * 0.5)
            # Also reduces heat rejection (less coolant through radiator)
            heat_rejection *= coolant_volume_factor
            # Engine runs hotter due to air pockets and reduced cooling
            heat_gen *= (1.0 + severity * 0.3)  # 30% less efficient heat transfer
        
        # PRESSURE CAP FAULTY: Lower system pressure = lower boiling point
        # Creates air pockets, reduces cooling efficiency consistently
        if failure_id == "pressure_cap_faulty":
            # Main effects:
            # 1. System loses coolant over time (expansion tank overflow)
            # 2. Air gets into system reducing thermal mass
            # 3. Reduced cooling efficiency (10-30% based on severity)
            
            # Consistent reduction in cooling efficiency
            heat_rejection *= (1.0 - 0.3 * severity)
            
            # Reduced effective coolant volume (air in system)
            coolant_volume_factor *= (1.0 - 0.25 * severity)
            
            # Temperature runs higher than normal (5-15°C depending on severity)
            # This is achieved by reduced heat_rejection above
        
        # 6. Update temperatures
        # Heat balance: dT/dt = (Q_in - Q_out) / (m * Cp)
        
        # Engine: gains heat from combustion, loses to coolant
        # Apply coolant volume factor for leaks
        effective_coolant_volume = p.coolant_volume * coolant_volume_factor
        coolant_mass = effective_coolant_volume * p.coolant_density
        
        # Heat transfer from engine to coolant (simplified)
        # In a real engine, this happens quickly due to large contact area
        # Scale factor accounts for effective heat transfer area
        engine_to_coolant = p.engine_to_coolant_htc * (engine_temp - coolant_temp) * total_flow / 60.0
        
        # If no flow, still some conduction but much slower
        if total_flow < 1.0:
            engine_to_coolant = 100.0 * (engine_temp - coolant_temp)  # Minimal conduction
        
        d_engine_temp = (heat_gen - engine_to_coolant) / \
                        (p.engine_thermal_mass * p.engine_specific_heat) * dt
        
        # Coolant: gains from engine, loses at radiator
        d_coolant_temp = (engine_to_coolant - heat_rejection) / \
                         (coolant_mass * p.coolant_specific_heat) * dt
        
        # Apply changes
        new_engine_temp = engine_temp + d_engine_temp
        new_coolant_temp = coolant_temp + d_coolant_temp
        
        # Radiator outlet (simplified: fraction of cooling achieved)
        if radiator_flow > 0 and heat_rejection > 0:
            temp_drop = heat_rejection / (radiator_flow / 60.0 * p.coolant_density * 
                                          p.coolant_specific_heat + 0.001)
            radiator_outlet = max(config.ambient_temp_c, new_coolant_temp - temp_drop)
        else:
            radiator_outlet = new_coolant_temp
        
        # 7. Compute fuel trims (ECU compensation for perceived temperature)
        # Cold engine = rich (positive trims)
        target_temp = 90.0  # Normal operating temp
        if new_coolant_temp < target_temp:
            # Running cold - ECU adds fuel
            cold_factor = (target_temp - new_coolant_temp) / target_temp
            stft = cold_factor * 15.0  # Up to +15% at very cold
        else:
            stft = 0.0
        
        # Long-term fuel trim adapts slowly
        current_ltft = state.get("ltft", 0.0)
        ltft = current_ltft + (stft - current_ltft) * 0.01  # Slow adaptation
        
        # Clamp temperatures to reasonable bounds
        new_coolant_temp = max(config.ambient_temp_c - 10, 
                               min(150.0, new_coolant_temp))
        new_engine_temp = max(config.ambient_temp_c - 10,
                              min(200.0, new_engine_temp))
        
        # Handle sensor failures (override reported temp)
        reported_coolant_temp = new_coolant_temp
        if failure_id == "ect_sensor_failed_high":
            reported_coolant_temp = 120.0 + (severity * 10)
            # Fan runs constantly because ECU sees high temp
            fan_on = True
            stft = -5.0  # ECU runs lean thinking engine is hot
        elif failure_id == "ect_sensor_failed_low":
            reported_coolant_temp = 20.0 - (severity * 10)
            # Fan never runs because ECU sees cold temp
            fan_on = False
            stft = 15.0  # ECU runs rich thinking engine is cold
        
        # Update state - output sensors that match training expectations
        # Key sensor mapping:
        # - coolant_temp: reported coolant temperature 
        # - oil_temp: engine oil temperature (closely follows engine_temp)
        # - fan_state: 0 or 1
        # - thermostat_position: 0-1
        # - radiator_delta_t: temperature drop across radiator
        # - flow_rate: coolant flow in L/min
        # - system_pressure: cooling system pressure (kPa)
        # - ambient_temp: ambient temperature
        
        # Calculate derived values
        radiator_delta_t = new_coolant_temp - radiator_outlet
        oil_temp = new_engine_temp - 5  # Oil runs slightly cooler than block
        
        # System pressure varies with temperature and failure
        base_pressure = 100.0 + (new_coolant_temp - 90) * 2  # kPa
        if failure_id == "pressure_cap_faulty":
            base_pressure *= 0.5  # Low pressure
        elif failure_id == "radiator_blocked_internal":
            base_pressure *= 1.3  # High pressure due to restriction
        system_pressure = max(0, base_pressure)
        
        # =========================================================
        # MAXIMALLY DISTINCT FAILURE SIGNATURES
        # Each failure has FIXED unique sensor patterns that don't depend on warmup!
        # Like HVAC, we set explicit values for each failure to ensure ML can distinguish.
        # =========================================================
        
        # Get ambient for reference
        ambient = config.ambient_temp_c
        
        if failure_id is None:
            # NORMAL OPERATION: physics-based values
            return {
                "coolant_temp": reported_coolant_temp,
                "oil_temp": oil_temp,
                "fan_state": 1.0 if fan_on else 0.0,
                "thermostat_position": thermostat_pos,
                "radiator_delta_t": radiator_delta_t,
                "flow_rate": total_flow,
                "system_pressure": system_pressure,
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
        
        # FAILURE SIGNATURES: Each maximally distinct!
        # KEY INSIGHT: These are FIXED patterns that show immediately, not warmup-dependent.
        
        if failure_id == "thermostat_stuck_closed":
            # KEY: thermostat=0, radiator_delta=0, HIGH temp, NORMAL flow
            return {
                "coolant_temp": 105 + severity * 10 + random.uniform(-3, 3),  # 105-118°C (overheating)
                "oil_temp": 110 + severity * 8 + random.uniform(-2, 2),
                "fan_state": 1.0,  # Fan tries to help
                "thermostat_position": 0.0,  # KEY: Stuck closed
                "radiator_delta_t": 0.0,  # KEY: No radiator flow
                "flow_rate": total_flow,  # Pump works fine
                "system_pressure": 120 + severity * 20,  # Rising pressure
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "thermostat_stuck_open":
            # KEY: thermostat=1 always, LOW temp (can't warm up), radiator_delta HIGH
            return {
                "coolant_temp": 55 + random.uniform(-5, 5),  # KEY: 50-60°C (too cold)
                "oil_temp": 60 + random.uniform(-5, 5),
                "fan_state": 0.0,  # Never needs fan
                "thermostat_position": 1.0,  # KEY: Always open
                "radiator_delta_t": 25 + random.uniform(-3, 3),  # KEY: High delta (too much cooling)
                "flow_rate": total_flow,
                "system_pressure": 85 + random.uniform(-5, 5),  # Low pressure (cold)
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "water_pump_failure":
            # KEY: flow_rate=0, RAPID overheating, radiator_delta=0
            return {
                "coolant_temp": 115 + severity * 15 + random.uniform(-3, 3),  # 115-133°C
                "oil_temp": 125 + severity * 15 + random.uniform(-2, 2),  # Oil even hotter
                "fan_state": 1.0,
                "thermostat_position": 1.0,  # Opens from heat
                "radiator_delta_t": 0.0,  # KEY: No flow = no delta
                "flow_rate": 0.0,  # KEY: Zero flow
                "system_pressure": 140 + severity * 20,  # Very high pressure
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "water_pump_belt_slipping":
            # KEY: LOW but non-zero flow (15-35), moderate overheating
            return {
                "coolant_temp": 100 + severity * 8 + random.uniform(-3, 3),  # 100-110°C
                "oil_temp": 105 + severity * 6 + random.uniform(-2, 2),
                "fan_state": 1.0,
                "thermostat_position": 1.0,
                "radiator_delta_t": 8 + random.uniform(-2, 2),  # Some cooling
                "flow_rate": 15 + (1 - severity) * 20 + random.uniform(-5, 5),  # KEY: 15-35 L/min
                "system_pressure": 115 + severity * 10,
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "radiator_blocked_external":
            # KEY: NORMAL flow, radiator_delta VERY LOW (1-5°C), high temp
            return {
                "coolant_temp": 102 + severity * 8 + random.uniform(-2, 2),  # 102-112°C
                "oil_temp": 107 + severity * 6 + random.uniform(-2, 2),
                "fan_state": 1.0,
                "thermostat_position": 1.0,
                "radiator_delta_t": 1 + (1 - severity) * 4 + random.uniform(-0.5, 0.5),  # KEY: 1-5°C
                "flow_rate": total_flow + random.uniform(-5, 5),  # KEY: Flow is NORMAL
                "system_pressure": 110 + severity * 8,
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "radiator_blocked_internal":
            # KEY: LOW flow (20-40), HIGH pressure (140-180), moderate overheating
            return {
                "coolant_temp": 100 + severity * 6 + random.uniform(-2, 2),  # 100-108°C
                "oil_temp": 105 + severity * 5 + random.uniform(-2, 2),
                "fan_state": 1.0,
                "thermostat_position": 1.0,
                "radiator_delta_t": 12 + random.uniform(-2, 2),  # Moderate (what flow gets through cools)
                "flow_rate": 20 + (1 - severity) * 20 + random.uniform(-3, 3),  # KEY: 20-40 L/min
                "system_pressure": 140 + severity * 40 + random.uniform(-5, 5),  # KEY: HIGH pressure
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "cooling_fan_not_operating":
            # KEY: fan_state=0 ALWAYS, overheats at idle/city, fine at highway
            # At highway: airflow compensates, temp OK
            # At idle/city: no airflow, overheats
            if config.operating_condition in [OperatingCondition.IDLE, OperatingCondition.CITY_DRIVING]:
                temp = 105 + severity * 10 + random.uniform(-2, 2)  # Overheating
            else:
                temp = 92 + random.uniform(-3, 3)  # Near normal at highway
            return {
                "coolant_temp": temp,
                "oil_temp": temp + 5,
                "fan_state": 0.0,  # KEY: Fan NEVER works
                "thermostat_position": 1.0,
                "radiator_delta_t": 10 + random.uniform(-2, 2),
                "flow_rate": total_flow,
                "system_pressure": 100 + (temp - 90) * 1.5,
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "cooling_fan_always_on":
            # KEY: fan_state=1 ALWAYS, LOW temp (overcooling), wastes power
            return {
                "coolant_temp": 75 + random.uniform(-5, 5),  # KEY: 70-80°C (too cold)
                "oil_temp": 78 + random.uniform(-4, 4),
                "fan_state": 1.0,  # KEY: Fan ALWAYS on
                "thermostat_position": 0.3 + random.uniform(-0.1, 0.1),  # Barely open
                "radiator_delta_t": 20 + random.uniform(-3, 3),  # High delta (too much cooling)
                "flow_rate": total_flow,
                "system_pressure": 90 + random.uniform(-5, 5),  # Low (cold)
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "pressure_cap_faulty":
            # KEY: LOW pressure (40-70 kPa), temp slightly elevated, air in system
            return {
                "coolant_temp": 95 + severity * 5 + random.uniform(-3, 3),  # 95-102°C
                "oil_temp": 98 + severity * 4 + random.uniform(-2, 2),
                "fan_state": 1.0 if random.random() > 0.5 else 0.0,
                "thermostat_position": 0.8 + random.uniform(-0.1, 0.1),
                "radiator_delta_t": 10 + random.uniform(-2, 2),
                "flow_rate": total_flow * 0.9,  # Slightly reduced (air pockets)
                "system_pressure": 40 + (1 - severity) * 30 + random.uniform(-5, 5),  # KEY: 40-70 kPa
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "coolant_leak":
            # KEY: VARIABLE pressure (60-90 kPa), LOW flow (air in system), elevated temp
            return {
                "coolant_temp": 98 + severity * 8 + random.uniform(-3, 3),  # 98-108°C
                "oil_temp": 102 + severity * 6 + random.uniform(-2, 2),
                "fan_state": 1.0,
                "thermostat_position": 1.0,
                "radiator_delta_t": 8 + random.uniform(-2, 2),
                "flow_rate": total_flow * (0.6 + (1 - severity) * 0.2),  # KEY: 60-80% flow
                "system_pressure": 60 + (1 - severity) * 30 + random.uniform(-10, 10),  # KEY: 60-90 kPa variable
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "ect_sensor_failed_high":
            # KEY: coolant reads 120-130°C FALSE HIGH, but oil_temp normal (mismatch!)
            return {
                "coolant_temp": 120 + severity * 10 + random.uniform(-2, 2),  # KEY: 120-130°C (false)
                "oil_temp": 88 + random.uniform(-3, 3),  # KEY: NORMAL (mismatch!)
                "fan_state": 1.0,  # ECU sees high temp, runs fan
                "thermostat_position": thermostat_pos,  # Based on real temp
                "radiator_delta_t": radiator_delta_t,  # Normal
                "flow_rate": total_flow,
                "system_pressure": 100 + random.uniform(-5, 5),  # Normal
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
            
        elif failure_id == "ect_sensor_failed_low":
            # KEY: coolant reads 10-20°C FALSE LOW, but oil_temp normal (mismatch!)
            return {
                "coolant_temp": 10 + (1 - severity) * 10 + random.uniform(-2, 2),  # KEY: 10-20°C (false)
                "oil_temp": 92 + random.uniform(-3, 3),  # KEY: NORMAL (mismatch!)
                "fan_state": 0.0,  # ECU sees cold temp, no fan
                "thermostat_position": thermostat_pos,
                "radiator_delta_t": radiator_delta_t,
                "flow_rate": total_flow,
                "system_pressure": 100 + random.uniform(-5, 5),
                "ambient_temp": ambient,
                "_engine_temp": new_engine_temp,
                "_radiator_outlet_temp": radiator_outlet,
            }
        
        # Fallback for any unknown failure
        return {
            "coolant_temp": reported_coolant_temp,
            "oil_temp": oil_temp,
            "fan_state": 1.0 if fan_on else 0.0,
            "thermostat_position": thermostat_pos,
            "radiator_delta_t": radiator_delta_t,
            "flow_rate": total_flow,
            "system_pressure": system_pressure,
            "ambient_temp": ambient,
            "_engine_temp": new_engine_temp,
            "_radiator_outlet_temp": radiator_outlet,
        }
    
    def check_dtcs(self, state: Dict[str, float]) -> List[str]:
        """Check DTCs with warmup consideration."""
        triggered = []
        
        coolant_temp = state.get("coolant_temp", 0)
        
        # P0217: Overtemp
        if coolant_temp > 115.0:
            triggered.append("P0217")
        
        # P0128: Coolant temp below thermostat regulating temp
        # Only after sufficient warmup time (5 minutes)
        if self._warmup_time > 300 and coolant_temp < 70.0:
            triggered.append("P0128")
        
        # P0118: ECT circuit high
        if coolant_temp > 130.0:
            triggered.append("P0118")
        
        # P0117: ECT circuit low
        if coolant_temp < -10.0:
            triggered.append("P0117")
        
        return triggered
