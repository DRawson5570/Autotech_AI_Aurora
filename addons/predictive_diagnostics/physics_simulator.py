"""
Physics Simulator for Automotive Failure Modes

This module generates synthetic PID data based on physics principles.
It's NOT machine learning - it's a forward model that says:

    "IF thermostat stuck open THEN coolant temp will behave like THIS"

The generated patterns are used to train the RF classifier to RECOGNIZE
failure modes. The RF doesn't learn physics - it learns to pattern match.

Physics captured here:
- Thermal dynamics (coolant system, oil temp)
- Fluid dynamics (fuel pressure, vacuum)
- Electrical behavior (voltage, resistance)
- Mechanical dynamics (RPM, speed)

Usage:
    from physics_simulator import PhysicsSimulator
    
    sim = PhysicsSimulator()
    pid_series = sim.simulate_failure("thermostat_stuck_open", duration_sec=300)
    # Returns time series of PID values showing failure progression
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import random
import math
import numpy as np
from datetime import datetime, timedelta

try:
    from .pid_specs import STANDARD_PIDS, VehicleSpecs
except ImportError:
    from pid_specs import STANDARD_PIDS, VehicleSpecs


# =============================================================================
# SIMULATION PARAMETERS
# =============================================================================

@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    duration_sec: float = 300       # 5 minutes default
    sample_rate_hz: float = 1.0     # 1 Hz default (1 sample/second)
    ambient_temp_f: float = 70.0    # Starting ambient temperature
    initial_coolant_f: float = 70.0 # Cold start
    initial_oil_f: float = 70.0
    initial_rpm: float = 0.0        # Engine off
    noise_level: float = 0.02       # 2% noise
    
    # Driving profile
    idle_only: bool = False         # Just idle, no driving
    aggressive_driving: bool = False # Higher loads
    highway_cruise: bool = False     # Steady state highway


@dataclass 
class EngineState:
    """Current state of the engine simulation."""
    time_sec: float = 0.0
    rpm: float = 0.0
    coolant_temp_f: float = 70.0
    oil_temp_f: float = 70.0
    intake_air_temp_f: float = 70.0
    map_kpa: float = 101.0          # Atmospheric
    maf_gs: float = 0.0
    throttle_pct: float = 0.0
    vehicle_speed_mph: float = 0.0
    stft_b1: float = 0.0            # Short term fuel trim
    ltft_b1: float = 0.0            # Long term fuel trim
    o2_b1s1_v: float = 0.45         # O2 sensor
    voltage: float = 12.6           # Battery
    fuel_pressure_kpa: float = 350.0
    timing_advance_deg: float = 10.0
    engine_load_pct: float = 0.0
    
    # Internal physics state (not PID visible)
    thermostat_open_pct: float = 0.0
    coolant_flow_rate: float = 0.0
    fan_running: bool = False
    engine_running: bool = False


# =============================================================================
# PHYSICS MODELS
# =============================================================================

class ThermalModel:
    """Models thermal behavior of cooling system."""
    
    # Physics constants
    COOLANT_HEAT_CAPACITY = 1.0     # Relative heat capacity
    ENGINE_HEAT_RATE_IDLE = 3.0     # °F/sec heat generation at idle
    ENGINE_HEAT_RATE_LOAD = 10.0    # °F/sec at full load
    RADIATOR_COOLING_RATE = 0.05    # °F/sec per degree above ambient, when flowing
    AMBIENT_COOLING_RATE = 0.01     # °F/sec per degree above ambient, natural
    THERMOSTAT_OPEN_TEMP = 195.0    # °F
    THERMOSTAT_FULL_OPEN = 210.0    # °F
    OVERHEAT_TEMP = 240.0           # °F
    FAN_ON_TEMP = 220.0             # °F
    FAN_OFF_TEMP = 200.0            # °F
    AMBIENT_TEMP = 70.0             # °F
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update coolant temperature based on physics."""
        if not state.engine_running:
            # Engine off - cool toward ambient
            temp_diff = state.coolant_temp_f - cls.AMBIENT_TEMP
            cool_rate = cls.AMBIENT_COOLING_RATE * temp_diff
            state.coolant_temp_f -= cool_rate * dt
            state.thermostat_open_pct = 0.0
            state.fan_running = False
            return
        
        # Heat generation based on load
        load_factor = state.engine_load_pct / 100.0
        heat_rate = cls.ENGINE_HEAT_RATE_IDLE + (cls.ENGINE_HEAT_RATE_LOAD - cls.ENGINE_HEAT_RATE_IDLE) * load_factor
        
        # Thermostat behavior
        if failure_mode == "thermostat_stuck_open":
            state.thermostat_open_pct = 1.0  # Always open
        elif failure_mode == "thermostat_stuck_closed":
            state.thermostat_open_pct = 0.0  # Always closed
        else:
            # Normal thermostat - gradual opening
            if state.coolant_temp_f < cls.THERMOSTAT_OPEN_TEMP:
                state.thermostat_open_pct = 0.0
            elif state.coolant_temp_f > cls.THERMOSTAT_FULL_OPEN:
                state.thermostat_open_pct = 1.0
            else:
                state.thermostat_open_pct = (state.coolant_temp_f - cls.THERMOSTAT_OPEN_TEMP) / (cls.THERMOSTAT_FULL_OPEN - cls.THERMOSTAT_OPEN_TEMP)
        
        # Water pump - determines coolant flow
        if failure_mode == "water_pump_failure":
            state.coolant_flow_rate = 0.1  # Minimal flow
        else:
            state.coolant_flow_rate = 0.5 + 0.5 * (state.rpm / 3000)  # RPM dependent
        
        # Cooling calculation
        temp_above_ambient = state.coolant_temp_f - cls.AMBIENT_TEMP
        cooling_rate = 0.0
        
        # Radiator cooling when thermostat is open
        if state.thermostat_open_pct > 0:
            base_cooling = cls.RADIATOR_COOLING_RATE * temp_above_ambient * state.thermostat_open_pct * state.coolant_flow_rate
            
            # Fan control
            if failure_mode == "cooling_fan_failure":
                state.fan_running = False
            else:
                if state.coolant_temp_f > cls.FAN_ON_TEMP:
                    state.fan_running = True
                elif state.coolant_temp_f < cls.FAN_OFF_TEMP:
                    state.fan_running = False
            
            # Fan adds cooling
            if state.fan_running:
                base_cooling *= 2.0
            
            # Airflow from vehicle speed adds cooling
            speed_factor = 1.0 + state.vehicle_speed_mph / 30.0
            cooling_rate = base_cooling * speed_factor
        else:
            # Thermostat closed - minimal cooling, only through block
            cooling_rate = cls.AMBIENT_COOLING_RATE * temp_above_ambient * 0.3
        
        # Coolant leak - loses coolant, reduces cooling efficiency AND reduces heat capacity
        if failure_mode == "coolant_leak":
            cooling_rate *= 0.6  # Reduced cooling (less coolant to radiate)
            heat_rate *= 1.3     # Faster temp rise (less coolant mass)
        
        # Net temperature change
        delta_temp = (heat_rate - cooling_rate) * dt
        state.coolant_temp_f += delta_temp
        
        # Clamp to reasonable range
        state.coolant_temp_f = max(state.coolant_temp_f, cls.AMBIENT_TEMP)
        state.coolant_temp_f = min(state.coolant_temp_f, 280.0)  # Max realistic overheat


