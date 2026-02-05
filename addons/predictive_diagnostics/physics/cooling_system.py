"""
Physics-Based Cooling System Model

This module implements a first-principles thermodynamic model of an automotive
cooling system. It can:

1. FORWARD SIMULATION: Given operating conditions + component states → predict temperatures
2. FAULT INJECTION: Model what happens when components fail
3. INVERSE INFERENCE: Given actual temps → identify which fault explains the deviation

Physics modeled:
- Heat generation from combustion (function of load, RPM, efficiency)
- Coolant heat absorption (mass flow rate × specific heat × ΔT)
- Radiator heat rejection (effectiveness-NTU method)
- Thermostat behavior (temperature-dependent flow control)
- Fan operation (forced vs. natural convection)

Reference: Fundamentals of Heat and Mass Transfer (Incropera & DeWitt)
           Automotive Cooling System Design (SAE papers)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

# Coolant properties (50/50 ethylene glycol/water at ~90°C)
COOLANT_SPECIFIC_HEAT = 3400  # J/(kg·K) - specific heat capacity
COOLANT_DENSITY = 1040  # kg/m³
COOLANT_THERMAL_CONDUCTIVITY = 0.42  # W/(m·K)

# Air properties (at ~40°C)
AIR_SPECIFIC_HEAT = 1006  # J/(kg·K)
AIR_DENSITY = 1.12  # kg/m³

# Typical engine parameters
GASOLINE_ENERGY_DENSITY = 34.2e6  # J/L (lower heating value)
TYPICAL_THERMAL_EFFICIENCY = 0.30  # 30% of fuel energy becomes work
HEAT_TO_COOLANT_FRACTION = 0.30  # ~30% of fuel energy goes to coolant


# =============================================================================
# COMPONENT MODELS
# =============================================================================

class ThermostatState(Enum):
    """Physical state of thermostat"""
    CLOSED = "closed"           # Fully closed, bypass only
    PARTIALLY_OPEN = "partial"  # Transitioning
    FULLY_OPEN = "open"         # Full flow to radiator


@dataclass
class ThermostatModel:
    """
    Models thermostat behavior using temperature-dependent wax expansion.
    
    Real thermostats use a wax pellet that expands with temperature,
    pushing a valve open. This creates hysteresis and gradual opening.
    
    Physics:
    - Wax expansion is roughly linear with temperature above threshold
    - Opening typically starts at rated temp (e.g., 195°F/90°C)
    - Full open ~10-15°C above rated temp
    - Hysteresis: closes at slightly lower temp than it opens
    """
    
    # Thermostat specs
    rated_temp_c: float = 90.0      # Temperature to start opening (°C)
    full_open_temp_c: float = 102.0  # Temperature for full open (°C)
    hysteresis_c: float = 3.0       # Hysteresis band (°C)
    
    # Flow characteristics
    max_flow_fraction: float = 1.0   # Max flow when fully open (fraction)
    bypass_flow_fraction: float = 0.15  # Flow through bypass when closed
    
    # Fault states
    stuck_closed: bool = False
    stuck_open: bool = False
    stuck_partially: float = 0.0  # 0 = not stuck, 0.5 = stuck half open
    
    def get_flow_fraction(self, coolant_temp_c: float, previous_state: float = 0.0) -> float:
        """
        Calculate flow fraction to radiator based on coolant temperature.
        
        Args:
            coolant_temp_c: Current coolant temperature
            previous_state: Previous flow fraction (for hysteresis)
            
        Returns:
            Flow fraction (0 = bypass only, 1 = full radiator flow)
        """
        # Handle fault states
        if self.stuck_closed:
            return self.bypass_flow_fraction
        if self.stuck_open:
            return self.max_flow_fraction
        if self.stuck_partially > 0:
            return self.stuck_partially
        
        # Normal operation with hysteresis
        # Opening threshold depends on whether we were open or closed
        if previous_state < 0.5:
            # Was mostly closed - use higher threshold to open
            threshold = self.rated_temp_c
        else:
            # Was mostly open - use lower threshold (hysteresis)
            threshold = self.rated_temp_c - self.hysteresis_c
        
        if coolant_temp_c <= threshold:
            return self.bypass_flow_fraction
        elif coolant_temp_c >= self.full_open_temp_c:
            return self.max_flow_fraction
        else:
            # Linear interpolation in transition zone
            fraction = (coolant_temp_c - threshold) / (self.full_open_temp_c - threshold)
            return self.bypass_flow_fraction + fraction * (self.max_flow_fraction - self.bypass_flow_fraction)
    
    def get_state(self, flow_fraction: float) -> ThermostatState:
        """Get discrete state for display"""
        if flow_fraction <= self.bypass_flow_fraction + 0.05:
            return ThermostatState.CLOSED
        elif flow_fraction >= self.max_flow_fraction - 0.05:
            return ThermostatState.FULLY_OPEN
        else:
            return ThermostatState.PARTIALLY_OPEN


@dataclass  
class WaterPumpModel:
    """
    Models centrifugal water pump behavior.
    
    Physics:
    - Flow rate proportional to RPM (approximately)
    - Head (pressure) proportional to RPM²
    - Actual flow depends on system resistance
    
    Typical automotive pump: 20-40 GPM at 3000 RPM
    """
    
    # Pump specs (normalized to 1000 RPM)
    flow_rate_at_1000rpm_lpm: float = 40.0  # Liters per minute at 1000 RPM
    
    # Fault states
    failed: bool = False           # Complete failure
    impeller_slipping: bool = False  # Reduced efficiency (worn impeller, belt slip)
    slip_factor: float = 1.0       # 1.0 = normal, 0.5 = 50% efficiency
    cavitating: bool = False       # Air in system causing cavitation
    
    def get_flow_rate_lpm(self, engine_rpm: float) -> float:
        """
        Calculate coolant flow rate based on engine RPM.
        
        Args:
            engine_rpm: Engine speed in RPM
            
        Returns:
            Flow rate in liters per minute
        """
        if self.failed:
            return 0.0
        
        # Flow roughly proportional to RPM
        # Real pumps have a more complex curve, but linear is reasonable approximation
        base_flow = self.flow_rate_at_1000rpm_lpm * (engine_rpm / 1000.0)
        
        # Apply efficiency losses
        if self.impeller_slipping:
            base_flow *= self.slip_factor
        
        if self.cavitating:
            # Cavitation severely reduces flow
            base_flow *= 0.3
        
        return base_flow
    
    def get_mass_flow_rate_kgs(self, engine_rpm: float) -> float:
        """Get mass flow rate in kg/s"""
        lpm = self.get_flow_rate_lpm(engine_rpm)
        # Convert L/min to kg/s
        return (lpm / 60.0) * (COOLANT_DENSITY / 1000.0)


@dataclass
class RadiatorModel:
    """
    Models radiator heat exchanger using effectiveness-NTU method.
    
    Physics:
    - Heat transfer: Q = ε × C_min × (T_hot_in - T_cold_in)
    - Effectiveness depends on NTU (number of transfer units)
    - NTU = UA / C_min where UA is overall heat transfer coefficient
    
    This is the standard method for heat exchanger analysis.
    """
    
    # Radiator specs
    core_area_m2: float = 0.5        # Frontal area
    fin_efficiency: float = 0.85     # Fin effectiveness
    ua_coefficient: float = 1200.0   # Overall heat transfer (W/K) at design conditions
    
    # Operating conditions affect UA
    design_airflow_kgs: float = 2.0  # Air mass flow at design point
    design_coolant_flow_kgs: float = 1.5
    
    # Fault states
    blocked_fraction: float = 0.0    # 0 = clear, 1 = fully blocked
    external_blockage: float = 0.0   # Bugs, debris on outside
    internal_scale: float = 0.0      # Scale buildup reducing heat transfer
    
    def get_heat_rejection_watts(
        self,
        coolant_temp_in_c: float,
        ambient_temp_c: float,
        coolant_flow_kgs: float,
        air_flow_kgs: float
    ) -> Tuple[float, float]:
        """
        Calculate heat rejected by radiator and outlet temperature.
        
        Uses effectiveness-NTU method for crossflow heat exchanger.
        
        Args:
            coolant_temp_in_c: Coolant inlet temperature (from engine)
            ambient_temp_c: Ambient air temperature  
            coolant_flow_kgs: Coolant mass flow rate (kg/s)
            air_flow_kgs: Air mass flow rate through radiator (kg/s)
            
        Returns:
            Tuple of (heat_rejected_watts, coolant_outlet_temp_c)
        """
        if coolant_flow_kgs <= 0 or air_flow_kgs <= 0:
            return 0.0, coolant_temp_in_c
        
        # Heat capacity rates
        C_coolant = coolant_flow_kgs * COOLANT_SPECIFIC_HEAT  # W/K
        C_air = air_flow_kgs * AIR_SPECIFIC_HEAT  # W/K
        
        C_min = min(C_coolant, C_air)
        C_max = max(C_coolant, C_air)
        C_ratio = C_min / C_max
        
        # Calculate effective UA considering blockages
        effective_ua = self.ua_coefficient
        
        # Internal blockage reduces flow area
        effective_ua *= (1 - self.blocked_fraction)
        
        # External blockage (debris) reduces airside heat transfer
        effective_ua *= (1 - self.external_blockage * 0.8)
        
        # Scale reduces heat transfer coefficient
        effective_ua *= (1 - self.internal_scale * 0.5)
        
        # Adjust UA for actual flow rates vs. design
        # UA scales approximately with flow^0.8 for turbulent flow
        flow_factor_coolant = (coolant_flow_kgs / self.design_coolant_flow_kgs) ** 0.8
        flow_factor_air = (air_flow_kgs / self.design_airflow_kgs) ** 0.8
        effective_ua *= min(flow_factor_coolant, flow_factor_air, 1.0)
        
        # NTU (Number of Transfer Units)
        NTU = effective_ua / C_min
        
        # Effectiveness for crossflow heat exchanger (both fluids unmixed)
        # Approximation: ε = 1 - exp((NTU^0.22 / C_ratio) * (exp(-C_ratio * NTU^0.78) - 1))
        if C_ratio < 0.01:
            # C_ratio ≈ 0, effectiveness approaches 1 - exp(-NTU)
            effectiveness = 1 - math.exp(-NTU)
        else:
            effectiveness = 1 - math.exp(
                (NTU ** 0.22 / C_ratio) * (math.exp(-C_ratio * NTU ** 0.78) - 1)
            )
        
        # Limit effectiveness to physical bounds
        effectiveness = max(0, min(effectiveness, 1.0))
        
        # Maximum possible heat transfer
        Q_max = C_min * (coolant_temp_in_c - ambient_temp_c)
        
        # Actual heat transfer
        Q_actual = effectiveness * Q_max
        
        # Coolant outlet temperature
        coolant_temp_out_c = coolant_temp_in_c - Q_actual / C_coolant
        
        return Q_actual, coolant_temp_out_c


@dataclass
class CoolingFanModel:
    """
    Models electric cooling fan behavior.
    
    Physics:
    - Air flow rate depends on fan speed and blade design
    - Actual airflow affected by vehicle speed (ram air)
    - Power consumption: P = 0.5 × ρ × A × v³ × (1/η)
    """
    
    # Fan specs
    max_airflow_cfm: float = 2500  # Cubic feet per minute at full speed
    activation_temp_c: float = 95.0  # Temperature to turn on
    deactivation_temp_c: float = 88.0  # Temperature to turn off (hysteresis)
    
    # Fault states
    failed: bool = False
    relay_stuck_on: bool = False
    relay_stuck_off: bool = False
    motor_weak: bool = False  # Reduced speed due to worn motor
    weak_factor: float = 0.6
    
    def get_airflow_kgs(
        self,
        coolant_temp_c: float,
        vehicle_speed_kph: float,
        ac_on: bool = False,
        previous_state: bool = False
    ) -> Tuple[float, bool]:
        """
        Calculate air mass flow through radiator.
        
        Args:
            coolant_temp_c: Coolant temperature for fan control
            vehicle_speed_kph: Vehicle speed (affects ram air)
            ac_on: Whether AC is on (may force fan on)
            previous_state: Whether fan was running (for hysteresis)
            
        Returns:
            Tuple of (air_mass_flow_kgs, fan_running)
        """
        # Determine if fan should run
        if self.failed or self.relay_stuck_off:
            fan_running = False
        elif self.relay_stuck_on:
            fan_running = True
        elif ac_on:
            fan_running = True  # AC typically forces fan on
        elif previous_state:
            # Was running - use lower threshold (hysteresis)
            fan_running = coolant_temp_c > self.deactivation_temp_c
        else:
            # Was off - use higher threshold
            fan_running = coolant_temp_c > self.activation_temp_c
        
        # Calculate ram air from vehicle speed
        # Approximate: airflow increases with speed
        # At 100 kph, ram air ≈ 1000-1500 CFM equivalent
        ram_air_cfm = (vehicle_speed_kph / 100.0) * 1200
        
        # Fan contribution
        fan_cfm = 0.0
        if fan_running:
            fan_cfm = self.max_airflow_cfm
            if self.motor_weak:
                fan_cfm *= self.weak_factor
        
        # Total airflow (not simply additive - diminishing returns)
        # Use root-sum-square approximation
        total_cfm = math.sqrt(ram_air_cfm**2 + fan_cfm**2)
        
        # Convert CFM to kg/s
        # 1 CFM = 0.000472 m³/s
        total_m3s = total_cfm * 0.000472
        total_kgs = total_m3s * AIR_DENSITY
        
        return total_kgs, fan_running


# =============================================================================
# SYSTEM STATE
# =============================================================================

@dataclass
class CoolingSystemState:
    """
    Complete state of the cooling system at a point in time.
    
    This is what the physics model calculates and what we compare
    to actual sensor readings.
    """
    # Temperatures (°C)
    coolant_temp_engine: float = 20.0    # At engine (ECT sensor location)
    coolant_temp_radiator_in: float = 20.0   # Entering radiator
    coolant_temp_radiator_out: float = 20.0  # Leaving radiator
    
    # Flow states
    thermostat_flow_fraction: float = 0.0  # 0 = closed, 1 = full open
    thermostat_state: ThermostatState = ThermostatState.CLOSED
    coolant_flow_rate_lpm: float = 0.0
    
    # Heat transfer (Watts)
    heat_generated: float = 0.0      # From combustion
    heat_to_coolant: float = 0.0     # Absorbed by coolant
    heat_rejected: float = 0.0       # Rejected by radiator
    
    # Fan state
    fan_running: bool = False
    airflow_kgs: float = 0.0
    
    # System pressure (for advanced modeling)
    system_pressure_kpa: float = 120.0  # Typical pressurized system
    
    # Energy balance
    heat_imbalance: float = 0.0  # Positive = heating up, negative = cooling down


# =============================================================================
# MAIN COOLING SYSTEM MODEL
# =============================================================================

@dataclass
class CoolingSystemModel:
    """
    Complete physics-based cooling system model.
    
    This is the core of model-based diagnosis. It can:
    
    1. SIMULATE: Given operating conditions → predict all temperatures
    2. INJECT FAULTS: Set component failure states → see effect
    3. COMPARE: Model prediction vs. actual sensors → find deviation
    
    The key insight: each fault produces a UNIQUE signature in the physics.
    - Thermostat stuck closed: high engine temp, cold radiator
    - Thermostat stuck open: low engine temp, warm radiator  
    - Water pump failed: high temp, no ΔT across radiator
    - Radiator blocked: high temp, large ΔT, still some flow
    
    Usage:
        model = CoolingSystemModel()
        
        # Normal operation
        state = model.simulate(rpm=2000, load=0.5, ambient=25, speed=60)
        print(f"Expected coolant temp: {state.coolant_temp_engine}°C")
        
        # Inject fault
        model.thermostat.stuck_closed = True
        faulty_state = model.simulate(rpm=2000, load=0.5, ambient=25, speed=60)
        print(f"With stuck thermostat: {faulty_state.coolant_temp_engine}°C")
    """
    
    # Component models
    thermostat: ThermostatModel = field(default_factory=ThermostatModel)
    water_pump: WaterPumpModel = field(default_factory=WaterPumpModel)
    radiator: RadiatorModel = field(default_factory=RadiatorModel)
    fan: CoolingFanModel = field(default_factory=CoolingFanModel)
    
    # Engine specs (can be set per vehicle)
    displacement_liters: float = 2.5
    num_cylinders: int = 4
    thermal_efficiency: float = 0.30
    heat_to_coolant_fraction: float = 0.30
    
    # Coolant system specs
    coolant_volume_liters: float = 8.0  # Total system capacity
    engine_thermal_mass_kj_k: float = 50.0  # Engine block thermal mass (kJ/K)
    
    # Coolant level (fraction of normal)
    coolant_level: float = 1.0  # 1.0 = full, 0.5 = low
    
    def calculate_heat_generation(
        self,
        rpm: float,
        load_fraction: float,
        fuel_rate_lph: float = None
    ) -> float:
        """
        Calculate heat generated by combustion that goes to coolant.
        
        Physics:
        - Fuel energy = fuel_rate × energy_density
        - ~30% becomes mechanical work
        - ~30% goes to coolant
        - ~40% goes out exhaust
        
        Args:
            rpm: Engine speed
            load_fraction: 0-1 load (0=idle, 1=WOT)
            fuel_rate_lph: Fuel consumption (L/hr), calculated if not provided
            
        Returns:
            Heat to coolant in Watts
        """
        if fuel_rate_lph is None:
            # Estimate fuel rate from RPM and load
            # Rough approximation: BSFC ~250 g/kWh, power scales with load
            # Typical 2.5L engine: ~150 kW peak
            peak_power_kw = self.displacement_liters * 60  # Rough: 60 kW/L
            current_power_kw = peak_power_kw * load_fraction * (rpm / 6000)
            
            # BSFC (brake specific fuel consumption) ~250-300 g/kWh
            bsfc = 280  # g/kWh
            fuel_rate_kg_h = current_power_kw * bsfc / 1000
            fuel_rate_lph = fuel_rate_kg_h / 0.75  # Gasoline density ~0.75 kg/L
            
            # Minimum fuel at idle
            fuel_rate_lph = max(fuel_rate_lph, 0.5)
        
        # Total fuel energy (Watts)
        fuel_energy_w = (fuel_rate_lph / 3600) * GASOLINE_ENERGY_DENSITY
        
        # Heat to coolant
        heat_to_coolant = fuel_energy_w * self.heat_to_coolant_fraction
        
        return heat_to_coolant
    
    def simulate_steady_state(
        self,
        rpm: float,
        load_fraction: float,
        ambient_temp_c: float,
        vehicle_speed_kph: float = 0,
        ac_on: bool = False,
        initial_temp_c: float = None,
        max_iterations: int = 100,
        tolerance_c: float = 0.1
    ) -> CoolingSystemState:
        """
        Calculate steady-state temperatures for given operating conditions.
        
        This iteratively solves the heat balance equations until equilibrium:
        Heat generated = Heat rejected (at steady state)
        
        Args:
            rpm: Engine RPM
            load_fraction: Engine load (0-1)
            ambient_temp_c: Ambient air temperature
            vehicle_speed_kph: Vehicle speed
            ac_on: AC compressor running
            initial_temp_c: Starting temperature for iteration
            max_iterations: Max solver iterations
            tolerance_c: Convergence tolerance
            
        Returns:
            CoolingSystemState with all calculated values
        """
        # Initialize
        if initial_temp_c is None:
            initial_temp_c = ambient_temp_c + 20
        
        coolant_temp = initial_temp_c
        thermostat_position = 0.0
        fan_running = False
        
        # Heat generation (constant for given operating point)
        heat_generated = self.calculate_heat_generation(rpm, load_fraction)
        
        # Coolant flow from pump
        coolant_flow_lpm = self.water_pump.get_flow_rate_lpm(rpm)
        coolant_flow_kgs = self.water_pump.get_mass_flow_rate_kgs(rpm)
        
        # Adjust for low coolant level
        if self.coolant_level < 0.7:
            # Low coolant causes air pockets, reduced flow
            coolant_flow_kgs *= self.coolant_level
        
        # Iterate to find equilibrium
        for iteration in range(max_iterations):
            # Thermostat position based on current temp
            thermostat_position = self.thermostat.get_flow_fraction(
                coolant_temp, thermostat_position
            )
            
            # Flow to radiator vs bypass
            radiator_flow_kgs = coolant_flow_kgs * thermostat_position
            
            # Airflow (fan + ram air)
            airflow_kgs, fan_running = self.fan.get_airflow_kgs(
                coolant_temp, vehicle_speed_kph, ac_on, fan_running
            )
            
            # Radiator heat rejection
            if radiator_flow_kgs > 0.01:  # Meaningful flow
                heat_rejected, radiator_out_temp = self.radiator.get_heat_rejection_watts(
                    coolant_temp,
                    ambient_temp_c,
                    radiator_flow_kgs,
                    airflow_kgs
                )
            else:
                # No radiator flow - minimal heat rejection (through block surface)
                heat_rejected = (coolant_temp - ambient_temp_c) * 20  # ~20 W/K ambient loss
                radiator_out_temp = coolant_temp
            
            # Heat balance
            heat_imbalance = heat_generated - heat_rejected
            
            # Temperature change rate
            # Q = m × c × dT/dt → dT = Q × dt / (m × c)
            # Using effective thermal mass of coolant + engine
            # Coolant: 8L × 1.04 kg/L × 3400 J/(kg·K) = 28,288 J/K = 28.3 kJ/K
            coolant_thermal_mass_jk = self.coolant_volume_liters * 1.04 * COOLANT_SPECIFIC_HEAT
            # Engine block: 50 kJ/K = 50,000 J/K
            engine_thermal_mass_jk = self.engine_thermal_mass_kj_k * 1000
            total_thermal_mass_jk = coolant_thermal_mass_jk + engine_thermal_mass_jk
            
            # Pseudo time step for iteration (not real time)
            # For 10 kW imbalance and 78,288 J/K total: 10000 / 78288 * 10 = 1.3°C/iter
            temp_adjustment = heat_imbalance / total_thermal_mass_jk * 10  # °C per iteration
            
            new_temp = coolant_temp + temp_adjustment
            
            # Check convergence
            if abs(new_temp - coolant_temp) < tolerance_c:
                coolant_temp = new_temp
                break
            
            coolant_temp = new_temp
            
            # Prevent runaway
            coolant_temp = max(ambient_temp_c, min(coolant_temp, 150))
        
        # Build final state
        state = CoolingSystemState(
            coolant_temp_engine=coolant_temp,
            coolant_temp_radiator_in=coolant_temp,  # Approximately same
            coolant_temp_radiator_out=radiator_out_temp if radiator_flow_kgs > 0.01 else coolant_temp,
            thermostat_flow_fraction=thermostat_position,
            thermostat_state=self.thermostat.get_state(thermostat_position),
            coolant_flow_rate_lpm=coolant_flow_lpm,
            heat_generated=heat_generated,
            heat_to_coolant=heat_generated,
            heat_rejected=heat_rejected,
            fan_running=fan_running,
            airflow_kgs=airflow_kgs,
            heat_imbalance=heat_imbalance,
        )
        
        return state
    
    def simulate_transient(
        self,
        rpm: float,
        load_fraction: float,
        ambient_temp_c: float,
        vehicle_speed_kph: float,
        initial_temp_c: float,
        duration_seconds: float,
        time_step: float = 1.0,
        ac_on: bool = False
    ) -> List[Tuple[float, CoolingSystemState]]:
        """
        Simulate temperature evolution over time (transient response).
        
        Useful for:
        - Warmup behavior (how long to reach operating temp)
        - Cooling after shutdown
        - Response to sudden load changes
        
        Args:
            rpm, load_fraction, etc.: Operating conditions
            initial_temp_c: Starting temperature
            duration_seconds: How long to simulate
            time_step: Simulation resolution
            
        Returns:
            List of (time, state) tuples
        """
        results = []
        
        current_temp = initial_temp_c
        thermostat_position = 0.0
        fan_running = False
        
        heat_generated = self.calculate_heat_generation(rpm, load_fraction)
        coolant_flow_kgs = self.water_pump.get_mass_flow_rate_kgs(rpm)
        
        # Thermal mass (J/K)
        thermal_mass = (
            self.coolant_volume_liters * COOLANT_DENSITY * COOLANT_SPECIFIC_HEAT +
            self.engine_thermal_mass_kj_k * 1000
        )
        
        t = 0.0
        while t <= duration_seconds:
            # Update thermostat
            thermostat_position = self.thermostat.get_flow_fraction(
                current_temp, thermostat_position
            )
            radiator_flow_kgs = coolant_flow_kgs * thermostat_position
            
            # Update fan
            airflow_kgs, fan_running = self.fan.get_airflow_kgs(
                current_temp, vehicle_speed_kph, ac_on, fan_running
            )
            
            # Heat rejection
            if radiator_flow_kgs > 0.01:
                heat_rejected, _ = self.radiator.get_heat_rejection_watts(
                    current_temp, ambient_temp_c, radiator_flow_kgs, airflow_kgs
                )
            else:
                heat_rejected = (current_temp - ambient_temp_c) * 20
            
            # Temperature change
            dT = (heat_generated - heat_rejected) * time_step / thermal_mass
            current_temp += dT
            current_temp = max(ambient_temp_c - 5, min(current_temp, 150))
            
            # Record state
            state = CoolingSystemState(
                coolant_temp_engine=current_temp,
                thermostat_flow_fraction=thermostat_position,
                thermostat_state=self.thermostat.get_state(thermostat_position),
                coolant_flow_rate_lpm=coolant_flow_kgs * 60 / (COOLANT_DENSITY / 1000),
                heat_generated=heat_generated,
                heat_rejected=heat_rejected,
                fan_running=fan_running,
                airflow_kgs=airflow_kgs,
                heat_imbalance=heat_generated - heat_rejected,
            )
            results.append((t, state))
            
            t += time_step
        
        return results
    
    def reset_faults(self):
        """Clear all fault states"""
        self.thermostat.stuck_closed = False
        self.thermostat.stuck_open = False
        self.thermostat.stuck_partially = 0.0
        
        self.water_pump.failed = False
        self.water_pump.impeller_slipping = False
        self.water_pump.slip_factor = 1.0
        self.water_pump.cavitating = False
        
        self.radiator.blocked_fraction = 0.0
        self.radiator.external_blockage = 0.0
        self.radiator.internal_scale = 0.0
        
        self.fan.failed = False
        self.fan.relay_stuck_on = False
        self.fan.relay_stuck_off = False
        self.fan.motor_weak = False
        
        self.coolant_level = 1.0
    
    def inject_fault(self, fault_id: str, severity: float = 1.0) -> None:
        """
        Inject a specific fault into the model.
        
        Args:
            fault_id: Identifier for the fault
            severity: 0-1 severity (for gradual faults)
        """
        fault_map = {
            "thermostat_stuck_closed": lambda: setattr(self.thermostat, 'stuck_closed', True),
            "thermostat_stuck_open": lambda: setattr(self.thermostat, 'stuck_open', True),
            "thermostat_stuck_partial": lambda: setattr(self.thermostat, 'stuck_partially', 0.3),
            
            "water_pump_failed": lambda: setattr(self.water_pump, 'failed', True),
            "water_pump_slipping": lambda: (
                setattr(self.water_pump, 'impeller_slipping', True),
                setattr(self.water_pump, 'slip_factor', 1 - severity * 0.5)
            ),
            "water_pump_cavitating": lambda: setattr(self.water_pump, 'cavitating', True),
            
            "radiator_blocked_internal": lambda: setattr(self.radiator, 'blocked_fraction', severity * 0.7),
            "radiator_blocked_external": lambda: setattr(self.radiator, 'external_blockage', severity * 0.8),
            "radiator_scale_buildup": lambda: setattr(self.radiator, 'internal_scale', severity * 0.6),
            
            "fan_failed": lambda: setattr(self.fan, 'failed', True),
            "fan_relay_stuck_on": lambda: setattr(self.fan, 'relay_stuck_on', True),
            "fan_relay_stuck_off": lambda: setattr(self.fan, 'relay_stuck_off', True),
            "fan_motor_weak": lambda: (
                setattr(self.fan, 'motor_weak', True),
                setattr(self.fan, 'weak_factor', 1 - severity * 0.5)
            ),
            
            "coolant_low": lambda: setattr(self, 'coolant_level', 1 - severity * 0.5),
            "coolant_leak_severe": lambda: setattr(self, 'coolant_level', 0.3),
        }
        
        if fault_id in fault_map:
            result = fault_map[fault_id]()
            # Handle functions that return tuples (multiple setattrs)
