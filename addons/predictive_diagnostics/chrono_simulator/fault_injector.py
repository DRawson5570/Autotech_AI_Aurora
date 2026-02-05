"""
Fault Injection Layer for PyChrono Vehicle Simulation

This module maps diagnostic failure modes (from knowledge/failures_*.py)
to PyChrono simulation modifications.

The approach:
1. FailureMode defines WHAT fails (e.g., "vacuum_leak")
2. FaultInjector defines HOW to simulate it in Chrono
3. BatchGenerator creates 1000s of labeled training examples
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional
from enum import Enum
import random


class FaultType(Enum):
    """Categories of fault injection methods."""
    TORQUE_REDUCTION = "torque_reduction"      # Engine power loss
    TORQUE_FLUCTUATION = "torque_fluctuation"  # Misfire, rough running
    THROTTLE_STUCK = "throttle_stuck"          # Actuator fault
    THROTTLE_DELAYED = "throttle_delayed"      # Response delay
    TIRE_FRICTION = "tire_friction"            # Worn/wet tires
    BRAKE_REDUCTION = "brake_reduction"        # Brake fade/wear
    SENSOR_DRIFT = "sensor_drift"              # Post-process sensor readings
    SENSOR_NOISE = "sensor_noise"              # Add noise to readings
    TRANSMISSION_SLIP = "transmission_slip"    # Torque loss in trans


@dataclass
class FaultInjection:
    """Defines how to inject a specific fault into Chrono simulation."""
    
    fault_type: FaultType
    
    # Parameters for the injection
    magnitude: float = 0.0          # Severity (0-1)
    variation: float = 0.1          # Random variation in magnitude
    
    # For time-varying faults
    onset_time: float = 0.0         # When fault starts (seconds)
    ramp_time: float = 0.0          # Time to reach full magnitude
    
    # For intermittent faults
    intermittent: bool = False
    duty_cycle: float = 1.0         # Fraction of time fault is active
    
    # For pattern-based faults (e.g., misfire)
    pattern: Optional[List[float]] = None  # Multipliers per cycle


@dataclass
class FailureSimulation:
    """Maps a diagnostic FailureMode to Chrono simulation parameters."""
    
    # Reference to diagnostic failure mode
    failure_mode_id: str            # e.g., "fuel.vacuum_leak"
    failure_mode_name: str          # e.g., "Vacuum Leak"
    
    # Chrono fault injections to apply
    injections: List[FaultInjection] = field(default_factory=list)
    
    # Sensor post-processing (simulate sensor effects)
    sensor_biases: Dict[str, float] = field(default_factory=dict)  # pid -> bias
    sensor_noise: Dict[str, float] = field(default_factory=dict)   # pid -> noise std
    
    # Expected PID patterns (for validation)
    expected_patterns: Dict[str, str] = field(default_factory=dict)  # pid -> "high"/"low"/etc
    
    # Scenario variations to generate
    severity_range: tuple = (0.1, 0.9)  # Min/max severity
    n_variations: int = 100             # How many scenarios per failure


# =============================================================================
# FAILURE MODE -> SIMULATION MAPPINGS
# =============================================================================

FAILURE_SIMULATIONS: Dict[str, FailureSimulation] = {}


def register_simulation(sim: FailureSimulation) -> None:
    """Register a failure simulation mapping."""
    FAILURE_SIMULATIONS[sim.failure_mode_id] = sim


# -----------------------------------------------------------------------------
# FUEL SYSTEM FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="fuel.vacuum_leak",
    failure_mode_name="Vacuum Leak",
    injections=[
        # Vacuum leak causes unmetered air -> lean condition -> ECU adds fuel
        # Simulate as slight power loss (lean mixture = less power)
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.10,  # 10% torque loss at full severity
            variation=0.03,
        ),
    ],
    # Post-process to simulate fuel trim compensation
    sensor_biases={
        "stft_b1": 0.12,      # +12% short term fuel trim (adding fuel)
        "stft_b2": 0.10,      # Slightly less on bank 2
        "ltft_b1": 0.08,      # Long term adapts
    },
    expected_patterns={
        "stft_b1": "high",
        "ltft_b1": "high",
        "rpm": "erratic",     # May have rough idle
    },
    severity_range=(0.05, 0.25),  # 5-25% severity
    n_variations=200,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.weak_fuel_pump",
    failure_mode_name="Weak Fuel Pump",
    injections=[
        # Weak pump = insufficient fuel under load = power loss under load
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.20,  # 20% loss under high load
            variation=0.05,
        ),
    ],
    sensor_biases={
        "fuel_pressure": -0.15,  # Low fuel pressure
    },
    expected_patterns={
        "fuel_pressure": "low",
        "stft_b1": "high",  # Lean at WOT
    },
    n_variations=150,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.clogged_injector",
    failure_mode_name="Clogged Fuel Injector",
    injections=[
        # One cylinder running lean = power loss + rough running
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.25,  # Cylinder contribution lost periodically
            pattern=[1.0, 1.0, 1.0, 0.75],  # Every 4th cycle affected
        ),
    ],
    sensor_biases={
        "stft_b1": 0.08,  # Moderate positive STFT
    },
    expected_patterns={
        "rpm": "fluctuating",
        "stft_b1": "high",
    },
    n_variations=100,
))


# -----------------------------------------------------------------------------
# IGNITION SYSTEM FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="ignition.misfire_cylinder",
    failure_mode_name="Cylinder Misfire",
    injections=[
        # Misfire = no combustion in one cylinder
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.30,  # 30% torque drop on affected cycle
            pattern=[1.0, 1.0, 1.0, 0.0],  # Complete miss every 4th (4-cyl)
            variation=0.05,
        ),
    ],
    sensor_biases={
        "stft_b1": 0.05,  # Slight positive (unburned fuel)
    },
    expected_patterns={
        "rpm": "fluctuating",
        "engine_load": "erratic",
    },
    n_variations=200,
))

register_simulation(FailureSimulation(
    failure_mode_id="ignition.weak_spark",
    failure_mode_name="Weak Spark (Worn Plugs/Coils)",
    injections=[
        # Weak spark = incomplete combustion = reduced power
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.15,
            variation=0.05,
        ),
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.08,
            intermittent=True,
            duty_cycle=0.7,  # Random misfires 30% of time
        ),
    ],
    expected_patterns={
        "rpm": "slightly_erratic",
        "acceleration": "sluggish",
    },
    n_variations=150,
))


# -----------------------------------------------------------------------------
# COOLING SYSTEM FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="cooling.thermostat_stuck_open",
    failure_mode_name="Thermostat Stuck Open",
    injections=[
        # No direct torque effect, but ECU runs rich when cold
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.05,  # Slight power loss from rich running
        ),
    ],
    sensor_biases={
        "coolant_temp": -30,  # Stays 30°F below normal
        "stft_b1": 0.08,      # Running rich (cold enrichment)
    },
    expected_patterns={
        "coolant_temp": "low",
        "warmup_time": "long",
        "stft_b1": "high",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="cooling.thermostat_stuck_closed",
    failure_mode_name="Thermostat Stuck Closed",
    injections=[
        # Overheating causes ECU to retard timing = power loss
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.20,
            onset_time=60.0,   # Builds up over time
            ramp_time=120.0,   # Takes 2 min to reach full severity
        ),
    ],
    sensor_biases={
        "coolant_temp": 40,  # Runs 40°F over normal
    },
    expected_patterns={
        "coolant_temp": "high",
        "timing_advance": "low",  # ECU retards timing
    },
    n_variations=100,
))


# -----------------------------------------------------------------------------
# TIRE/SUSPENSION FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="tires.worn_tires",
    failure_mode_name="Worn Tires (Low Tread)",
    injections=[
        FaultInjection(
            fault_type=FaultType.TIRE_FRICTION,
            magnitude=0.3,  # 30% friction reduction
            variation=0.1,
        ),
    ],
    # Worn tires show as wheel speed sensor variance (traction events)
    sensor_biases={
        "wheel_slip_events": 5.0,       # TCS activations per 100 samples
        "tire_wear_index": 0.7,         # 0=new, 1=bald (computed from slip)
    },
    sensor_noise={
        "speed_kmh": 2.0,               # More speed variation from slip
    },
    expected_patterns={
        "wheel_slip": "high",
        "traction_control": "active",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="tires.low_pressure",
    failure_mode_name="Low Tire Pressure",
    injections=[
        # Low pressure = increased rolling resistance = fuel economy hit
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.05,  # Slight resistance increase
        ),
    ],
    sensor_biases={
        "tire_pressure": -10,  # 10 PSI low
    },
    expected_patterns={
        "tire_pressure": "low",
        "fuel_economy": "poor",
    },
    n_variations=50,
))


# -----------------------------------------------------------------------------
# BRAKE FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="brakes.brake_fade",
    failure_mode_name="Brake Fade (Overheated)",
    injections=[
        FaultInjection(
            fault_type=FaultType.BRAKE_REDUCTION,
            magnitude=0.4,  # 40% brake effectiveness loss
            onset_time=30.0,  # After sustained braking
        ),
    ],
    # Brake fade = overheating = high brake temps, longer decel times
    sensor_biases={
        "brake_temp": 150.0,            # Elevated brake temp (degrees over normal)
        "decel_rate": -0.3,             # Reduced deceleration capability (g)
        "brake_pedal_travel": 0.2,      # More pedal travel needed
    },
    expected_patterns={
        "brake_effectiveness": "reduced",
        "stopping_distance": "increased",
    },
    n_variations=75,
))


# -----------------------------------------------------------------------------
# TRANSMISSION FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="transmission.slipping",
    failure_mode_name="Transmission Slipping",
    injections=[
        FaultInjection(
            fault_type=FaultType.TRANSMISSION_SLIP,
            magnitude=0.15,  # 15% torque loss in trans
            intermittent=True,
            duty_cycle=0.8,
        ),
    ],
    # Trans slip = RPM/speed mismatch, ATF temp rise, erratic shifting
    sensor_biases={
        "trans_slip_ratio": 0.15,       # RPM vs expected ratio mismatch
        "trans_temp": 30.0,             # ATF running hotter (degrees)
        "shift_quality": -0.4,          # Harsh/delayed shifts (-1 to 1 scale)
    },
    sensor_noise={
        "rpm": 100.0,                   # RPM hunting/flare during shifts
    },
    expected_patterns={
        "rpm": "high_for_speed",  # RPM climbs but speed doesn't
        "trans_slip": "detected",
    },
    n_variations=100,
))


# -----------------------------------------------------------------------------
# OXYGEN SENSOR FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="fuel.o2_sensor_lazy",
    failure_mode_name="Lazy O2 Sensor (Slow Response)",
    injections=[
        # Lazy O2 = ECU fuel trims over/undershoot before correcting
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.05,
            intermittent=True,
            duty_cycle=0.9,
        ),
    ],
    sensor_biases={
        "o2_b1s1_response_time": 0.5,   # Slow voltage transitions
        "stft_b1": 0.05,                # Slight positive (overshooting)
        "fuel_economy": -0.08,          # Worse fuel economy
    },
    sensor_noise={
        "stft_b1": 3.0,                 # STFT hunting
    },
    expected_patterns={
        "o2_voltage": "slow_oscillation",
        "stft_b1": "hunting",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.o2_sensor_stuck_lean",
    failure_mode_name="O2 Sensor Stuck Lean",
    injections=[
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.08,  # Rich running = slight power loss
        ),
    ],
    sensor_biases={
        "o2_b1s1": -0.3,                # Stuck low voltage (lean signal)
        "ltft_b1": -0.15,               # ECU adding fuel constantly
        "stft_b1": -0.10,
        "fuel_economy": -0.12,          # Running rich
    },
    expected_patterns={
        "o2_voltage": "stuck_low",
        "ltft_b1": "negative",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.o2_sensor_stuck_rich",
    failure_mode_name="O2 Sensor Stuck Rich",
    injections=[
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.10,  # Lean running = power loss
        ),
    ],
    sensor_biases={
        "o2_b1s1": 0.4,                 # Stuck high voltage (rich signal)
        "ltft_b1": 0.18,                # ECU removing fuel constantly
        "stft_b1": 0.12,
    },
    expected_patterns={
        "o2_voltage": "stuck_high",
        "ltft_b1": "positive",
        "engine_knock": "possible",
    },
    n_variations=80,
))


# -----------------------------------------------------------------------------
# EGR FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="emissions.egr_stuck_open",
    failure_mode_name="EGR Valve Stuck Open",
    injections=[
        # Stuck open EGR = diluted intake = rough idle, power loss
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.15,
            variation=0.05,
        ),
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.10,
            intermittent=True,
            duty_cycle=0.7,
        ),
    ],
    sensor_biases={
        "egr_flow": 0.25,               # EGR flowing at idle (bad)
        "rpm_deviation": -100,          # Rough/low idle
        "stft_b1": 0.06,                # Lean due to dilution
    },
    expected_patterns={
        "idle": "rough",
        "egr_flow": "high_at_idle",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="emissions.egr_stuck_closed",
    failure_mode_name="EGR Valve Stuck Closed",
    injections=[
        # Stuck closed = higher NOx, possible knock under load
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "egr_flow": -0.20,              # No EGR flow under load
        "knock_retard": 3.0,            # ECU retarding timing (degrees)
        "nox_emissions": 0.30,          # Higher NOx
    },
    expected_patterns={
        "egr_flow": "low_at_cruise",
        "timing_retard": "active",
    },
    n_variations=80,
))


# -----------------------------------------------------------------------------
# CATALYTIC CONVERTER FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="emissions.cat_efficiency_low",
    failure_mode_name="Catalytic Converter Degraded",
    injections=[
        # Degraded cat = no torque effect, but O2 sensors show issue
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "o2_b1s2": 0.15,                # Downstream O2 mimicking upstream
        "cat_efficiency": -0.30,        # Reduced conversion efficiency
    },
    expected_patterns={
        "o2_b1s2": "mirroring_upstream",
        "cat_monitor": "incomplete",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="emissions.cat_clogged",
    failure_mode_name="Catalytic Converter Clogged/Restricted",
    injections=[
        # Clogged cat = exhaust backpressure = significant power loss
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.30,
            onset_time=10.0,  # Gets worse as RPM increases
        ),
    ],
    sensor_biases={
        "exhaust_backpressure": 15.0,   # PSI above normal
        "cat_temp": 100.0,              # Running hot
    },
    expected_patterns={
        "power_at_wot": "reduced",
        "exhaust_smell": "sulfur",
    },
    n_variations=75,
))


# -----------------------------------------------------------------------------
# MAF/MAP SENSOR FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="fuel.maf_contaminated",
    failure_mode_name="MAF Sensor Contaminated/Dirty",
    injections=[
        # Dirty MAF reads low = ECU delivers less fuel = lean
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.10,
        ),
    ],
    sensor_biases={
        "maf": -0.15,                   # Reading 15% low
        "ltft_b1": 0.12,                # ECU adding fuel to compensate
        "ltft_b2": 0.10,
    },
    expected_patterns={
        "maf": "low_for_rpm",
        "ltft": "positive_both_banks",
    },
    n_variations=150,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.map_sensor_drift",
    failure_mode_name="MAP Sensor Drift",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "map": 8.0,                     # Reading high (kPa)
        "ltft_b1": -0.08,               # ECU removing fuel (thinks load higher)
    },
    expected_patterns={
        "map": "high_at_idle",
        "calculated_load": "inconsistent",
    },
    n_variations=75,
))


# -----------------------------------------------------------------------------
# KNOCK SENSOR FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="ignition.knock_sensor_failed",
    failure_mode_name="Knock Sensor Failed",
    injections=[
        # Failed KS = ECU can't detect knock = potential engine damage
        # ECU may run extra timing retard as safety
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.08,  # Conservative timing
        ),
    ],
    sensor_biases={
        "knock_sensor_signal": 0.0,     # No signal
        "timing_advance": -5.0,         # Retarded for safety
    },
    expected_patterns={
        "knock_signal": "absent",
        "timing": "retarded",
    },
    n_variations=50,
))


# -----------------------------------------------------------------------------
# EVAP SYSTEM FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="emissions.evap_leak_small",
    failure_mode_name="Small EVAP Leak",
    injections=[
        # Small leak = no drivability issues, just emissions
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.3,
        ),
    ],
    sensor_biases={
        "evap_system_pressure": -0.5,   # Can't hold vacuum
        "evap_leak_size": 0.020,        # ~0.020" leak
    },
    expected_patterns={
        "evap_monitor": "incomplete",
        "fuel_cap": "check",
    },
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="emissions.evap_purge_stuck_open",
    failure_mode_name="EVAP Purge Valve Stuck Open",
    injections=[
        # Stuck open = fuel vapors at idle = rich condition
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.05,
            intermittent=True,
            duty_cycle=0.9,
        ),
    ],
    sensor_biases={
        "stft_b1": -0.08,               # Running rich at idle
        "rpm_deviation": 50,            # Slightly high idle
    },
    expected_patterns={
        "idle": "high",
        "stft_at_idle": "negative",
    },
    n_variations=60,
))


# -----------------------------------------------------------------------------
# EXHAUST LEAK FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="exhaust.pre_cat_leak",
    failure_mode_name="Exhaust Leak (Pre-Cat)",
    injections=[
        # Exhaust leak before O2 sensor = false lean reading
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.03,  # Minimal power effect
        ),
    ],
    sensor_biases={
        "o2_b1s1": -0.2,                # False lean from air ingestion
        "stft_b1": -0.10,               # ECU adds fuel (incorrectly)
        "ltft_b1": -0.08,
    },
    expected_patterns={
        "o2_voltage": "erratic_lean",
        "ltft": "negative",
        "exhaust_noise": "ticking_cold",
    },
    n_variations=80,
))


# -----------------------------------------------------------------------------
# COMPRESSION/MECHANICAL FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="engine.low_compression_cylinder",
    failure_mode_name="Low Compression (One Cylinder)",
    injections=[
        # One weak cylinder = misfire + power loss
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.20,
            pattern=[1.0, 1.0, 1.0, 0.80],  # 4-cyl with weak #4
        ),
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.08,
        ),
    ],
    sensor_biases={
        "misfire_count_cyl4": 5.0,      # Misfires on weak cylinder
        "compression_variance": 0.20,    # 20% variance in compression
    },
    expected_patterns={
        "misfire": "single_cylinder",
        "power": "reduced",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="engine.valve_seat_recession",
    failure_mode_name="Valve Seat Recession",
    injections=[
        # Valve not sealing = compression loss + misfire at idle
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.15,
            intermittent=True,
            duty_cycle=0.85,
        ),
    ],
    sensor_biases={
        "idle_rpm_variance": 50.0,      # Rough idle
        "vacuum_at_idle": -3.0,         # Low vacuum (inHg)
    },
    expected_patterns={
        "idle": "rough",
        "vacuum": "low",
    },
    n_variations=60,
))


# -----------------------------------------------------------------------------
# AIR INTAKE FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="fuel.air_filter_clogged",
    failure_mode_name="Air Filter Severely Clogged",
    injections=[
        # Restricted intake = reduced airflow = power loss
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.15,
            onset_time=0.0,
        ),
    ],
    sensor_biases={
        "maf": -0.10,                   # Reduced airflow
        "map": 5.0,                     # Higher manifold vacuum
        "ltft_b1": -0.05,               # Slightly rich
    },
    expected_patterns={
        "power_at_wot": "reduced",
        "throttle_response": "sluggish",
    },
    n_variations=75,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.intake_gasket_leak",
    failure_mode_name="Intake Manifold Gasket Leak",
    injections=[
        # Unmetered air leak = lean condition
        FaultInjection(
            fault_type=FaultType.TORQUE_FLUCTUATION,
            magnitude=0.08,
            intermittent=True,
            duty_cycle=0.9,
        ),
    ],
    sensor_biases={
        "stft_b1": 0.15,                # High positive fuel trim
        "ltft_b1": 0.10,
        "idle_rpm_variance": 30.0,      # Rough idle
    },
    expected_patterns={
        "ltft": "positive_both_banks",
        "idle": "rough",
    },
    n_variations=100,
))


# -----------------------------------------------------------------------------
# PCV SYSTEM FAILURES
# -----------------------------------------------------------------------------

register_simulation(FailureSimulation(
    failure_mode_id="emissions.pcv_stuck_open",
    failure_mode_name="PCV Valve Stuck Open",
    injections=[
        # Stuck open = excessive crankcase vacuum = oil consumption
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "crankcase_vacuum": -5.0,       # Excessive vacuum (inHg)
        "oil_consumption": 0.3,         # Quart per 1000 miles
        "stft_b1": 0.05,                # Slight lean
    },
    expected_patterns={
        "oil_level": "drops_fast",
        "idle": "slightly_rough",
    },
    n_variations=50,
))


# =============================================================================
# STEERING SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="steering.power_steering_pump_failing",
    failure_mode_name="Power Steering Pump Failing",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "steering_effort": 3.5,          # Increased effort (lbf)
        "ps_pump_pressure": -25.0,       # Low pressure (PSI)
        "ps_fluid_temp": 30.0,           # Running hot
        "steering_assist": -0.40,        # Reduced assist
    },
    sensor_noise={
        "steering_effort": 0.5,          # Intermittent heaviness
    },
    expected_patterns={
        "steering": "heavy_at_low_speed",
        "noise": "whining_on_turn",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="steering.rack_leak",
    failure_mode_name="Steering Rack Leak",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "ps_fluid_level": -0.25,         # Low fluid
        "steering_effort": 1.5,          # Slightly heavier
        "ps_pump_pressure": -10.0,       # Reduced pressure
    },
    expected_patterns={
        "fluid_level": "dropping",
        "puddle": "under_front",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="steering.tie_rod_worn",
    failure_mode_name="Worn Tie Rod End",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "steering_play": 0.5,            # Degrees of play
        "toe_angle": 0.8,                # Alignment off (degrees)
        "tire_wear_inner": 0.3,          # Inner edge wear
    },
    sensor_noise={
        "steering_angle": 1.0,           # Wandering
    },
    expected_patterns={
        "steering": "loose_feel",
        "tire_wear": "inner_edge",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="steering.alignment_out",
    failure_mode_name="Wheel Alignment Out of Spec",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.3,
        ),
    ],
    sensor_biases={
        "camber_angle": 1.2,             # Out of spec (degrees)
        "toe_angle": 0.6,                # Toe out
        "steering_wheel_offset": 5.0,    # Degrees off center
        "tire_wear_edge": 0.25,          # Edge wear
    },
    expected_patterns={
        "pull": "to_one_side",
        "tire_wear": "uneven",
    },
    n_variations=120,
))


# =============================================================================
# SUSPENSION SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="suspension.shock_worn",
    failure_mode_name="Worn Shock Absorber",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "suspension_oscillation": 0.4,   # Extra bounce cycles
        "body_roll": 0.15,               # Increased roll (degrees)
        "nose_dive": 0.20,               # Increased dive on braking
        "ride_height_variance": 0.5,     # Uneven ride height (inches)
    },
    expected_patterns={
        "ride": "bouncy",
        "braking": "nose_dive_excessive",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="suspension.strut_mount_failed",
    failure_mode_name="Failed Strut Mount",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "strut_noise_level": 0.7,        # Clunking on bumps
        "steering_feel": -0.3,           # Vague steering
        "alignment_drift": 0.5,          # Alignment changes
    },
    sensor_noise={
        "suspension_position": 0.3,      # Erratic readings
    },
    expected_patterns={
        "noise": "clunk_over_bumps",
        "steering": "vague",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="suspension.ball_joint_worn",
    failure_mode_name="Worn Ball Joint",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "suspension_play": 0.15,         # Inches of play
        "camber_variance": 0.8,          # Changes with load
        "tire_wear_edge": 0.3,           # Edge wear
        "clunk_frequency": 0.6,          # Noise over bumps
    },
    expected_patterns={
        "noise": "clunk_on_bumps",
        "tire_wear": "edge",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="suspension.sway_bar_link_broken",
    failure_mode_name="Broken Sway Bar Link",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "body_roll": 0.25,               # Increased roll in corners
        "sway_bar_noise": 0.8,           # Rattling/clunking
        "cornering_stability": -0.2,     # Reduced stability
    },
    expected_patterns={
        "noise": "rattle_over_bumps",
        "handling": "body_roll_excessive",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="suspension.spring_broken",
    failure_mode_name="Broken Coil Spring",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "ride_height_fl": -1.5,          # Corner dropped (inches)
        "alignment_camber": 2.0,         # Severe camber change
        "tire_wear_severe": 0.5,         # Rapid edge wear
    },
    expected_patterns={
        "visual": "corner_sagging",
        "handling": "pulls_to_side",
    },
    n_variations=60,
))


# =============================================================================
# HVAC SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="hvac.ac_compressor_failing",
    failure_mode_name="AC Compressor Failing",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "ac_pressure_high": -40.0,       # Low high-side pressure (PSI)
        "ac_pressure_low": 15.0,         # High low-side pressure
        "cabin_temp_delta": 15.0,        # Not cooling well (°F above target)
        "ac_clutch_cycling": 0.4,        # Excessive cycling
    },
    sensor_noise={
        "ac_pressure_high": 8.0,         # Fluctuating pressure
    },
    expected_patterns={
        "cooling": "inadequate",
        "noise": "compressor_grinding",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="hvac.refrigerant_low",
    failure_mode_name="Low Refrigerant Level",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "ac_pressure_high": -50.0,       # Very low high-side (PSI)
        "ac_pressure_low": -10.0,        # Low low-side
        "ac_superheat": 20.0,            # High superheat (°F)
        "cabin_temp_delta": 20.0,        # Poor cooling
    },
    expected_patterns={
        "cooling": "weak",
        "ice_on_lines": "possible",
    },
    n_variations=120,
))

register_simulation(FailureSimulation(
    failure_mode_id="hvac.blend_door_stuck",
    failure_mode_name="Blend Door Actuator Stuck",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "blend_door_position": 0.0,      # Stuck position
        "blend_door_commanded": 0.7,     # Different from actual
        "cabin_temp_error": 15.0,        # Can't reach target (°F)
    },
    expected_patterns={
        "temp_control": "no_response",
        "noise": "clicking_behind_dash",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="hvac.blower_motor_failing",
    failure_mode_name="Blower Motor Failing",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "blower_speed_actual": -0.30,    # Running slow
        "blower_current": 0.5,           # Drawing extra current (A)
        "airflow_volume": -0.35,         # Reduced airflow
    },
    sensor_noise={
        "blower_speed_actual": 0.1,      # Intermittent
    },
    expected_patterns={
        "airflow": "weak_or_intermittent",
        "noise": "squealing_or_grinding",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="hvac.heater_core_clogged",
    failure_mode_name="Clogged Heater Core",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "heater_inlet_temp": 190.0,      # Hot going in (°F)
        "heater_outlet_temp": 120.0,     # Cooler coming out
        "cabin_heat_output": -0.50,      # Reduced heat
    },
    expected_patterns={
        "heat": "inadequate",
        "coolant_smell": "possible",
    },
    n_variations=60,
))


# =============================================================================
# ABS SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="abs.wheel_speed_sensor_failed",
    failure_mode_name="ABS Wheel Speed Sensor Failed",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.8,
        ),
    ],
    sensor_biases={
        "wss_fl": 0.0,                   # No signal from FL
        "wss_variance": 100.0,           # Huge variance vs others
        "abs_activation_false": 1.0,     # Spurious ABS activation
        "abs_lamp": 1.0,                 # ABS light on
    },
    expected_patterns={
        "abs_light": "on",
        "abs_function": "disabled",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="abs.pump_motor_weak",
    failure_mode_name="ABS Pump Motor Weak",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "abs_pump_pressure": -0.25,      # Can't build full pressure
        "abs_pump_current": 0.8,         # Drawing extra current (A)
        "abs_response_time": 0.3,        # Delayed response (s)
        "abs_lamp": 1.0,
    },
    expected_patterns={
        "abs_light": "on",
        "braking_abs": "weak_or_delayed",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="abs.module_communication",
    failure_mode_name="ABS Module Communication Error",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "can_bus_errors_abs": 5.0,       # Communication errors
        "abs_lamp": 1.0,
        "traction_lamp": 1.0,            # TCS also disabled
        "stability_lamp": 1.0,           # ESC also disabled
    },
    expected_patterns={
        "multiple_lights": "abs_tcs_esc",
        "function": "all_disabled",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="abs.tone_ring_damaged",
    failure_mode_name="ABS Tone Ring Damaged",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "wss_rr_variance": 0.15,         # Erratic signal
        "wss_rr_dropouts": 3.0,          # Signal dropouts per second
        "abs_lamp": 1.0,
    },
    sensor_noise={
        "wss_rr": 5.0,                   # Noisy signal
    },
    expected_patterns={
        "abs_light": "intermittent_or_on",
        "wss_signal": "erratic",
    },
    n_variations=80,
))


# =============================================================================
# AIRBAG/SRS SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="airbag.clock_spring_broken",
    failure_mode_name="Clock Spring Broken",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.8,
        ),
    ],
    sensor_biases={
        "airbag_lamp": 1.0,              # SRS light on
        "driver_airbag_resistance": 999.0,  # Open circuit (ohms)
        "horn_function": 0.0,            # Horn doesn't work
        "cruise_buttons": 0.0,           # Steering wheel buttons dead
    },
    expected_patterns={
        "airbag_light": "on",
        "horn": "not_working",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="airbag.seat_sensor_failed",
    failure_mode_name="Seat Occupant Sensor Failed",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "airbag_lamp": 1.0,
        "seat_occupancy_detected": 0.0,  # Can't detect passenger
        "passenger_airbag_status": 0.0,  # Shows "off"
    },
    expected_patterns={
        "airbag_light": "on",
        "passenger_airbag": "disabled",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="airbag.srs_module_fault",
    failure_mode_name="SRS Control Module Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.9,
        ),
    ],
    sensor_biases={
        "airbag_lamp": 1.0,
        "srs_dtc_count": 3.0,            # Multiple codes stored
        "srs_readiness": 0.0,            # System not ready
        "can_bus_errors_srs": 2.0,
    },
    expected_patterns={
        "airbag_light": "on_solid",
        "all_airbags": "status_unknown",
    },
    n_variations=60,
))


# =============================================================================
# LIGHTING SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="lighting.headlight_out",
    failure_mode_name="Headlight Bulb Out",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "headlight_fl_current": 0.0,     # No current draw (A)
        "headlight_fl_status": 0.0,      # Bulb out
        "lighting_dtc": 1.0,             # DTC stored
    },
    expected_patterns={
        "headlight": "one_out",
        "dash_indicator": "possible",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="lighting.ballast_failed",
    failure_mode_name="HID Ballast Failed",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "hid_ballast_output": 0.0,       # No output voltage
        "headlight_fr_status": 0.0,      # Light out
        "hid_igniter_attempts": 5.0,     # Repeated ignition attempts
    },
    sensor_noise={
        "hid_ballast_output": 10.0,      # Flickering before failure
    },
    expected_patterns={
        "headlight": "flickering_or_out",
        "color": "pink_before_failure",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="lighting.turn_signal_fast",
    failure_mode_name="Turn Signal Fast Flash (Bulb Out)",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "turn_signal_frequency": 2.0,    # Fast flash (Hz vs normal 1 Hz)
        "turn_signal_rr_current": 0.0,   # Rear bulb out
        "turn_signal_load": -0.50,       # Half normal load
    },
    expected_patterns={
        "turn_signal": "fast_flash",
        "bulb": "rear_out",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="lighting.bcm_lighting_fault",
    failure_mode_name="BCM Lighting Control Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "bcm_lighting_status": 0.0,      # Module fault
        "auto_headlight_function": 0.0,  # Auto lights not working
        "daytime_running_lights": 0.0,   # DRL fault
        "can_bus_errors_bcm": 3.0,
    },
    expected_patterns={
        "auto_lights": "not_working",
        "multiple_light_issues": "yes",
    },
    n_variations=50,
))


# =============================================================================
# BODY ELECTRICAL SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="body_electrical.window_motor_failing",
    failure_mode_name="Power Window Motor Failing",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "window_fl_speed": -0.50,        # Slow operation
        "window_fl_current": 1.5,        # High current draw (A)
        "window_fl_position_error": 0.1, # Position errors
    },
    sensor_noise={
        "window_fl_current": 0.3,        # Intermittent
    },
    expected_patterns={
        "window": "slow_or_stuck",
        "noise": "grinding_or_clicking",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="body_electrical.door_lock_actuator",
    failure_mode_name="Door Lock Actuator Failed",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "door_fl_lock_status": 0.5,      # Inconsistent status
        "door_fl_lock_current": 0.0,     # No current = no movement
        "central_lock_error": 1.0,
    },
    expected_patterns={
        "door_lock": "not_responding",
        "key_fob": "one_door_not_locking",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="body_electrical.bcm_fault",
    failure_mode_name="Body Control Module Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.8,
        ),
    ],
    sensor_biases={
        "bcm_status": 0.0,               # Module fault
        "can_bus_errors_bcm": 5.0,       # Communication errors
        "interior_lights_error": 1.0,
        "wiper_error": 1.0,
        "accessory_power_error": 1.0,
    },
    expected_patterns={
        "multiple_electrical": "issues",
        "intermittent": "symptoms",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="body_electrical.parasitic_drain",
    failure_mode_name="Parasitic Battery Drain",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "key_off_current": 0.350,        # 350mA drain (normal <50mA)
        "battery_voltage_overnight": -1.5,  # Voltage drop
        "battery_state_of_charge": -0.20,   # Depleted
    },
    expected_patterns={
        "battery": "dead_after_sitting",
        "starting": "slow_crank_morning",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="body_electrical.relay_stuck",
    failure_mode_name="Electrical Relay Stuck",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "relay_state_error": 1.0,        # Stuck on or off
        "controlled_circuit_status": 0.5,  # Erratic operation
        "relay_coil_resistance": 999.0,  # Open or shorted
    },
    expected_patterns={
        "component": "stuck_on_or_off",
        "fuse": "may_blow",
    },
    n_variations=60,
))


# =============================================================================
# HYBRID SYSTEM FAILURES
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="hybrid.hv_battery_degraded",
    failure_mode_name="HV Battery Capacity Degraded",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "hv_battery_soc_max": -0.25,     # Can't charge fully
        "hv_battery_capacity": -0.30,    # 30% capacity loss
        "ev_range_estimate": -0.35,      # Reduced EV range
        "hv_battery_temp": 10.0,         # Running warm (°C)
        "cell_voltage_variance": 0.15,   # Unbalanced cells (V)
    },
    expected_patterns={
        "ev_range": "reduced",
        "fuel_economy": "decreased",
    },
    n_variations=120,
))

register_simulation(FailureSimulation(
    failure_mode_id="hybrid.inverter_fault",
    failure_mode_name="Hybrid Inverter Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.TORQUE_REDUCTION,
            magnitude=0.40,
        ),
    ],
    sensor_biases={
        "inverter_temp": 50.0,           # Overheating (°C above normal)
        "hv_system_lamp": 1.0,           # Warning light
        "electric_motor_available": 0.0,  # Motor disabled
        "regenerative_braking": 0.0,     # Regen disabled
    },
    expected_patterns={
        "warning_light": "hybrid_system",
        "power": "gas_only",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="hybrid.cooling_pump_failed",
    failure_mode_name="HV Battery Cooling Pump Failed",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "hv_battery_temp": 25.0,         # Overheating (°C above normal)
        "hv_coolant_flow": 0.0,          # No flow
        "hv_system_lamp": 1.0,
        "power_limit_active": 1.0,       # Power limited for protection
    },
    expected_patterns={
        "warning_light": "overheating",
        "power": "reduced_for_protection",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="hybrid.12v_battery_weak",
    failure_mode_name="12V Auxiliary Battery Weak (Hybrid)",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "aux_battery_voltage": -1.5,     # Low voltage (V)
        "aux_battery_cca": -0.30,        # Reduced CCA
        "ready_light_delay": 3.0,        # Slow to "Ready" (s)
        "accessory_power_error": 0.5,
    },
    expected_patterns={
        "starting": "slow_to_ready",
        "electrical": "glitches",
    },
    n_variations=80,
))


# =============================================================================
# ADDITIONAL BRAKE SYSTEM FAILURES (expanding from 1)
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="brakes.caliper_sticking",
    failure_mode_name="Brake Caliper Sticking",
    injections=[
        FaultInjection(
            fault_type=FaultType.BRAKE_REDUCTION,
            magnitude=0.3,
        ),
    ],
    sensor_biases={
        "brake_temp_fl": 150.0,          # Hot caliper (°F above normal)
        "brake_drag": 1.0,               # Dragging brake
        "fuel_economy_loss": 0.15,       # MPG loss from drag
        "wheel_pull": 0.3,               # Pulls when braking
    },
    expected_patterns={
        "pull": "to_one_side_braking",
        "smell": "hot_brakes",
    },
    n_variations=100,
))

register_simulation(FailureSimulation(
    failure_mode_id="brakes.master_cylinder_failing",
    failure_mode_name="Master Cylinder Failing",
    injections=[
        FaultInjection(
            fault_type=FaultType.BRAKE_REDUCTION,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "brake_pedal_travel": 0.30,      # Extra travel before engagement
        "brake_pressure": -0.25,         # Reduced pressure
        "brake_fluid_level": -0.10,      # Slight level drop
    },
    expected_patterns={
        "pedal": "spongy_or_sinks",
        "stopping": "longer_distance",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="brakes.rotor_warped",
    failure_mode_name="Warped Brake Rotor",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.4,
        ),
    ],
    sensor_biases={
        "brake_vibration": 0.6,          # Pulsation when braking
        "steering_wheel_shake": 0.4,     # Shake through steering
        "rotor_runout": 0.008,           # Inches of runout
    },
    expected_patterns={
        "vibration": "when_braking",
        "steering_shake": "during_braking",
    },
    n_variations=100,
))


# =============================================================================
# ADDITIONAL STARTING SYSTEM FAILURES (expanding from 1)
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="starting.starter_solenoid_weak",
    failure_mode_name="Starter Solenoid Weak",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "starter_engage_time": 0.5,      # Delayed engagement (s)
        "solenoid_click": 0.5,           # Click but no crank (intermittent)
        "starting_current": -0.20,       # Low current (not engaging)
    },
    sensor_noise={
        "starter_engage_time": 0.2,      # Intermittent
    },
    expected_patterns={
        "starting": "click_no_crank",
        "intermittent": "yes",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="starting.neutral_safety_switch",
    failure_mode_name="Neutral Safety Switch Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "gear_position_signal": 0.0,     # No signal
        "starter_enable": 0.0,           # Starter inhibited
        "shift_indicator_error": 1.0,
    },
    expected_patterns={
        "no_crank": "in_park",
        "workaround": "start_in_neutral",
    },
    n_variations=60,
))


# =============================================================================
# ADDITIONAL EV SYSTEM FAILURES (expanding from 1)
# =============================================================================

register_simulation(FailureSimulation(
    failure_mode_id="ev.charging_port_fault",
    failure_mode_name="EV Charging Port Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.6,
        ),
    ],
    sensor_biases={
        "charge_port_status": 0.0,       # Fault
        "charge_pilot_signal": 0.0,      # No communication
        "charge_session_error": 1.0,
    },
    expected_patterns={
        "charging": "wont_start",
        "port_light": "error_color",
    },
    n_variations=80,
))

register_simulation(FailureSimulation(
    failure_mode_id="ev.onboard_charger_fault",
    failure_mode_name="Onboard Charger Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "ac_charge_power": 0.0,          # No AC charging
        "charger_temp": 50.0,            # Overheating
        "charge_rate_ac": 0.0,           # 0 kW AC
        "hv_system_lamp": 1.0,
    },
    expected_patterns={
        "ac_charging": "not_working",
        "dc_fast_charge": "may_work",
    },
    n_variations=60,
))

register_simulation(FailureSimulation(
    failure_mode_id="ev.dc_dc_converter_fault",
    failure_mode_name="DC-DC Converter Fault",
    injections=[
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.7,
        ),
    ],
    sensor_biases={
        "aux_battery_voltage": -2.0,     # Low 12V (not charging)
        "dcdc_output_voltage": 0.0,      # No output
        "dcdc_status": 0.0,              # Fault
        "accessory_power_error": 1.0,
    },
    expected_patterns={
        "12v_system": "dying",
        "warning_light": "multiple",
    },
    n_variations=60,
))


# =============================================================================
# FAULT INJECTOR CLASS
# =============================================================================

class ChronoFaultInjector:
    """
    Applies fault injections to a PyChrono vehicle simulation.
    
    Usage:
        injector = ChronoFaultInjector(simulation)
        
        # In simulation loop:
        driver_inputs = injector.modify_inputs(driver_inputs, time)
        # ... run simulation step ...
        sensor_data = injector.modify_outputs(raw_sensor_data, time)
    """
    
    def __init__(self, simulation: FailureSimulation, severity: float = 0.5):
        self.simulation = simulation
        self.severity = severity
        self._start_time = 0.0
    
    def modify_inputs(self, inputs: Dict[str, float], time: float) -> Dict[str, float]:
        """Modify driver inputs based on fault injections."""
        modified = inputs.copy()
        
        for injection in self.simulation.injections:
            if injection.fault_type == FaultType.THROTTLE_STUCK:
                # Clamp throttle to stuck value
                stuck_value = injection.magnitude * self.severity
                modified['throttle'] = max(modified.get('throttle', 0), stuck_value)
                
            elif injection.fault_type == FaultType.THROTTLE_DELAYED:
                # Smooth/delay throttle response
                # (Would need state from previous step - simplified here)
                pass
        
        return modified
    
    def modify_torque(self, base_torque: float, time: float, cycle: int = 0) -> float:
        """Modify engine torque output based on fault injections."""
        torque = base_torque
        
        for injection in self.simulation.injections:
            # Check if fault has started
            if time < injection.onset_time:
                continue
            
            # Calculate effective magnitude with ramp
            if injection.ramp_time > 0:
                ramp_progress = min(1.0, (time - injection.onset_time) / injection.ramp_time)
            else:
                ramp_progress = 1.0
            
            effective_mag = injection.magnitude * self.severity * ramp_progress
            
            # Add variation
            effective_mag *= (1.0 + random.gauss(0, injection.variation))
            
            if injection.fault_type == FaultType.TORQUE_REDUCTION:
                torque *= (1.0 - effective_mag)
                
            elif injection.fault_type == FaultType.TORQUE_FLUCTUATION:
                if injection.pattern:
                    # Apply pattern-based reduction
                    pattern_idx = cycle % len(injection.pattern)
                    pattern_mult = injection.pattern[pattern_idx]
                    torque *= pattern_mult
                elif injection.intermittent:
                    # Random intermittent
                    if random.random() > injection.duty_cycle:
                        torque *= (1.0 - effective_mag)
        
        return torque
    
    def modify_outputs(self, sensor_data: Dict[str, float], time: float) -> Dict[str, float]:
        """Apply sensor biases and noise to simulation outputs."""
        modified = sensor_data.copy()
        
        # Apply biases
        for pid, bias in self.simulation.sensor_biases.items():
            if pid in modified:
                effective_bias = bias * self.severity
                modified[pid] += effective_bias
        
        # Apply noise
        for pid, noise_std in self.simulation.sensor_noise.items():
            if pid in modified:
                modified[pid] += random.gauss(0, noise_std)
        
        return modified
    
    def get_tire_friction_multiplier(self) -> float:
        """Get tire friction multiplier for worn/wet tire faults."""
        for injection in self.simulation.injections:
            if injection.fault_type == FaultType.TIRE_FRICTION:
                return 1.0 - (injection.magnitude * self.severity)
        return 1.0
    
    def get_brake_multiplier(self, time: float) -> float:
        """Get brake effectiveness multiplier for brake faults."""
        for injection in self.simulation.injections:
            if injection.fault_type == FaultType.BRAKE_REDUCTION:
                if time >= injection.onset_time:
                    return 1.0 - (injection.magnitude * self.severity)
        return 1.0


# =============================================================================
# AUTO-LOAD GENERATED SIMULATIONS FROM KNOWLEDGE BASE
# =============================================================================

def load_generated_simulations():
    """Load auto-generated simulations from knowledge_sync."""
    import sys
    from pathlib import Path
    
    # Add parent to path for knowledge imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    try:
        from knowledge.failures import get_all_failure_modes
        from knowledge_sync import (
            knowledge_to_sim_id, 
            generate_sensor_biases,
            get_knowledge_failures_with_pid_effects
        )
        
        # Get failures with PID effects that we don't already have
        existing_ids = set(FAILURE_SIMULATIONS.keys())
        
        for failure in get_knowledge_failures_with_pid_effects():
            sim_id = knowledge_to_sim_id(failure.id)
            
            # Skip if already registered manually
            if sim_id in existing_ids:
                continue
            
            # Generate sensor biases from PID effects
            biases = generate_sensor_biases(failure)
            
            # Skip if no usable biases
            if not biases:
                continue
            
            # Create simulation with sensor drift only (no physics)
            sim = FailureSimulation(
                failure_mode_id=sim_id,
                failure_mode_name=failure.name,
                injections=[
                    FaultInjection(
                        fault_type=FaultType.SENSOR_DRIFT,
                        magnitude=0.5,
                    ),
                ],
                sensor_biases=biases,
                severity_range=(0.1, 0.9),
                n_variations=30,  # Fewer variations for auto-generated
            )
            register_simulation(sim)
        
    except ImportError as e:
        # Knowledge module not available, skip auto-generation
        pass


# Auto-load on module import
load_generated_simulations()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_all_simulations() -> List[FailureSimulation]:
    """Get all registered failure simulations."""
    return list(FAILURE_SIMULATIONS.values())


def get_simulation(failure_mode_id: str) -> Optional[FailureSimulation]:
    """Get simulation for a specific failure mode."""
    return FAILURE_SIMULATIONS.get(failure_mode_id)


def get_simulations_by_system(system: str) -> List[FailureSimulation]:
    """Get all simulations for a system (e.g., 'fuel', 'cooling')."""
    return [
        sim for sim in FAILURE_SIMULATIONS.values()
        if sim.failure_mode_id.startswith(f"{system}.")
    ]


# =============================================================================
# MAIN - List available simulations
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Registered Failure Simulations")
    print("=" * 60)
    
    for sim in get_all_simulations():
        print(f"\n{sim.failure_mode_id}: {sim.failure_mode_name}")
        print(f"  Injections: {len(sim.injections)}")
        print(f"  Sensor biases: {list(sim.sensor_biases.keys())}")
        print(f"  Variations to generate: {sim.n_variations}")
        print(f"  Severity range: {sim.severity_range}")
    
    print(f"\nTotal: {len(FAILURE_SIMULATIONS)} failure simulations")