class FuelModel:
    """Models fuel system behavior."""
    
    NORMAL_FUEL_PRESSURE_KPA = 350.0
    PRESSURE_TOLERANCE = 0.10  # ±10%
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update fuel system parameters."""
        if not state.engine_running:
            state.fuel_pressure_kpa = 0.0
            state.stft_b1 = 0.0
            return
        
        # Base fuel pressure
        target_pressure = cls.NORMAL_FUEL_PRESSURE_KPA
        
        if failure_mode == "fuel_pump_weak":
            target_pressure *= 0.75  # 25% low
        elif failure_mode == "fuel_pressure_regulator_failure":
            target_pressure *= 1.3   # Running high
        elif failure_mode == "clogged_fuel_filter":
            target_pressure *= 0.85  # Slightly low
        
        # Smooth transition to target
        state.fuel_pressure_kpa += (target_pressure - state.fuel_pressure_kpa) * 0.1
        
        # Fuel trim response to pressure issues
        pressure_error = (state.fuel_pressure_kpa - cls.NORMAL_FUEL_PRESSURE_KPA) / cls.NORMAL_FUEL_PRESSURE_KPA
        
        # Low pressure = lean = positive fuel trim (adding fuel)
        # High pressure = rich = negative fuel trim
        base_trim = -pressure_error * 30  # Scale to reasonable trim values
        
        # Vacuum leak - causes lean condition
        if failure_mode == "vacuum_leak":
            base_trim += 15  # Lean, adding fuel
        
        # Injector issues
        if failure_mode == "injector_clogged":
            base_trim += 12
        elif failure_mode == "injector_leaking":
            base_trim -= 10
        
        # MAF issues
        if failure_mode == "maf_sensor_dirty":
            base_trim += 8  # Under-reports air, goes lean
        
        # STFT responds quickly
        state.stft_b1 += (base_trim - state.stft_b1) * 0.3 * dt
        state.stft_b1 = max(-25, min(25, state.stft_b1))  # Clamp
        
        # LTFT adapts slowly
        if abs(state.stft_b1) > 5:
            state.ltft_b1 += state.stft_b1 * 0.01 * dt
        state.ltft_b1 = max(-25, min(25, state.ltft_b1))


class O2SensorModel:
    """Models O2 sensor behavior."""
    
    STOICH_VOLTAGE = 0.45
    LEAN_VOLTAGE = 0.1
    RICH_VOLTAGE = 0.9
    SWITCH_PERIOD_SEC = 1.0
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update O2 sensor readings."""
        if not state.engine_running:
            state.o2_b1s1_v = 0.0
            return
        
        # Normal switching behavior based on fuel trim
        total_trim = state.stft_b1 + state.ltft_b1
        
        if failure_mode == "o2_sensor_stuck_lean":
            state.o2_b1s1_v = cls.LEAN_VOLTAGE + random.uniform(-0.02, 0.02)
        elif failure_mode == "o2_sensor_stuck_rich":
            state.o2_b1s1_v = cls.RICH_VOLTAGE + random.uniform(-0.02, 0.02)
        elif failure_mode == "o2_sensor_lazy":
            # Slow switching, dampened response
            target = cls.STOICH_VOLTAGE + math.sin(state.time_sec * 0.5) * 0.2
            state.o2_b1s1_v += (target - state.o2_b1s1_v) * 0.1 * dt
        else:
            # Normal fast switching
            switch_val = math.sin(state.time_sec * 2 * math.pi / cls.SWITCH_PERIOD_SEC)
            # Bias based on fuel trim
            bias = -total_trim * 0.01  # Positive trim = lean = lower voltage
            state.o2_b1s1_v = cls.STOICH_VOLTAGE + switch_val * 0.35 + bias
        
        state.o2_b1s1_v = max(0.0, min(1.0, state.o2_b1s1_v))


