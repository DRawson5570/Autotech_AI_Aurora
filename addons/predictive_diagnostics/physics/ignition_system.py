"""
Physics-Based Ignition System Model

This module implements a first-principles model of an automotive ignition system.
It can:

1. FORWARD SIMULATION: Given operating conditions → predict spark energy, timing, combustion
2. FAULT INJECTION: Model what happens when components fail
3. INVERSE INFERENCE: Given misfire patterns → identify which fault explains them

Physics modeled:
- Ignition coil energy storage (E = ½LI²)
- Spark plug gap breakdown voltage
- Combustion timing and knock threshold
- Misfire detection via crankshaft position variation

Reference: Bosch Automotive Handbook
           SAE J1979 OBD-II standards
           Heywood - Internal Combustion Engine Fundamentals
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math
import random


# =============================================================================
# PHYSICAL CONSTANTS
# =============================================================================

# Ignition coil properties
TYPICAL_COIL_INDUCTANCE_MH = 8.0  # Primary inductance (millihenries)
TYPICAL_COIL_RESISTANCE_OHMS = 0.5  # Primary resistance
TYPICAL_TURNS_RATIO = 100  # Secondary/primary turns ratio

# Spark plug properties
NOMINAL_GAP_MM = 1.0  # Typical spark plug gap
BREAKDOWN_VOLTAGE_KV_PER_MM = 3.0  # kV needed per mm gap at atmospheric pressure
PRESSURE_FACTOR = 0.1  # Additional kV per bar of cylinder pressure

# Combustion properties
STOICH_AFR = 14.7
FLAME_SPEED_MS = 30  # m/s for gasoline at stoich
COMBUSTION_DURATION_DEG = 50  # Typical burn duration in crank degrees

# Knock threshold
KNOCK_ONSET_TEMP_K = 1100  # End-gas auto-ignition temperature


# =============================================================================
# COMPONENT MODELS
# =============================================================================

@dataclass
class IgnitionCoilModel:
    """
    Models ignition coil behavior.
    
    Physics:
    - Primary circuit charges: I(t) = (V/R)(1 - e^(-Rt/L))
    - Energy stored: E = ½LI²
    - Secondary voltage: V2 = N × dI/dt (during collapse)
    
    The coil stores energy in its magnetic field during dwell time,
    then releases it as high voltage when the primary circuit opens.
    """
    
    # Coil specifications
    primary_inductance_mh: float = TYPICAL_COIL_INDUCTANCE_MH
    primary_resistance_ohms: float = TYPICAL_COIL_RESISTANCE_OHMS
    turns_ratio: float = TYPICAL_TURNS_RATIO
    
    # Coil health
    shorted_turns: float = 0.0  # Fraction of turns shorted (0-1)
    
    # Fault states
    failed_open: bool = False  # No spark
    weak: bool = False
    weak_factor: float = 1.0  # Energy multiplier when weak
    intermittent: bool = False
    intermittent_failure_rate: float = 0.1  # Probability of failure per spark
    
    def get_dwell_current(
        self,
        battery_voltage: float,
        dwell_time_ms: float
    ) -> float:
        """
        Calculate primary current at end of dwell period.
        
        I(t) = (V/R)(1 - e^(-Rt/L))
        
        Args:
            battery_voltage: System voltage
            dwell_time_ms: Dwell time in milliseconds
            
        Returns:
            Primary current in amps
        """
        if self.failed_open:
            return 0.0
        
        # Effective inductance (reduced by shorted turns)
        l_eff = self.primary_inductance_mh * (1 - self.shorted_turns) / 1000  # Convert to H
        r = self.primary_resistance_ohms
        
        if l_eff <= 0 or r <= 0:
            return 0.0
        
        # Time constant
        tau = l_eff / r  # seconds
        t = dwell_time_ms / 1000  # Convert to seconds
        
        # Steady-state current
        i_max = battery_voltage / r
        
        # Current at end of dwell
        current = i_max * (1 - math.exp(-t / tau))
        
        return current
    
    def get_spark_energy_mj(
        self,
        battery_voltage: float,
        dwell_time_ms: float
    ) -> float:
        """
        Calculate energy available for spark.
        
        E = ½LI²
        
        Args:
            battery_voltage: System voltage
            dwell_time_ms: Dwell time
            
        Returns:
            Spark energy in millijoules
        """
        if self.failed_open:
            return 0.0
        
        # Check intermittent failure
        if self.intermittent and random.random() < self.intermittent_failure_rate:
            return 0.0
        
        current = self.get_dwell_current(battery_voltage, dwell_time_ms)
        l_eff = self.primary_inductance_mh * (1 - self.shorted_turns) / 1000
        
        # Energy stored
        energy_j = 0.5 * l_eff * current * current
        energy_mj = energy_j * 1000
        
        # Apply weak factor
        if self.weak:
            energy_mj *= self.weak_factor
        
        return energy_mj
    
    def get_secondary_voltage_kv(
        self,
        battery_voltage: float,
        dwell_time_ms: float,
        collapse_time_us: float = 100
    ) -> float:
        """
        Estimate peak secondary voltage during coil collapse.
        
        V_secondary ≈ N × L × dI/dt
        
        Args:
            battery_voltage: System voltage
            dwell_time_ms: Dwell time
            collapse_time_us: Time for primary current to collapse
            
        Returns:
            Peak secondary voltage in kilovolts
        """
        if self.failed_open:
            return 0.0
        
        current = self.get_dwell_current(battery_voltage, dwell_time_ms)
        l_eff = self.primary_inductance_mh * (1 - self.shorted_turns) / 1000
        
        # dI/dt during collapse
        di_dt = current / (collapse_time_us / 1e6)
        
        # Secondary voltage
        v_secondary = self.turns_ratio * l_eff * di_dt
        v_kv = v_secondary / 1000
        
        if self.weak:
            v_kv *= self.weak_factor
        
        return min(v_kv, 50)  # Cap at realistic max


@dataclass 
class SparkPlugModel:
    """
    Models spark plug behavior.
    
    Physics:
    - Breakdown voltage depends on gap and cylinder pressure
    - V_breakdown = k × gap × (1 + pressure_factor × P)
    - Fouling increases required voltage
    - Worn electrodes increase gap
    """
    
    # Plug specifications
    gap_mm: float = NOMINAL_GAP_MM
    heat_range: int = 6  # 1-10 scale, affects fouling tendency
    
    # Plug health  
    electrode_wear_mm: float = 0.0  # Additional gap from wear
    fouling_level: float = 0.0  # 0-1, increases required voltage
    
    # Fault states
    cracked_insulator: bool = False  # Voltage leaks to ground
    bridged_gap: bool = False  # Carbon bridge shorts gap
    
    def get_required_voltage_kv(
        self,
        cylinder_pressure_bar: float,
        afr: float = STOICH_AFR
    ) -> float:
        """
        Calculate voltage required to fire spark plug.
        
        Args:
            cylinder_pressure_bar: Cylinder pressure at ignition
            afr: Air-fuel ratio (lean requires more voltage)
            
        Returns:
            Required breakdown voltage in kV
        """
        if self.bridged_gap:
            # Carbon bridge shorts the gap - fires at very low voltage
            return 1.0
        
        # Effective gap
        effective_gap = self.gap_mm + self.electrode_wear_mm
        
        # Base breakdown voltage
        base_kv = BREAKDOWN_VOLTAGE_KV_PER_MM * effective_gap
        
        # Pressure factor (higher pressure needs more voltage)
        pressure_factor = 1 + PRESSURE_FACTOR * cylinder_pressure_bar
        
        # Lean mixture factor (lean needs more voltage)
        lean_factor = 1.0 + max(0, (afr - STOICH_AFR) / STOICH_AFR) * 0.5
        
        # Fouling factor
        fouling_factor = 1.0 + self.fouling_level * 2.0
        
        # Cracked insulator reduces effective voltage (leakage)
        if self.cracked_insulator:
            # Some voltage leaks to ground
            return base_kv * pressure_factor * lean_factor * fouling_factor * 1.5
        
        return base_kv * pressure_factor * lean_factor * fouling_factor
    
    def will_fire(
        self,
        available_voltage_kv: float,
        cylinder_pressure_bar: float,
        afr: float = STOICH_AFR
    ) -> bool:
        """Check if spark will occur."""
        if self.bridged_gap:
            # Always "fires" but with weak/no spark
            return True  # Technically fires, just poorly
        
        required = self.get_required_voltage_kv(cylinder_pressure_bar, afr)
        return available_voltage_kv >= required


@dataclass
class CrankshaftPositionModel:
    """
    Models crankshaft position sensor for misfire detection.
    
    The ECU detects misfires by monitoring crankshaft acceleration
    during each power stroke. A misfire causes less acceleration
    (or deceleration) compared to normal combustion.
    """
    
    # Sensor specs
    teeth_count: int = 58  # Teeth on reluctor wheel (60-2 pattern)
    missing_teeth: int = 2  # Gap for sync
    
    # Measurement
    rpm_variation_threshold: float = 2.0  # % variation to flag misfire
    
    def calculate_rpm_variation(
        self,
        cylinder_torques: List[float],
        base_rpm: float
    ) -> List[float]:
        """
        Calculate RPM variation from combustion torques.
        
        Args:
            cylinder_torques: Torque contribution from each cylinder
            base_rpm: Average engine speed
            
        Returns:
            RPM variation percentage for each cylinder
        """
        if not cylinder_torques:
            return []
        
        avg_torque = sum(cylinder_torques) / len(cylinder_torques)
        if avg_torque <= 0:
            return [0.0] * len(cylinder_torques)
        
        variations = []
        for torque in cylinder_torques:
            # Torque deficit causes RPM drop
            deficit = (avg_torque - torque) / avg_torque
            # Convert to RPM variation (simplified)
            rpm_var = deficit * 5.0  # Empirical scaling
            variations.append(rpm_var)
        
        return variations
    
    def detect_misfires(
        self,
        rpm_variations: List[float]
    ) -> List[bool]:
        """
        Detect which cylinders are misfiring.
        
        Args:
            rpm_variations: RPM variation for each cylinder
            
        Returns:
            Boolean for each cylinder (True = misfire detected)
        """
        return [
            abs(var) > self.rpm_variation_threshold 
            for var in rpm_variations
        ]


# =============================================================================
# STATE DATACLASS
# =============================================================================

@dataclass
class IgnitionSystemState:
    """Snapshot of ignition system state."""
    
    # Per-cylinder states
    spark_energy_mj: List[float] = field(default_factory=list)
    secondary_voltage_kv: List[float] = field(default_factory=list)
    required_voltage_kv: List[float] = field(default_factory=list)
    spark_fired: List[bool] = field(default_factory=list)
    combustion_quality: List[float] = field(default_factory=list)  # 0-1
    
    # Misfire detection
    misfire_detected: List[bool] = field(default_factory=list)
    misfire_count_total: int = 0
    
    # Timing
    base_timing_deg: float = 0
    actual_timing_deg: float = 0
    knock_retard_deg: float = 0
    
    # System health indicators
    coil_primary_current_a: float = 0
    dwell_time_ms: float = 0
    rpm: float = 0


# =============================================================================
# MAIN IGNITION SYSTEM MODEL
# =============================================================================

@dataclass
class IgnitionSystemModel:
    """
    Complete physics-based ignition system model.
    
    This models the ignition process from coil charging to combustion:
    1. ECU commands dwell time based on RPM/load
    2. Coil stores energy during dwell
    3. Primary circuit opens, secondary voltage spikes
    4. If voltage exceeds breakdown, spark occurs
    5. Spark ignites mixture, combustion produces torque
    6. ECU monitors crankshaft for misfire detection
    """
    
    # Component models (one coil per cylinder for COP)
    coils: List[IgnitionCoilModel] = field(default_factory=lambda: [
        IgnitionCoilModel() for _ in range(4)
    ])
    
    spark_plugs: List[SparkPlugModel] = field(default_factory=lambda: [
        SparkPlugModel() for _ in range(4)
    ])
    
    crank_sensor: CrankshaftPositionModel = field(default_factory=CrankshaftPositionModel)
    
    # Engine specs
    num_cylinders: int = 4
    compression_ratio: float = 10.5
    
    # Timing parameters
    base_timing_deg_btdc: float = 10.0  # Base timing
    max_advance_deg: float = 35.0
    
    # Battery voltage
    battery_voltage: float = 14.0
    
    def calculate_dwell_time(self, rpm: float) -> float:
        """
        Calculate optimal dwell time for given RPM.
        
        At higher RPM, less time is available so dwell must be shorter.
        ECU tries to maintain sufficient coil energy.
        
        Args:
            rpm: Engine speed
            
        Returns:
            Dwell time in milliseconds
        """
        if rpm <= 0:
            return 4.0  # Default
        
        # Time per revolution in ms
        ms_per_rev = 60000 / rpm
        
        # Time per firing event (4 cylinder, fires every 180 deg)
        ms_per_fire = ms_per_rev / 2
        
        # Dwell is typically 30-50% of available time
        # At low RPM, cap at 4ms to prevent coil saturation
        # At high RPM, use available time
        dwell = min(4.0, ms_per_fire * 0.4)
        
        return max(1.0, dwell)  # Minimum 1ms
    
    def calculate_spark_advance(
        self,
        rpm: float,
        load_fraction: float,
        coolant_temp_c: float = 90,
        knock_detected: bool = False
    ) -> float:
        """
        Calculate spark timing advance.
        
        Physics:
        - Higher RPM needs more advance (less time for burn)
        - Higher load needs less advance (faster burn, knock risk)
        - Cold engine needs less advance
        
        Args:
            rpm: Engine speed
            load_fraction: Engine load (0-1)
            coolant_temp_c: Coolant temperature
            knock_detected: Whether knock sensor triggered
            
        Returns:
            Spark advance in degrees BTDC
        """
        # Base timing
        advance = self.base_timing_deg_btdc
        
        # RPM-based advance (more advance at higher RPM)
        if rpm > 1000:
            rpm_advance = (rpm - 1000) / 5000 * 20  # Up to 20 deg
            advance += min(rpm_advance, 20)
        
        # Load-based retard (less advance at high load)
        load_retard = load_fraction * 10  # Up to 10 deg retard
        advance -= load_retard
        
        # Cold engine retard
        if coolant_temp_c < 60:
            cold_retard = (60 - coolant_temp_c) / 60 * 5  # Up to 5 deg
            advance -= cold_retard
        
        # Knock retard
        if knock_detected:
            advance -= 5  # Immediate 5 deg retard
        
        # Clamp to safe range
        advance = max(0, min(advance, self.max_advance_deg))
        
        return advance
    
    def calculate_cylinder_pressure(
        self,
        rpm: float,
        load_fraction: float,
        timing_deg_btdc: float
    ) -> float:
        """
        Estimate cylinder pressure at ignition timing.
        
        This is a simplified model - actual pressure depends on
        valve timing, boost, etc.
        
        Args:
            rpm: Engine speed
            load_fraction: Throttle/load
            timing_deg_btdc: When spark fires
            
        Returns:
            Cylinder pressure in bar
        """
        # Atmospheric pressure
        p_atm = 1.0  # bar
        
        # Manifold pressure (higher load = higher pressure)
        # WOT ≈ atmospheric, idle ≈ 0.3 bar
        p_manifold = 0.3 + load_fraction * 0.7
        
        # Compression at ignition timing
        # Simplified: assume spark fires around 70% of compression stroke
        effective_cr = self.compression_ratio * 0.7
        
        # Polytropic compression P2 = P1 × (V1/V2)^n
        # n ≈ 1.3 for air-fuel mixture
        p_cylinder = p_manifold * (effective_cr ** 1.3)
        
        return p_cylinder
    
    def simulate_cycle(
        self,
        rpm: float,
        load_fraction: float,
        afr: float = STOICH_AFR,
        coolant_temp_c: float = 90,
        knock_detected: bool = False
    ) -> IgnitionSystemState:
        """
        Simulate one engine cycle across all cylinders.
        
        Args:
            rpm: Engine speed
            load_fraction: Engine load
            afr: Air-fuel ratio
            coolant_temp_c: Coolant temperature
            knock_detected: Whether knock sensor triggered
            
        Returns:
            IgnitionSystemState with all calculated values
        """
        # Calculate timing and dwell
        dwell_ms = self.calculate_dwell_time(rpm)
        advance_deg = self.calculate_spark_advance(
            rpm, load_fraction, coolant_temp_c, knock_detected
        )
        
        # Calculate cylinder pressure
        cyl_pressure = self.calculate_cylinder_pressure(rpm, load_fraction, advance_deg)
        
        # Per-cylinder calculations
        spark_energies = []
        secondary_voltages = []
        required_voltages = []
        spark_fired_list = []
        combustion_qualities = []
        cylinder_torques = []
        
        for i in range(self.num_cylinders):
            coil = self.coils[i]
            plug = self.spark_plugs[i]
            
            # Coil energy
            energy_mj = coil.get_spark_energy_mj(self.battery_voltage, dwell_ms)
            spark_energies.append(energy_mj)
            
            # Secondary voltage
            voltage_kv = coil.get_secondary_voltage_kv(self.battery_voltage, dwell_ms)
            secondary_voltages.append(voltage_kv)
            
            # Required voltage
            req_voltage = plug.get_required_voltage_kv(cyl_pressure, afr)
            required_voltages.append(req_voltage)
            
            # Did spark fire?
            fired = plug.will_fire(voltage_kv, cyl_pressure, afr)
            spark_fired_list.append(fired)
            
            # Combustion quality (simplified)
            if fired and energy_mj > 10:  # Need minimum energy
                # Quality depends on energy margin and AFR
                energy_margin = energy_mj / 30  # Normalize to typical 30mJ
                afr_factor = 1.0 - abs(afr - STOICH_AFR) / STOICH_AFR * 0.5
                quality = min(1.0, energy_margin * afr_factor)
            else:
                quality = 0.0  # Misfire
            
            combustion_qualities.append(quality)
            
            # Torque contribution (for misfire detection)
            # Normal torque = 1.0, misfire = 0
            cylinder_torques.append(quality)
        
        # Misfire detection
        rpm_variations = self.crank_sensor.calculate_rpm_variation(cylinder_torques, rpm)
        misfires = self.crank_sensor.detect_misfires(rpm_variations)
        misfire_count = sum(1 for m in misfires if m)
        
        # Primary current (from first coil, representative)
        primary_current = self.coils[0].get_dwell_current(self.battery_voltage, dwell_ms)
        
        return IgnitionSystemState(
            spark_energy_mj=spark_energies,
            secondary_voltage_kv=secondary_voltages,
            required_voltage_kv=required_voltages,
            spark_fired=spark_fired_list,
            combustion_quality=combustion_qualities,
            misfire_detected=misfires,
            misfire_count_total=misfire_count,
            base_timing_deg=self.base_timing_deg_btdc,
            actual_timing_deg=advance_deg,
            knock_retard_deg=5.0 if knock_detected else 0.0,
            coil_primary_current_a=primary_current,
            dwell_time_ms=dwell_ms,
            rpm=rpm
        )
    
    def inject_fault(
        self,
        fault_id: str,
        severity: float = 1.0,
        cylinder: int = None
    ) -> None:
        """
        Inject a specific fault into the model.
        
        Args:
            fault_id: Identifier for the fault
            severity: 0-1 severity
            cylinder: Which cylinder (0-based) for cylinder-specific faults
        """
        cyl = cylinder if cylinder is not None else 0
        
        fault_map = {
            # Coil faults
            "coil_failed": lambda: setattr(self.coils[cyl], 'failed_open', True),
            "coil_weak": lambda: (
                setattr(self.coils[cyl], 'weak', True),
                setattr(self.coils[cyl], 'weak_factor', 1 - severity * 0.5)
            ),
            "coil_intermittent": lambda: (
                setattr(self.coils[cyl], 'intermittent', True),
                setattr(self.coils[cyl], 'intermittent_failure_rate', severity * 0.3)
            ),
            "coil_shorted_turns": lambda: (
                setattr(self.coils[cyl], 'shorted_turns', severity * 0.3)
            ),
            
            # Spark plug faults
            "plug_fouled": lambda: (
                setattr(self.spark_plugs[cyl], 'fouling_level', severity)
            ),
            "plug_worn": lambda: (
                setattr(self.spark_plugs[cyl], 'electrode_wear_mm', severity * 0.5)
            ),
            "plug_cracked": lambda: (
                setattr(self.spark_plugs[cyl], 'cracked_insulator', True)
            ),
            "plug_bridged": lambda: (
                setattr(self.spark_plugs[cyl], 'bridged_gap', True)
            ),
            
            # System-wide faults
            "low_battery_voltage": lambda: (
                setattr(self, 'battery_voltage', 14.0 - severity * 4.0)  # Down to 10V
            ),
            "timing_sensor_drift": lambda: (
                setattr(self, 'base_timing_deg_btdc', 
                       self.base_timing_deg_btdc + severity * 10)  # Up to 10 deg drift
            ),
            
            # All cylinders
            "all_coils_weak": lambda: [
                (setattr(c, 'weak', True), setattr(c, 'weak_factor', 1 - severity * 0.3))
                for c in self.coils
            ],
            "all_plugs_fouled": lambda: [
                setattr(p, 'fouling_level', severity * 0.7)
                for p in self.spark_plugs
            ],
        }
        
        if fault_id in fault_map:
            fault_map[fault_id]()
        else:
            raise ValueError(f"Unknown fault: {fault_id}")
    
    def reset(self) -> None:
        """Reset all components to healthy state."""
        self.coils = [IgnitionCoilModel() for _ in range(self.num_cylinders)]
        self.spark_plugs = [SparkPlugModel() for _ in range(self.num_cylinders)]
        self.battery_voltage = 14.0
        self.base_timing_deg_btdc = 10.0


# =============================================================================
# DIAGNOSTIC SIGNATURES
# =============================================================================

def get_ignition_fault_signatures() -> Dict[str, Dict]:
    """
    Return diagnostic signatures for ignition system faults.
    
    Each signature describes:
    - What observables are affected
    - Expected direction of change
    - Which cylinder(s) affected
    """
    return {
        "coil_failed": {
            "description": "Ignition coil open circuit - no spark",
            "observables": {
                "spark_fired": "false (affected cylinder)",
                "misfire_detected": "true (affected cylinder)",
                "combustion_quality": "0 (affected cylinder)",
            },
            "dtcs": ["P0351-P0358 (coil circuit)", "P0300-P0304 (misfire)"],
            "symptoms": ["Rough idle", "Loss of power", "Check engine light"],
        },
        "coil_weak": {
            "description": "Weak coil - insufficient spark energy",
            "observables": {
                "spark_energy_mj": "low (affected cylinder)",
                "secondary_voltage_kv": "low",
                "misfire_detected": "intermittent at high load",
            },
            "dtcs": ["P0300-P0304 (random misfire)"],
            "symptoms": ["Misfire under load", "Hesitation during acceleration"],
        },
        "plug_fouled": {
            "description": "Fouled spark plug - requires higher voltage",
            "observables": {
                "required_voltage_kv": "high (affected cylinder)",
                "misfire_detected": "possible at low load/idle",
            },
            "dtcs": ["P0300-P0304 (misfire)"],
            "symptoms": ["Hard starting", "Rough idle", "Black exhaust smoke"],
        },
        "plug_worn": {
            "description": "Worn electrodes - increased gap",
            "observables": {
                "required_voltage_kv": "high (wider gap)",
                "misfire_detected": "possible at high RPM/load",
            },
            "dtcs": ["P0300-P0304 (misfire)"],
            "symptoms": ["Misfire at WOT", "Reduced fuel economy"],
        },
        "low_battery_voltage": {
            "description": "Low system voltage - weak spark all cylinders",
            "observables": {
                "spark_energy_mj": "low (all cylinders)",
                "secondary_voltage_kv": "low (all cylinders)",
                "coil_primary_current_a": "low",
            },
            "dtcs": ["P0300 (random misfire)", "Battery/charging codes"],
            "symptoms": ["Hard starting", "Random misfires", "Dim lights"],
        },
    }
