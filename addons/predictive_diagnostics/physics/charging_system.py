"""
Physics-Based Charging System Model

This module implements a first-principles model of an automotive charging system.
It can:

1. FORWARD SIMULATION: Given operating conditions → predict voltage, current, battery state
2. FAULT INJECTION: Model what happens when components fail
3. INVERSE INFERENCE: Given voltage/current readings → identify which fault explains them

Physics modeled:
- Alternator output characteristics (voltage regulation, current capacity)
- Battery chemistry (lead-acid charge/discharge, internal resistance)
- Voltage drop across connections (Ohm's law)
- Load balance (electrical demand vs. generation capacity)

Reference: Bosch Automotive Handbook
           SAE J1979 OBD-II standards
           Battery Council International standards
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

# Battery properties (typical 12V lead-acid)
NOMINAL_BATTERY_VOLTAGE = 12.6  # Volts (fully charged, resting)
BATTERY_CAPACITY_AH = 60  # Amp-hours
INTERNAL_RESISTANCE_MOHM = 5  # milliohms (new battery)

# Alternator properties
NOMINAL_CHARGING_VOLTAGE = 14.2  # Volts (regulated)
VOLTAGE_REGULATION_TOLERANCE = 0.3  # ±0.3V
MAX_ALTERNATOR_CURRENT = 120  # Amps

# Temperature coefficients
BATTERY_TEMP_COEFFICIENT = -0.017  # V/°C from 25°C reference
ALTERNATOR_TEMP_DERATING = 0.01  # Current reduction per °C above 80°C

# Minimum thresholds
MIN_CRANKING_VOLTAGE = 9.6  # Below this, starter won't engage
LOW_VOLTAGE_THRESHOLD = 12.0  # Battery needs charging
HIGH_VOLTAGE_THRESHOLD = 15.0  # Overcharging risk


# =============================================================================
# COMPONENT MODELS
# =============================================================================

@dataclass
class BatteryModel:
    """
    Models lead-acid battery behavior.
    
    Physics:
    - Open circuit voltage indicates state of charge
    - Internal resistance causes voltage drop under load
    - Capacity degrades with age and sulfation
    - Temperature affects performance
    
    V_terminal = V_oc - I × R_internal
    """
    
    # Battery specifications
    nominal_voltage: float = NOMINAL_BATTERY_VOLTAGE
    capacity_ah: float = BATTERY_CAPACITY_AH
    internal_resistance_mohm: float = INTERNAL_RESISTANCE_MOHM
    
    # Battery state
    state_of_charge: float = 1.0  # 0-1 (1 = fully charged)
    state_of_health: float = 1.0  # 0-1 (1 = new battery)
    temperature_c: float = 25.0  # Battery temperature
    
    # Fault states
    sulfated: bool = False
    sulfation_factor: float = 1.0  # Multiplier for internal resistance
    dead_cell: bool = False  # One cell shorted/open
    
    def get_open_circuit_voltage(self) -> float:
        """
        Calculate battery OCV based on state of charge.
        
        For lead-acid: OCV ≈ 11.9 + 0.7 × SOC
        
        Returns:
            Open circuit voltage
        """
        if self.dead_cell:
            # One cell dead = ~2V less
            base_voltage = 10.5 + 0.6 * self.state_of_charge
        else:
            base_voltage = 11.9 + 0.7 * self.state_of_charge
        
        # Temperature correction
        temp_correction = BATTERY_TEMP_COEFFICIENT * (self.temperature_c - 25)
        
        # Health affects capacity but not OCV much
        return base_voltage + temp_correction
    
    def get_internal_resistance(self) -> float:
        """
        Calculate effective internal resistance.
        
        Increases with:
        - Low state of charge
        - Low temperature
        - Age/sulfation
        
        Returns:
            Internal resistance in ohms
        """
        base_r = self.internal_resistance_mohm / 1000  # Convert to ohms
        
        # SOC effect (resistance increases at low SOC)
        soc_factor = 1 + (1 - self.state_of_charge) * 0.5
        
        # Temperature effect (resistance increases when cold)
        if self.temperature_c < 25:
            temp_factor = 1 + (25 - self.temperature_c) * 0.02
        else:
            temp_factor = 1.0
        
        # Health/age effect
        health_factor = 1 + (1 - self.state_of_health) * 2
        
        # Sulfation effect
        if self.sulfated:
            sulfation_mult = self.sulfation_factor
        else:
            sulfation_mult = 1.0
        
        return base_r * soc_factor * temp_factor * health_factor * sulfation_mult
    
    def get_terminal_voltage(self, current_draw: float) -> float:
        """
        Calculate terminal voltage under load.
        
        V = V_oc - I × R
        
        Args:
            current_draw: Current being drawn (positive = discharge)
            
        Returns:
            Terminal voltage
        """
        v_oc = self.get_open_circuit_voltage()
        r_int = self.get_internal_resistance()
        
        # Voltage drop under load
        v_drop = current_draw * r_int
        
        return v_oc - v_drop
    
    def get_cranking_voltage(self, starter_current: float = 200) -> float:
        """
        Calculate voltage during cranking (high current draw).
        
        Args:
            starter_current: Starter motor current draw
            
        Returns:
            Voltage during cranking
        """
        return self.get_terminal_voltage(starter_current)


@dataclass
class AlternatorModel:
    """
    Models alternator behavior.
    
    Physics:
    - Three-phase AC generator with rectifier
    - Voltage regulator maintains output voltage
    - Current output depends on RPM and field current
    - Temperature affects maximum output
    """
    
    # Alternator specifications
    rated_output_amps: float = MAX_ALTERNATOR_CURRENT
    regulated_voltage: float = NOMINAL_CHARGING_VOLTAGE
    
    # Operating parameters
    cut_in_rpm: float = 1000  # Minimum RPM for charging
    full_output_rpm: float = 2500  # RPM for rated output
    
    # Component health
    regulator_voltage: float = NOMINAL_CHARGING_VOLTAGE
    efficiency: float = 0.65  # Typical alternator efficiency
    
    # Fault states
    failed: bool = False
    diode_failed: bool = False  # One diode open/shorted
    regulator_failed_high: bool = False  # Overcharging
    regulator_failed_low: bool = False  # Undercharging
    bearing_worn: bool = False  # Increased friction, noise
    belt_slipping: bool = False
    slip_factor: float = 1.0  # Effective RPM multiplier when slipping
    
    def get_output_voltage(self, rpm: float, temperature_c: float = 80) -> float:
        """
        Calculate alternator output voltage.
        
        Args:
            rpm: Alternator shaft RPM (≈ 2.5x engine RPM)
            temperature_c: Alternator temperature
            
        Returns:
            Output voltage
        """
        if self.failed:
            return 0.0
        
        if self.regulator_failed_high:
            return 16.0  # Overcharging
        
        if self.regulator_failed_low:
            return 12.0  # Not charging properly
        
        # Below cut-in, no output
        effective_rpm = rpm * (self.slip_factor if self.belt_slipping else 1.0)
        if effective_rpm < self.cut_in_rpm:
            return 0.0
        
        # Diode failure causes AC ripple and lower DC output
        if self.diode_failed:
            return self.regulator_voltage * 0.85
        
        # Temperature affects regulation slightly
        temp_factor = 1.0
        if temperature_c > 100:
            temp_factor = 1 - (temperature_c - 100) * 0.002  # Slight voltage drop when hot
        
        return self.regulator_voltage * temp_factor
    
    def get_output_current(
        self,
        rpm: float,
        electrical_load: float,
        temperature_c: float = 80
    ) -> float:
        """
        Calculate available alternator current.
        
        Args:
            rpm: Alternator shaft RPM
            electrical_load: Electrical demand in amps
            temperature_c: Alternator temperature
            
        Returns:
            Available current in amps
        """
        if self.failed:
            return 0.0
        
        # Effective RPM accounting for belt slip
        effective_rpm = rpm * (self.slip_factor if self.belt_slipping else 1.0)
        
        if effective_rpm < self.cut_in_rpm:
            return 0.0
        
        # Current capacity increases with RPM up to rated
        rpm_factor = min(1.0, (effective_rpm - self.cut_in_rpm) / 
                        (self.full_output_rpm - self.cut_in_rpm))
        
        max_current = self.rated_output_amps * rpm_factor
        
        # Temperature derating
        if temperature_c > 80:
            derating = (temperature_c - 80) * ALTERNATOR_TEMP_DERATING
            max_current *= (1 - derating)
        
        # Diode failure reduces output by ~1/3
        if self.diode_failed:
            max_current *= 0.67
        
        # Return lesser of demand or capacity
        return min(electrical_load, max_current)


@dataclass
class VoltageRegulatorModel:
    """
    Models the voltage regulator (may be internal or external).
    
    Physics:
    - Senses system voltage
    - Controls alternator field current
    - Maintains set-point voltage
    """
    
    set_point_voltage: float = NOMINAL_CHARGING_VOLTAGE
    hysteresis: float = 0.1  # Volts
    
    # Fault states
    failed_open: bool = False  # No field current - no charging
    failed_shorted: bool = False  # Full field - overcharging
    
    def get_field_duty_cycle(self, system_voltage: float) -> float:
        """
        Calculate field current duty cycle based on voltage feedback.
        
        Returns:
            Duty cycle 0-1
        """
        if self.failed_open:
            return 0.0
        
        if self.failed_shorted:
            return 1.0
        
        if system_voltage < self.set_point_voltage - self.hysteresis:
            # Voltage low - increase field
            return min(1.0, (self.set_point_voltage - system_voltage) / 2)
        elif system_voltage > self.set_point_voltage + self.hysteresis:
            # Voltage high - decrease field
            return max(0.0, 1 - (system_voltage - self.set_point_voltage) / 2)
        else:
            # In regulation band
            return 0.5


# =============================================================================
# STATE DATACLASS  
# =============================================================================

@dataclass
class ChargingSystemState:
    """Snapshot of charging system state."""
    
    # Voltages
    battery_voltage: float = 0.0
    system_voltage: float = 0.0
    alternator_output_voltage: float = 0.0
    
    # Currents
    alternator_output_current: float = 0.0
    battery_current: float = 0.0  # Positive = charging
    total_electrical_load: float = 0.0
    
    # Battery state
    battery_soc: float = 0.0
    battery_internal_resistance_mohm: float = 0.0
    
    # System status
    charging: bool = False
    charge_warning_light: bool = False
    overcharging: bool = False
    
    # Operating conditions
    engine_rpm: float = 0.0
    alternator_rpm: float = 0.0
    temperature_c: float = 25.0


# =============================================================================
# MAIN CHARGING SYSTEM MODEL
# =============================================================================

@dataclass
class ChargingSystemModel:
    """
    Complete physics-based charging system model.
    
    This models the automotive electrical system:
    1. Alternator generates AC, rectified to DC
    2. Voltage regulator maintains system voltage
    3. Battery stores energy and handles transients
    4. Electrical loads consume current
    """
    
    # Component models
    battery: BatteryModel = field(default_factory=BatteryModel)
    alternator: AlternatorModel = field(default_factory=AlternatorModel)
    regulator: VoltageRegulatorModel = field(default_factory=VoltageRegulatorModel)
    
    # Pulley ratio (alternator spins faster than engine)
    pulley_ratio: float = 2.5
    
    # Connection resistance (cables, grounds)
    connection_resistance_mohm: float = 10  # milliohms
    
    def calculate_electrical_load(
        self,
        headlights: bool = False,
        ac_on: bool = False,
        heated_seats: bool = False,
        audio_high: bool = False,
        other_loads_amps: float = 5.0  # Base load (ECU, fuel pump, etc.)
    ) -> float:
        """
        Calculate total electrical load.
        
        Args:
            headlights: Headlights on
            ac_on: AC compressor clutch engaged
            heated_seats: Heated seats on
            audio_high: High-power audio system
            other_loads_amps: Base electrical load
            
        Returns:
            Total load in amps
        """
        load = other_loads_amps
        
        if headlights:
            load += 15  # ~180W total
        if ac_on:
            load += 5  # Blower, clutch signal
        if heated_seats:
            load += 10  # ~120W
        if audio_high:
            load += 20  # High-power amplifier
        
        return load
    
    def simulate_steady_state(
        self,
        engine_rpm: float,
        headlights: bool = False,
        ac_on: bool = False,
        heated_seats: bool = False,
        audio_high: bool = False,
        ambient_temp_c: float = 25.0
    ) -> ChargingSystemState:
        """
        Simulate charging system at steady state.
        
        Args:
            engine_rpm: Engine speed
            headlights: Headlights on
            ac_on: AC on
            heated_seats: Heated seats
            audio_high: High power audio
            ambient_temp_c: Ambient temperature
            
        Returns:
            ChargingSystemState with all calculated values
        """
        # Calculate alternator RPM
        alt_rpm = engine_rpm * self.pulley_ratio
        
        # Estimate component temperatures
        alt_temp = ambient_temp_c + 40  # Alternator runs hot
        batt_temp = ambient_temp_c + 10  # Battery slightly warmer
        self.battery.temperature_c = batt_temp
        
        # Calculate electrical load
        electrical_load = self.calculate_electrical_load(
            headlights, ac_on, heated_seats, audio_high
        )
        
        # Get alternator output
        alt_voltage = self.alternator.get_output_voltage(alt_rpm, alt_temp)
        alt_current_capacity = self.alternator.get_output_current(
            alt_rpm, electrical_load * 1.5, alt_temp  # Request more than needed
        )
        
        # Determine system operation
        if alt_voltage > 0 and engine_rpm > 0:
            # Engine running - alternator supplies power
            charging = True
            
            # System voltage is alternator output minus connection drop
            connection_drop = (electrical_load * self.connection_resistance_mohm / 1000)
            system_voltage = alt_voltage - connection_drop
            
            # Current balance
            if alt_current_capacity >= electrical_load:
                # Alternator can handle load, excess charges battery
                alt_current = electrical_load + 10  # Plus charging current
                battery_current = alt_current - electrical_load  # Positive = charging
            else:
                # Alternator can't keep up, battery supplements
                alt_current = alt_current_capacity
                battery_current = -(electrical_load - alt_current)  # Negative = discharging
            
        else:
            # Engine off or alternator not producing
            charging = False
            alt_current = 0
            
            # System runs on battery alone
            system_voltage = self.battery.get_terminal_voltage(electrical_load)
            battery_current = -electrical_load  # Discharging
        
        # Battery voltage
        battery_voltage = self.battery.get_terminal_voltage(abs(battery_current))
        
        # Check warning conditions
        charge_warning = system_voltage < LOW_VOLTAGE_THRESHOLD
        overcharging = system_voltage > HIGH_VOLTAGE_THRESHOLD
        
        return ChargingSystemState(
            battery_voltage=battery_voltage,
            system_voltage=system_voltage,
            alternator_output_voltage=alt_voltage,
            alternator_output_current=alt_current,
            battery_current=battery_current,
            total_electrical_load=electrical_load,
            battery_soc=self.battery.state_of_charge,
            battery_internal_resistance_mohm=self.battery.get_internal_resistance() * 1000,
            charging=charging,
            charge_warning_light=charge_warning,
            overcharging=overcharging,
            engine_rpm=engine_rpm,
            alternator_rpm=alt_rpm,
            temperature_c=ambient_temp_c
        )
    
    def simulate_cranking(
        self,
        ambient_temp_c: float = 25.0,
        starter_current: float = 200
    ) -> Tuple[float, bool]:
        """
        Simulate battery voltage during engine cranking.
        
        Args:
            ambient_temp_c: Ambient temperature (affects battery)
            starter_current: Starter motor current draw
            
        Returns:
            Tuple of (cranking voltage, will_start)
        """
        self.battery.temperature_c = ambient_temp_c
        
        cranking_voltage = self.battery.get_cranking_voltage(starter_current)
        will_start = cranking_voltage >= MIN_CRANKING_VOLTAGE
        
        return cranking_voltage, will_start
    
    def inject_fault(self, fault_id: str, severity: float = 1.0) -> None:
        """
        Inject a specific fault into the model.
        
        Args:
            fault_id: Identifier for the fault
            severity: 0-1 severity
        """
        fault_map = {
            # Alternator faults
            "alternator_failed": lambda: setattr(self.alternator, 'failed', True),
            "alternator_diode_failed": lambda: setattr(self.alternator, 'diode_failed', True),
            "alternator_overcharging": lambda: setattr(self.alternator, 'regulator_failed_high', True),
            "alternator_undercharging": lambda: setattr(self.alternator, 'regulator_failed_low', True),
            "belt_slipping": lambda: (
                setattr(self.alternator, 'belt_slipping', True),
                setattr(self.alternator, 'slip_factor', 1 - severity * 0.5)
            ),
            
            # Battery faults
            "battery_weak": lambda: (
                setattr(self.battery, 'state_of_charge', 0.5 - severity * 0.3),
                setattr(self.battery, 'state_of_health', 0.7 - severity * 0.3)
            ),
            "battery_dead_cell": lambda: setattr(self.battery, 'dead_cell', True),
            "battery_sulfated": lambda: (
                setattr(self.battery, 'sulfated', True),
                setattr(self.battery, 'sulfation_factor', 1 + severity * 4)  # Up to 5x resistance
            ),
            
            # Connection faults
            "high_resistance_connection": lambda: (
                setattr(self, 'connection_resistance_mohm', 
                       self.connection_resistance_mohm + severity * 100)  # Add up to 100mohm
            ),
        }
        
        if fault_id in fault_map:
            fault_map[fault_id]()
        else:
            raise ValueError(f"Unknown fault: {fault_id}")
    
    def reset(self) -> None:
        """Reset all components to healthy state."""
        self.battery = BatteryModel()
        self.alternator = AlternatorModel()
        self.regulator = VoltageRegulatorModel()
        self.connection_resistance_mohm = 10


# =============================================================================
# DIAGNOSTIC SIGNATURES
# =============================================================================

def get_charging_fault_signatures() -> Dict[str, Dict]:
    """
    Return diagnostic signatures for charging system faults.
    """
    return {
        "alternator_failed": {
            "description": "Alternator not generating - belt, internal failure",
            "observables": {
                "system_voltage": "low (~12V battery only)",
                "alternator_output_voltage": "0V",
                "charging": "false",
                "charge_warning_light": "on",
            },
            "dtcs": ["P0562 (system voltage low)", "P0620 (alternator control)"],
            "symptoms": ["Battery warning light", "Battery drains", "Dim lights"],
        },
        "alternator_overcharging": {
            "description": "Voltage regulator failed high - overcharging",
            "observables": {
                "system_voltage": "high (>15V)",
                "overcharging": "true",
            },
            "dtcs": ["P0563 (system voltage high)"],
            "symptoms": ["Battery boiling", "Burnt bulbs", "Electrical damage"],
        },
        "battery_weak": {
            "description": "Weak/old battery - reduced capacity and high resistance",
            "observables": {
                "battery_voltage": "low under load",
                "battery_internal_resistance": "high",
                "cranking_voltage": "low",
            },
            "dtcs": ["P0562 (intermittent)"],
            "symptoms": ["Slow cranking", "Hard starting when cold"],
        },
        "battery_dead_cell": {
            "description": "One cell shorted or open - ~2V less",
            "observables": {
                "battery_voltage": "~10.5V (vs normal 12.6V)",
                "system_voltage": "low",
            },
            "dtcs": ["P0562"],
            "symptoms": ["Won't hold charge", "May not start"],
        },
        "belt_slipping": {
            "description": "Drive belt slipping - intermittent charging",
            "observables": {
                "system_voltage": "varies with load/RPM",
                "charging": "intermittent",
            },
            "dtcs": ["P0562 (intermittent)"],
            "symptoms": ["Squealing noise", "Voltage fluctuates"],
        },
    }