class ElectricalModel:
    """Models electrical system behavior."""
    
    BATTERY_VOLTAGE = 12.6
    CHARGING_VOLTAGE_MIN = 13.5
    CHARGING_VOLTAGE_MAX = 14.7
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update electrical system."""
        if not state.engine_running:
            # Battery only
            if failure_mode == "battery_weak":
                state.voltage = 11.8 + random.uniform(-0.2, 0.2)
            else:
                state.voltage = cls.BATTERY_VOLTAGE + random.uniform(-0.1, 0.1)
            return
        
        # Engine running - alternator charging
        if failure_mode == "alternator_failure":
            # No charging, draining battery
            state.voltage = max(10.0, state.voltage - 0.01 * dt)
        elif failure_mode == "voltage_regulator_failure":
            # Overcharging or erratic
            state.voltage = 15.5 + random.uniform(-1.0, 1.0)
        else:
            # Normal charging
            target = (cls.CHARGING_VOLTAGE_MIN + cls.CHARGING_VOLTAGE_MAX) / 2
            state.voltage += (target - state.voltage) * 0.5 * dt
            state.voltage += random.uniform(-0.1, 0.1)


class IntakeModel:
    """Models intake/air system behavior."""
    
    ATMOSPHERIC_KPA = 101.3
    IDLE_MAP_KPA = 35.0
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update intake system parameters."""
        if not state.engine_running:
            state.map_kpa = cls.ATMOSPHERIC_KPA
            state.maf_gs = 0.0
            state.intake_air_temp_f = 70.0
            return
        
        # MAP based on throttle and RPM
        base_map = cls.IDLE_MAP_KPA + (cls.ATMOSPHERIC_KPA - cls.IDLE_MAP_KPA) * (state.throttle_pct / 100)
        
        if failure_mode == "vacuum_leak":
            base_map += 15  # Higher MAP (less vacuum)
        elif failure_mode == "pcv_valve_stuck_open":
            base_map += 8
        
        state.map_kpa = base_map + random.uniform(-1, 1)
        
        # MAF based on RPM and throttle
        base_maf = 3.0 + (state.rpm / 1000) * 5.0 * (1 + state.throttle_pct / 100)
        
        if failure_mode == "maf_sensor_dirty":
            base_maf *= 0.85  # Under-reports
        elif failure_mode == "maf_sensor_failure":
            base_maf = 0.0  # Dead
        elif failure_mode == "air_filter_clogged":
            base_maf *= 0.9
        
        state.maf_gs = base_maf + random.uniform(-0.5, 0.5)
        
        # Intake air temp
        if failure_mode == "iat_sensor_failure":
            state.intake_air_temp_f = -40  # Typical failure value
        else:
            # Rises slightly with engine heat
            heat_soak = min(20, state.time_sec / 60 * 5)  # Up to 20°F
            state.intake_air_temp_f = 70 + heat_soak + random.uniform(-2, 2)


