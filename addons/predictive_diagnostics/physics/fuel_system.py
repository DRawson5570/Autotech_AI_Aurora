"""
Physics-Based Fuel System Model

This module implements a first-principles model of an automotive fuel system.
It can:

1. FORWARD SIMULATION: Given operating conditions → predict fuel pressure, trims, AFR
2. FAULT INJECTION: Model what happens when components fail
3. INVERSE INFERENCE: Given actual readings → identify which fault explains deviation

Physics modeled:
- Fuel pump pressure-flow curves
- Injector flow dynamics (pulse width, dead time)
- Air-fuel ratio stoichiometry
- Fuel trim calculations (short and long term)
- Oxygen sensor feedback loop

Reference: Bosch Automotive Handbook
           SAE J1979 OBD-II standards
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

# Stoichiometric air-fuel ratio for gasoline
STOICH_AFR = 14.7  # kg air / kg fuel

# Fuel properties (gasoline)
FUEL_DENSITY = 750  # kg/m³ (0.75 kg/L)
FUEL_ENERGY_DENSITY = 34.2e6  # J/kg (lower heating value)

# Air properties at standard conditions
AIR_DENSITY_STP = 1.225  # kg/m³ at sea level, 15°C
R_AIR = 287  # J/(kg·K) specific gas constant

# Injector constants
INJECTOR_DEAD_TIME_MS = 1.0  # Typical dead time at 14V


# =============================================================================
# COMPONENT MODELS
# =============================================================================

class FuelPumpType(Enum):
    """Type of fuel pump"""
    IN_TANK_ELECTRIC = "in_tank_electric"
    EXTERNAL_ELECTRIC = "external_electric"
    MECHANICAL = "mechanical"
    GDI_HIGH_PRESSURE = "gdi_high_pressure"


@dataclass
class FuelPumpModel:
    """
    Models electric fuel pump behavior.
    
    Physics:
    - Pump creates pressure differential
    - Flow rate depends on pressure demand and pump health
    - Pressure regulated by bypass valve or PWM control
    
    Modern fuel systems: returnless with PWM-controlled pump
    """
    
    # Pump specifications
    pump_type: FuelPumpType = FuelPumpType.IN_TANK_ELECTRIC
    max_pressure_kpa: float = 450  # Maximum pressure capability
    max_flow_lph: float = 150  # Maximum flow rate (L/hr)
    nominal_pressure_kpa: float = 380  # Target regulated pressure
    
    # For GDI systems
    gdi_high_pressure_kpa: float = 15000  # 150 bar for direct injection
    
    # Pump health (1.0 = new, decreasing = worn)
    efficiency: float = 1.0
    
    # Fault states
    failed: bool = False
    weak: bool = False
    weak_factor: float = 1.0  # 1.0 = normal, 0.5 = 50% capacity
    check_valve_leaking: bool = False
    
    def get_pressure_kpa(
        self,
        fuel_demand_lph: float,
        battery_voltage: float = 14.0
    ) -> float:
        """
        Calculate fuel rail pressure given demand.
        
        Args:
            fuel_demand_lph: Current fuel consumption rate
            battery_voltage: Battery/charging system voltage
            
        Returns:
            Fuel rail pressure in kPa
        """
        if self.failed:
            return 0.0
        
        # Voltage affects pump speed/output
        voltage_factor = min(battery_voltage / 14.0, 1.1)
        
        # Effective pump capacity
        effective_flow = self.max_flow_lph * self.efficiency * voltage_factor
        if self.weak:
            effective_flow *= self.weak_factor
        
        # Pressure drops as demand approaches capacity
        # Using simplified pump curve
        demand_ratio = fuel_demand_lph / effective_flow if effective_flow > 0 else 1.0
        
        if demand_ratio > 1.0:
            # Demand exceeds capacity - pressure drops significantly
            pressure = self.nominal_pressure_kpa * (1 - (demand_ratio - 1) * 0.5)
        else:
            # Normal operation - maintain regulated pressure
            pressure = self.nominal_pressure_kpa * (1 - demand_ratio * 0.1)
        
        # Check valve leak causes pressure bleed-down after shutdown
        # (affects hot restart, not running pressure)
        
        return max(0, min(pressure, self.max_pressure_kpa))
    
    def get_flow_capacity_lph(self, battery_voltage: float = 14.0) -> float:
        """Get current pump flow capacity."""
        if self.failed:
            return 0.0
        
        voltage_factor = min(battery_voltage / 14.0, 1.1)
        capacity = self.max_flow_lph * self.efficiency * voltage_factor
        
        if self.weak:
            capacity *= self.weak_factor
        
        return capacity


@dataclass
class FuelInjectorModel:
    """
    Models fuel injector behavior.
    
    Physics:
    - Injector is a solenoid valve
    - Flow rate depends on pressure differential and orifice size
    - Dead time: delay between signal and actual opening
    - Pulse width controls fuel quantity
    
    Flow equation: Q = Cd × A × √(2ΔP/ρ)
    Where:
        Cd = discharge coefficient (~0.8)
        A = orifice area
        ΔP = pressure differential
        ρ = fuel density
    """
    
    # Injector specifications
    static_flow_cc_min: float = 200  # Flow rate at standard pressure (cc/min)
    reference_pressure_kpa: float = 300  # Pressure for static flow rating
    dead_time_ms: float = 1.0  # Electrical dead time
    
    # Injector health
    flow_deviation: float = 0.0  # -0.1 = 10% lean, +0.1 = 10% rich
    
    # Fault states
    failed_open: bool = False  # Stuck open - flooding
    failed_closed: bool = False  # Stuck closed - no fuel
    partially_clogged: bool = False
    clog_factor: float = 1.0  # 1.0 = clear, 0.5 = 50% clogged
    leaking: bool = False
    leak_rate_cc_min: float = 0.0
    
    def get_fuel_mass_mg(
        self,
        pulse_width_ms: float,
        rail_pressure_kpa: float,
        manifold_pressure_kpa: float = 100
    ) -> float:
        """
        Calculate fuel mass delivered per injection event.
        
        Args:
            pulse_width_ms: Commanded pulse width
            rail_pressure_kpa: Fuel rail pressure
            manifold_pressure_kpa: Intake manifold pressure (for port injection)
            
        Returns:
            Fuel mass in milligrams
        """
        if self.failed_closed:
            return 0.0
        
        if self.failed_open:
            # Continuous flow - very rich
            return 1000.0  # Arbitrary large value
        
        # Effective pulse width (subtract dead time)
        effective_pw_ms = max(0, pulse_width_ms - self.dead_time_ms)
        
        # Pressure differential
        delta_p = rail_pressure_kpa - manifold_pressure_kpa
        if delta_p <= 0:
            return 0.0
        
        # Flow scales with sqrt of pressure ratio
        pressure_factor = math.sqrt(delta_p / self.reference_pressure_kpa)
        
        # Base flow rate
        flow_cc_min = self.static_flow_cc_min * pressure_factor
        
        # Apply clog factor
        if self.partially_clogged:
            flow_cc_min *= self.clog_factor
        
        # Apply individual injector deviation
        flow_cc_min *= (1 + self.flow_deviation)
        
        # Convert to mg per pulse
        # flow_cc_min → cc/ms → cc per pulse → grams → mg
        flow_cc_ms = flow_cc_min / 60000
        fuel_cc = flow_cc_ms * effective_pw_ms
        # FUEL_DENSITY is in kg/m³ = g/L, and 1 cc = 0.001 L
        # fuel_cc * (FUEL_DENSITY g/L) * (0.001 L/cc) * 1000 mg/g = fuel_cc * FUEL_DENSITY
        # Wait, that's wrong. FUEL_DENSITY = 750 kg/m³ = 750 g/L = 0.75 g/cc
        fuel_density_g_cc = FUEL_DENSITY / 1000  # 750 kg/m³ = 0.75 g/cc
        fuel_mass_mg = fuel_cc * fuel_density_g_cc * 1000  # cc * g/cc * mg/g
        
        # Add leak if present
        if self.leaking:
            leak_cc_ms = self.leak_rate_cc_min / 60000
            fuel_mass_mg += leak_cc_ms * 10 * FUEL_DENSITY  # Assume 10ms leak window
        
        return fuel_mass_mg


@dataclass
class MAFSensorModel:
    """
    Models Mass Air Flow sensor.
    
    Physics:
    - Hot wire/film anemometer principle
    - Measures air mass flow directly
    - Output is voltage or frequency proportional to flow
    
    Common failure modes:
    - Contamination (oil, dirt) → reads low
    - Damage → erratic readings
    - Complete failure → default to calculated load
    """
    
    # Sensor calibration
    max_flow_gs: float = 300  # Maximum measurable flow (g/s)
    
    # Sensor health
    contamination_factor: float = 1.0  # 1.0 = clean, 0.8 = reads 20% low
    
    # Fault states
    failed: bool = False
    erratic: bool = False
    contaminated: bool = False
    
    def get_reading_gs(self, actual_airflow_gs: float) -> float:
        """
        Get MAF sensor reading given actual airflow.
        
        Args:
            actual_airflow_gs: True air mass flow rate
            
        Returns:
            Sensor reading (may differ from actual if faulty)
        """
        if self.failed:
            return 0.0  # ECU will use speed-density backup
        
        reading = actual_airflow_gs
        
        # Contamination causes underreading
        if self.contaminated:
            reading *= self.contamination_factor
        
        # Erratic sensor adds noise
        if self.erratic:
            import random
            reading *= (0.9 + random.random() * 0.2)  # ±10% noise
        
        return min(reading, self.max_flow_gs)


@dataclass
class O2SensorModel:
    """
    Models oxygen sensor (narrow-band or wide-band).
    
    Physics:
    - Zirconia element generates voltage based on O2 differential
    - Narrow-band: switches at stoich (~450mV)
    - Wide-band: linear output, measures actual AFR
    
    Voltage output (narrow-band):
    - Rich (λ < 1): 800-1000 mV
    - Stoich (λ = 1): ~450 mV
    - Lean (λ > 1): 100-200 mV
    """
    
    # Sensor type
    is_wideband: bool = False
    
    # Sensor health
    response_time_ms: float = 100  # Time to switch states
    
    # Fault states
    failed: bool = False
    lazy: bool = False  # Slow response
    lazy_factor: float = 1.0  # 1.0 = normal, 3.0 = 3x slower
    biased_lean: bool = False  # Always reads lean
    biased_rich: bool = False  # Always reads rich
    heater_failed: bool = False  # Won't reach operating temp
    
    def get_voltage_mv(self, lambda_value: float, sensor_temp_c: float = 600) -> float:
        """
        Get O2 sensor voltage for given lambda (AFR/14.7).
        
        Args:
            lambda_value: Actual lambda (1.0 = stoich)
            sensor_temp_c: Sensor temperature
            
        Returns:
            Sensor voltage in millivolts
        """
        if self.failed:
            return 450  # Stuck at mid-point
        
        if self.heater_failed and sensor_temp_c < 300:
            return 450  # Not hot enough to function
        
        # Apply bias faults
        effective_lambda = lambda_value
        if self.biased_lean:
            effective_lambda *= 1.1  # Reads 10% leaner
        if self.biased_rich:
            effective_lambda *= 0.9  # Reads 10% richer
        
        if self.is_wideband:
            # Wide-band: linear output
            # Typical: 0V at λ=0.7, 5V at λ=1.3
            voltage_mv = 2500 + (effective_lambda - 1.0) * 4000
            return max(0, min(5000, voltage_mv))
        else:
            # Narrow-band: switching behavior
            if effective_lambda < 0.99:
                # Rich
                voltage_mv = 800 + (0.99 - effective_lambda) * 200
            elif effective_lambda > 1.01:
                # Lean
                voltage_mv = 200 - (effective_lambda - 1.01) * 100
            else:
                # Near stoich - rapid transition
                voltage_mv = 450 + (1.0 - effective_lambda) * 3500
            
            return max(50, min(950, voltage_mv))


# =============================================================================
# FUEL SYSTEM STATE
# =============================================================================

@dataclass
class FuelSystemState:
    """
    Complete state of the fuel system at a point in time.
    """
    # Pressures
    fuel_rail_pressure_kpa: float = 380
    fuel_pump_flow_lph: float = 0
    
    # Fuel delivery
    commanded_pulse_width_ms: float = 3.0
    actual_fuel_mass_mg: float = 0
    fuel_consumption_lph: float = 0
    
    # Air-fuel mixture
    commanded_afr: float = 14.7
    actual_afr: float = 14.7
    lambda_value: float = 1.0
    
    # Fuel trims
    short_term_fuel_trim: float = 0.0  # Percentage
    long_term_fuel_trim: float = 0.0   # Percentage
    total_fuel_trim: float = 0.0
    
    # O2 sensor readings
    o2_bank1_mv: float = 450
    o2_bank2_mv: float = 450
    
    # MAF reading
    maf_reading_gs: float = 0
    actual_airflow_gs: float = 0
    
    # Operating state
    in_open_loop: bool = False
    in_fuel_cutoff: bool = False


# =============================================================================
# MAIN FUEL SYSTEM MODEL
# =============================================================================

@dataclass
class FuelSystemModel:
    """
    Complete physics-based fuel system model.
    
    This models the fuel delivery system from tank to combustion:
    1. Fuel pump creates pressure
    2. Injectors meter fuel based on pulse width
    3. ECU calculates pulse width from MAF and target AFR
    4. O2 sensors provide feedback for closed-loop control
    5. Fuel trims compensate for deviations
    """
    
    # Component models
    fuel_pump: FuelPumpModel = field(default_factory=FuelPumpModel)
    maf_sensor: MAFSensorModel = field(default_factory=MAFSensorModel)
    o2_sensor_bank1: O2SensorModel = field(default_factory=O2SensorModel)
    o2_sensor_bank2: O2SensorModel = field(default_factory=lambda: O2SensorModel())
    
    # Injectors (can be individual or averaged)
    injectors: List[FuelInjectorModel] = field(default_factory=lambda: [
        FuelInjectorModel() for _ in range(4)
    ])
    
    # Engine specs
    displacement_liters: float = 2.5
    num_cylinders: int = 4
    volumetric_efficiency: float = 0.85
    
    # Battery voltage affects pump and injectors
    battery_voltage: float = 14.0
    
    def calculate_airflow(
        self,
        rpm: float,
        load_fraction: float,
        ambient_temp_c: float = 25,
        altitude_m: float = 0
    ) -> float:
        """
        Calculate air mass flow into engine.
        
        Physics: Air flow = (Displacement × RPM × VE × ρ_air) / 2
        (Divide by 2 for 4-stroke - each cylinder fires every other revolution)
        
        Args:
            rpm: Engine speed
            load_fraction: 0-1 throttle/load
            ambient_temp_c: Ambient temperature
            altitude_m: Altitude above sea level
            
        Returns:
            Air mass flow in g/s
        """
        # Air density correction for temperature and altitude
        temp_k = ambient_temp_c + 273.15
        pressure_pa = 101325 * math.exp(-altitude_m / 8500)  # Barometric formula
        air_density = pressure_pa / (R_AIR * temp_k)  # kg/m³
        
        # Volumetric flow rate (L/s)
        displacement_m3 = self.displacement_liters / 1000
        vol_flow_m3_s = (displacement_m3 * rpm / 60 * self.volumetric_efficiency * load_fraction) / 2
        
        # Mass flow rate
        mass_flow_kg_s = vol_flow_m3_s * air_density
        mass_flow_gs = mass_flow_kg_s * 1000
        
        return mass_flow_gs
    
    def calculate_fuel_required(
        self,
        airflow_gs: float,
        target_afr: float = STOICH_AFR
    ) -> float:
        """
        Calculate fuel mass required for target AFR.
        
        Args:
            airflow_gs: Air mass flow in g/s
            target_afr: Target air-fuel ratio
            
        Returns:
            Required fuel flow in g/s
        """
        return airflow_gs / target_afr
    
    def calculate_pulse_width(
        self,
        fuel_required_gs: float,
        rpm: float,
        rail_pressure_kpa: float,
        manifold_pressure_kpa: float = 100
    ) -> float:
        """
        Calculate injector pulse width to deliver required fuel.
        
        Args:
            fuel_required_gs: Fuel mass flow needed (g/s)
            rpm: Engine speed
            rail_pressure_kpa: Fuel rail pressure
            manifold_pressure_kpa: Intake manifold pressure
            
        Returns:
            Pulse width in milliseconds
        """
        # Fuel per injection event
        injections_per_second = rpm / 60 * self.num_cylinders / 2
        if injections_per_second <= 0:
            return 0
        
        fuel_per_injection_g = fuel_required_gs / injections_per_second
        fuel_per_injection_mg = fuel_per_injection_g * 1000
        
        # Use average injector characteristics
        avg_injector = self.injectors[0]
        
        # Pressure correction
        delta_p = rail_pressure_kpa - manifold_pressure_kpa
        pressure_factor = math.sqrt(delta_p / avg_injector.reference_pressure_kpa) if delta_p > 0 else 0
        
        # Flow rate at current pressure
        # static_flow_cc_min * density (g/cc) / 60 s/min gives g/s, divide by 1000 for mg/ms
        # FUEL_DENSITY is 750 kg/m³ = 0.75 g/cc
        fuel_density_g_cc = FUEL_DENSITY / 1000
        flow_mg_ms = (avg_injector.static_flow_cc_min * fuel_density_g_cc / 60) * pressure_factor
        
        if flow_mg_ms <= 0:
            return 0
        
        # Pulse width = fuel needed / flow rate + dead time
        effective_pw = fuel_per_injection_mg / flow_mg_ms
        total_pw = effective_pw + avg_injector.dead_time_ms
        
        return total_pw
    
    def simulate_steady_state(
        self,
        rpm: float,
        load_fraction: float,
        ambient_temp_c: float = 25,
        altitude_m: float = 0,
        target_afr: float = STOICH_AFR,
        existing_ltft: float = 0.0
    ) -> FuelSystemState:
        """
        Simulate fuel system at steady state.
        
        This models the closed-loop fuel control:
        1. ECU reads MAF to determine air flow
        2. Calculates required fuel for target AFR
        3. Commands injector pulse width
        4. O2 sensor reads actual mixture
        5. Fuel trims adjust for error
        
        Args:
            rpm: Engine speed
            load_fraction: Engine load (0-1)
            ambient_temp_c: Ambient temperature
            altitude_m: Altitude
            target_afr: Commanded AFR
            existing_ltft: Pre-existing long-term fuel trim
            
        Returns:
            FuelSystemState with all calculated values
        """
        # === ACTUAL AIR FLOW ===
        actual_airflow_gs = self.calculate_airflow(rpm, load_fraction, ambient_temp_c, altitude_m)
        
        # === MAF SENSOR READING (may differ from actual) ===
        maf_reading_gs = self.maf_sensor.get_reading_gs(actual_airflow_gs)
        
        # === FUEL CALCULATION (ECU uses MAF reading) ===
        # ECU thinks this much air is coming in
        fuel_required_gs = self.calculate_fuel_required(maf_reading_gs, target_afr)
        
        # Apply existing LTFT (ECU has learned this adjustment)
        fuel_required_gs *= (1 + existing_ltft / 100)
        
        # === FUEL PRESSURE ===
        # Convert g/s to L/h: (g/s) / (g/L) * 3600 s/h
        # FUEL_DENSITY is kg/m³ = g/L / 1000, so we use 0.75 kg/L = 750 g/L
        fuel_density_g_l = FUEL_DENSITY  # 750 g/L
        fuel_consumption_lph = fuel_required_gs / fuel_density_g_l * 3600
        rail_pressure = self.fuel_pump.get_pressure_kpa(fuel_consumption_lph, self.battery_voltage)
        
        # Manifold pressure estimate
        manifold_pressure = 100 * load_fraction + 30  # Rough approximation
        
        # === PULSE WIDTH CALCULATION ===
        pulse_width = self.calculate_pulse_width(
            fuel_required_gs, rpm, rail_pressure, manifold_pressure
        )
        
        # === ACTUAL FUEL DELIVERED (may differ due to injector issues) ===
        # Each injector fires once per 2 revolutions (4-stroke)
        # injections_per_second_per_cylinder = rpm / 60 / 2
        injections_per_cyl_per_sec = rpm / 120 if rpm > 0 else 0
        
        total_fuel_gs = 0
        total_fuel_mg = 0  # Total fuel mass per injection cycle (all cylinders)
        for injector in self.injectors:
            # Fuel mass per injection event for this injector
            fuel_mg_per_event = injector.get_fuel_mass_mg(pulse_width, rail_pressure, manifold_pressure)
            total_fuel_mg += fuel_mg_per_event
            # Fuel flow rate from this injector (g/s)
            fuel_gs_this_injector = (fuel_mg_per_event / 1000) * injections_per_cyl_per_sec
            total_fuel_gs += fuel_gs_this_injector
        
        actual_fuel_gs = total_fuel_gs
        
        # === ACTUAL AIR-FUEL RATIO ===
        if actual_fuel_gs > 0:
            actual_afr = actual_airflow_gs / actual_fuel_gs
        else:
            actual_afr = 999  # No fuel = infinite AFR
        
        lambda_value = actual_afr / STOICH_AFR
        
        # === O2 SENSOR READINGS ===
        o2_bank1_mv = self.o2_sensor_bank1.get_voltage_mv(lambda_value)
        o2_bank2_mv = self.o2_sensor_bank2.get_voltage_mv(lambda_value)
        
        # === FUEL TRIM CALCULATION ===
        # STFT responds to immediate O2 feedback
        # If running lean (lambda > 1), STFT goes positive (add fuel)
        # If running rich (lambda < 1), STFT goes negative (remove fuel)
        
        if lambda_value > 1.02:
            # Running lean - need more fuel
            stft = (lambda_value - 1.0) * 100  # Percentage
        elif lambda_value < 0.98:
            # Running rich - need less fuel
            stft = (lambda_value - 1.0) * 100
        else:
            stft = 0.0
        
        # Clamp STFT to typical range
        stft = max(-25, min(25, stft))
        
        # LTFT is the existing learned value
        ltft = existing_ltft
        
        # Total trim
        total_trim = stft + ltft
        
        # === BUILD STATE ===
        state = FuelSystemState(
            fuel_rail_pressure_kpa=rail_pressure,
            fuel_pump_flow_lph=fuel_consumption_lph,
            commanded_pulse_width_ms=pulse_width,
            actual_fuel_mass_mg=total_fuel_mg / self.num_cylinders,  # Per cylinder
            fuel_consumption_lph=fuel_consumption_lph,
            commanded_afr=target_afr,
            actual_afr=actual_afr,
            lambda_value=lambda_value,
            short_term_fuel_trim=stft,
            long_term_fuel_trim=ltft,
            total_fuel_trim=total_trim,
            o2_bank1_mv=o2_bank1_mv,
            o2_bank2_mv=o2_bank2_mv,
            maf_reading_gs=maf_reading_gs,
            actual_airflow_gs=actual_airflow_gs,
            in_open_loop=False,
            in_fuel_cutoff=False
        )
        
        return state
    
    def inject_fault(self, fault_id: str, severity: float = 1.0, cylinder: int = None) -> None:
        """
        Inject a specific fault into the model.
        
        Args:
            fault_id: Identifier for the fault
            severity: 0-1 severity
            cylinder: Which cylinder (0-based) for injector faults
        """
        fault_map = {
            # Fuel pump faults
            "fuel_pump_failed": lambda: setattr(self.fuel_pump, 'failed', True),
            "fuel_pump_weak": lambda: (
                setattr(self.fuel_pump, 'weak', True),
                setattr(self.fuel_pump, 'weak_factor', 1 - severity * 0.5)
            ),
            "fuel_pump_check_valve_leak": lambda: setattr(self.fuel_pump, 'check_valve_leaking', True),
            
            # MAF sensor faults
            "maf_failed": lambda: setattr(self.maf_sensor, 'failed', True),
            "maf_contaminated": lambda: (
                setattr(self.maf_sensor, 'contaminated', True),
                setattr(self.maf_sensor, 'contamination_factor', 1 - severity * 0.3)
            ),
            "maf_erratic": lambda: setattr(self.maf_sensor, 'erratic', True),
            
            # O2 sensor faults
            "o2_bank1_failed": lambda: setattr(self.o2_sensor_bank1, 'failed', True),
            "o2_bank1_lazy": lambda: (
                setattr(self.o2_sensor_bank1, 'lazy', True),
                setattr(self.o2_sensor_bank1, 'lazy_factor', 1 + severity * 2)
            ),
            "o2_bank1_biased_lean": lambda: setattr(self.o2_sensor_bank1, 'biased_lean', True),
            "o2_bank1_biased_rich": lambda: setattr(self.o2_sensor_bank1, 'biased_rich', True),
            "o2_bank1_heater_failed": lambda: setattr(self.o2_sensor_bank1, 'heater_failed', True),
            
            # Injector faults (affect specific cylinder or all)
            "injector_clogged": lambda: self._inject_injector_fault(
                'partially_clogged', True, cylinder, clog_factor=1-severity*0.5
            ),
            "injector_leaking": lambda: self._inject_injector_fault(
                'leaking', True, cylinder, leak_rate=severity*5
            ),
            "injector_failed_open": lambda: self._inject_injector_fault(
                'failed_open', True, cylinder
            ),
            "injector_failed_closed": lambda: self._inject_injector_fault(
                'failed_closed', True, cylinder
            ),
            
            # System-wide faults
            "vacuum_leak": lambda: setattr(self, 'volumetric_efficiency', 
                                           self.volumetric_efficiency * (1 + severity * 0.2)),
            "exhaust_leak_pre_o2": lambda: setattr(self.o2_sensor_bank1, 'biased_lean', True),
            "low_battery_voltage": lambda: setattr(self, 'battery_voltage', 12.0 - severity * 2),
        }
        
        if fault_id in fault_map:
            fault_map[fault_id]()
    
    def _inject_injector_fault(
        self, 
        attr: str, 
        value: bool, 
        cylinder: int = None,
        clog_factor: float = None,
        leak_rate: float = None
    ):
        """Helper to inject fault into specific or all injectors."""
        if cylinder is not None and 0 <= cylinder < len(self.injectors):
            targets = [self.injectors[cylinder]]
        else:
            targets = self.injectors
        
        for inj in targets:
            setattr(inj, attr, value)
            if clog_factor is not None:
                inj.clog_factor = clog_factor
            if leak_rate is not None:
                inj.leak_rate_cc_min = leak_rate
    
    def clear_faults(self) -> None:
        """Reset all components to healthy state."""
        self.fuel_pump = FuelPumpModel()
        self.maf_sensor = MAFSensorModel()
        self.o2_sensor_bank1 = O2SensorModel()
        self.o2_sensor_bank2 = O2SensorModel()
        self.injectors = [FuelInjectorModel() for _ in range(self.num_cylinders)]
        self.battery_voltage = 14.0
        self.volumetric_efficiency = 0.85