class IgnitionModel:
    """Models ignition system behavior."""
    
    BASE_TIMING = 10.0  # degrees BTDC
    
    @classmethod
    def update(cls, state: EngineState, dt: float, failure_mode: str = None):
        """Update ignition parameters."""
        if not state.engine_running:
            state.timing_advance_deg = 0.0
            return
        
        # Base timing + advance
        base = cls.BASE_TIMING
        
        # More advance at higher RPM, less at high load
        rpm_advance = (state.rpm - 800) / 1000 * 10
        load_retard = state.engine_load_pct / 100 * 5
        
        target = base + rpm_advance - load_retard
        
        if failure_mode == "knock_sensor_failure":
            # Can't detect knock, may not retard when needed
            target += 5  # Running too advanced
        
        state.timing_advance_deg = target + random.uniform(-0.5, 0.5)


# =============================================================================
# MAIN SIMULATOR
# =============================================================================

class PhysicsSimulator:
    """
    Simulates engine/vehicle behavior under various failure modes.
    
    Uses physics models to generate realistic PID time series.
    """
    
    # Mapping of failure modes to physics effects
    SUPPORTED_FAILURES = {
        # Cooling system
        "thermostat_stuck_open": "cooling",
        "thermostat_stuck_closed": "cooling",
        "water_pump_failure": "cooling",
        "cooling_fan_failure": "cooling",
        "coolant_leak": "cooling",
        
        # Fuel system
        "fuel_pump_weak": "fuel",
        "fuel_pressure_regulator_failure": "fuel",
        "clogged_fuel_filter": "fuel",
        "vacuum_leak": "fuel",
        "injector_clogged": "fuel",
        "injector_leaking": "fuel",
        "maf_sensor_dirty": "fuel",
        
        # O2 sensors
        "o2_sensor_stuck_lean": "o2",
        "o2_sensor_stuck_rich": "o2",
        "o2_sensor_lazy": "o2",
        
        # Electrical
        "alternator_failure": "electrical",
        "voltage_regulator_failure": "electrical",
        "battery_weak": "electrical",
        
        # Intake
        "maf_sensor_failure": "intake",
        "air_filter_clogged": "intake",
        "pcv_valve_stuck_open": "intake",
        "iat_sensor_failure": "intake",
        
        # Ignition
        "knock_sensor_failure": "ignition",
        
        # Normal operation (no failure)
        "normal": None,
    }
    
    def __init__(self, vehicle_specs: VehicleSpecs = None):
        """Initialize simulator with optional vehicle-specific specs."""
        self.vehicle_specs = vehicle_specs
        
        # Override physics constants if we have vehicle specs
        if vehicle_specs:
            if vehicle_specs.thermostat_opens_at:
                ThermalModel.THERMOSTAT_OPEN_TEMP = vehicle_specs.thermostat_opens_at
            if vehicle_specs.operating_temp_max:
                ThermalModel.THERMOSTAT_FULL_OPEN = vehicle_specs.operating_temp_max
            if vehicle_specs.fuel_pressure_spec:
                FuelModel.NORMAL_FUEL_PRESSURE_KPA = vehicle_specs.fuel_pressure_spec
    
    def simulate_failure(
        self,
        failure_mode: str,
        config: SimulationConfig = None,
        driving_profile: List[Tuple[float, float, float]] = None,
    ) -> Dict[str, List[Tuple[float, float]]]:
        """
        Simulate a failure mode and return PID time series.
        
        Args:
            failure_mode: One of SUPPORTED_FAILURES keys
            config: Simulation configuration
            driving_profile: Optional list of (time, rpm, throttle) tuples
            
        Returns:
            Dict mapping PID name to list of (time, value) tuples
        """
        if failure_mode not in self.SUPPORTED_FAILURES:
            raise ValueError(f"Unknown failure mode: {failure_mode}. "
                           f"Supported: {list(self.SUPPORTED_FAILURES.keys())}")
        
        config = config or SimulationConfig()
        state = EngineState(
            coolant_temp_f=config.initial_coolant_f,
            oil_temp_f=config.initial_oil_f,
            intake_air_temp_f=config.ambient_temp_f,
        )
        
        # Generate driving profile if not provided
        if driving_profile is None:
            driving_profile = self._generate_driving_profile(config)
        
        # Run simulation
        dt = 1.0 / config.sample_rate_hz
        time_points = np.arange(0, config.duration_sec, dt)
        
        # Initialize result arrays
        results = {
            "coolant_temp": [],
            "rpm": [],
            "stft_b1": [],
            "ltft_b1": [],
            "o2_b1s1": [],
            "voltage": [],
            "map": [],
            "maf": [],
            "throttle_position": [],
            "vehicle_speed": [],
            "intake_air_temp": [],
            "fuel_pressure": [],
            "timing_advance": [],
            "engine_load": [],
        }
        
        profile_idx = 0
        for t in time_points:
            state.time_sec = t
            
            # Get driving inputs from profile
            while profile_idx < len(driving_profile) - 1 and driving_profile[profile_idx + 1][0] <= t:
                profile_idx += 1
            
            _, target_rpm, target_throttle = driving_profile[profile_idx]
            
            # Engine start at t=5
            if t >= 5 and not state.engine_running:
                state.engine_running = True
                state.rpm = 1200  # Cranking
            
            # Smooth RPM and throttle transitions
            if state.engine_running:
                state.rpm += (target_rpm - state.rpm) * 0.1
                state.throttle_pct += (target_throttle - state.throttle_pct) * 0.2
                
                # Calculate load from throttle and RPM
                state.engine_load_pct = state.throttle_pct * 0.7 + (state.rpm / 6000) * 30
                
                # Vehicle speed from RPM (simplified)
                state.vehicle_speed_mph = max(0, (state.rpm - 800) / 40)
            
            # Update all physics models
            ThermalModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            FuelModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            O2SensorModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            ElectricalModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            IntakeModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            IgnitionModel.update(state, dt, failure_mode if failure_mode != "normal" else None)
            
            # Add noise
            noise = config.noise_level
            
            # Record results
            results["coolant_temp"].append((t, state.coolant_temp_f + random.uniform(-noise*10, noise*10)))
            results["rpm"].append((t, state.rpm + random.uniform(-noise*50, noise*50)))
            results["stft_b1"].append((t, state.stft_b1 + random.uniform(-noise*2, noise*2)))
            results["ltft_b1"].append((t, state.ltft_b1 + random.uniform(-noise*2, noise*2)))
            results["o2_b1s1"].append((t, state.o2_b1s1_v))
            results["voltage"].append((t, state.voltage))
            results["map"].append((t, state.map_kpa + random.uniform(-noise*5, noise*5)))
            results["maf"].append((t, state.maf_gs + random.uniform(-noise*1, noise*1)))
            results["throttle_position"].append((t, state.throttle_pct))
            results["vehicle_speed"].append((t, state.vehicle_speed_mph))
            results["intake_air_temp"].append((t, state.intake_air_temp_f))
            results["fuel_pressure"].append((t, state.fuel_pressure_kpa))
            results["timing_advance"].append((t, state.timing_advance_deg))
            results["engine_load"].append((t, state.engine_load_pct))
        
        return results
    
    def _generate_driving_profile(self, config: SimulationConfig) -> List[Tuple[float, float, float]]:
        """Generate a realistic driving profile."""
        profile = []
        
        # First 5 seconds - engine off
        profile.append((0, 0, 0))
        
        # Engine start and idle
        profile.append((5, 800, 5))
        
        if config.idle_only:
            # Just idle for duration
            profile.append((config.duration_sec, 800, 5))
        elif config.highway_cruise:
            # Quick warmup then highway
            profile.append((30, 1500, 20))  # Light driving
            profile.append((60, 2500, 40))  # Accelerating
            profile.append((90, 2200, 30))  # Highway cruise
            profile.append((config.duration_sec, 2200, 30))
        else:
            # Mixed city driving
            t = 10
            while t < config.duration_sec:
                # Random driving segments
                segment_type = random.choice(["idle", "accelerate", "cruise", "decel"])
                segment_duration = random.uniform(15, 45)
                
                if segment_type == "idle":
                    profile.append((t, 800, 5))
                elif segment_type == "accelerate":
                    profile.append((t, random.uniform(2000, 4000), random.uniform(40, 80)))
                elif segment_type == "cruise":
                    profile.append((t, random.uniform(1500, 2500), random.uniform(20, 40)))
                elif segment_type == "decel":
                    profile.append((t, random.uniform(1000, 1500), random.uniform(0, 10)))
                
                t += segment_duration
        
        return sorted(profile, key=lambda x: x[0])
    
    def extract_features(self, pid_series: Dict[str, List[Tuple[float, float]]]) -> Dict[str, float]:
        """
        Extract features from PID time series for classification.
        
        Returns statistical features suitable for RF training.
        """
        features = {}
        
        for pid_name, series in pid_series.items():
            if len(series) < 2:
                continue
                
            values = np.array([v for t, v in series])
            times = np.array([t for t, v in series])
            
            # Basic statistics
            features[f"{pid_name}_mean"] = float(np.mean(values))
            features[f"{pid_name}_std"] = float(np.std(values))
            features[f"{pid_name}_min"] = float(np.min(values))
            features[f"{pid_name}_max"] = float(np.max(values))
            features[f"{pid_name}_range"] = float(np.max(values) - np.min(values))
            
            # Rate of change
            if len(values) > 1:
                dv = np.diff(values)
                dt = np.diff(times)
                rates = dv / np.maximum(dt, 0.001)
                features[f"{pid_name}_rate_mean"] = float(np.mean(rates))
                features[f"{pid_name}_rate_max"] = float(np.max(np.abs(rates)))
            
            # Final value (steady state)
            features[f"{pid_name}_final"] = float(np.mean(values[-10:]))
            
            # Time to reach threshold (for warmup analysis)
            if pid_name == "coolant_temp":
                # Time to reach 180°F
                above_threshold = values >= 180
                if np.any(above_threshold):
                    idx = np.argmax(above_threshold)
                    features["coolant_warmup_time"] = float(times[idx])
                else:
                    features["coolant_warmup_time"] = float(times[-1])  # Never reached
        
        return features


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import sys
    import json
    
    failure_mode = sys.argv[1] if len(sys.argv) > 1 else "thermostat_stuck_open"
    
    print(f"\n=== Simulating: {failure_mode} ===\n")
    
    sim = PhysicsSimulator()
    config = SimulationConfig(duration_sec=300, idle_only=False)
    
    results = sim.simulate_failure(failure_mode, config)
    features = sim.extract_features(results)
    
    print("Key features:")
    for key in ["coolant_temp_final", "coolant_warmup_time", "stft_b1_mean", 
                "ltft_b1_mean", "voltage_mean", "fuel_pressure_final"]:
        if key in features:
            print(f"  {key}: {features[key]:.2f}")
    
    print(f"\nCoolant temp progression:")
    for i, (t, v) in enumerate(results["coolant_temp"]):
        if i % 30 == 0:  # Every 30 seconds
            print(f"  t={t:3.0f}s: {v:.1f}°F")
