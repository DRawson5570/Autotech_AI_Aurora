#!/usr/bin/env python3
"""
Batch Generator for Synthetic Diagnostic Training Data

Generates 1000s of labeled failure scenarios using PyChrono vehicle simulation.
Each scenario is a time-series of OBD-II style data with ground truth failure labels.

Usage:
    conda activate chrono_test
    python batch_generator.py --count 1000 --output ../training_data/chrono_synthetic
    
    # Use multiprocessing for faster generation:
    python batch_generator.py --count 20000 --workers 12 --output ../training_data/chrono_synthetic
"""

import pychrono as chrono
import pychrono.vehicle as veh
import json
import os
import math
import random
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import csv
import multiprocessing as mp
from functools import partial

from fault_injector import (
    FAILURE_SIMULATIONS, 
    FailureSimulation, 
    ChronoFaultInjector,
    get_all_simulations,
)


@dataclass
class SimulationConfig:
    """Configuration for a single simulation run."""
    failure_mode_id: str
    failure_mode_name: str
    vehicle_type: str
    severity: float
    duration: float
    scenario: str  # "idle", "acceleration", "cruise", "deceleration"
    ambient_temp: float
    road_surface: str


@dataclass 
class SensorReading:
    """A single timestep of sensor data."""
    t: float
    rpm: float
    speed_kmh: float
    throttle_pct: float
    engine_torque_nm: float
    gear: int
    coolant_temp: float
    stft_b1: float
    stft_b2: float
    ltft_b1: float
    ltft_b2: float
    engine_load: float
    fuel_pressure: float
    tire_pressure: float


@dataclass
class SimulationResult:
    """Complete result from one simulation run."""
    failure_mode_id: str
    failure_mode_name: str
    vehicle: str
    severity: float
    scenario: str
    conditions: Dict
    time_series: List[Dict]
    metadata: Dict


class BatchGenerator:
    """Generates batches of synthetic diagnostic training data."""
    
    # Available vehicles in PyChrono
    VEHICLES = ["hmmwv", "sedan"]  # Start with these two
    
    # Driving scenarios
    SCENARIOS = {
        "idle": {"throttle": 0.0, "duration": 30.0},
        "gentle_acceleration": {"throttle": 0.3, "duration": 20.0},
        "moderate_acceleration": {"throttle": 0.5, "duration": 15.0},
        "cruise": {"throttle": 0.2, "duration": 30.0},
        "wot": {"throttle": 1.0, "duration": 10.0},  # Wide open throttle
        "deceleration": {"throttle": 0.0, "duration": 15.0, "initial_speed": 60},
    }
    
    def __init__(self, output_dir: str, verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.manifest = []
        
    def log(self, msg: str):
        if self.verbose:
            print(msg)
    
    def create_vehicle(self, vehicle_type: str) -> Tuple[veh.HMMWV_Full, veh.RigidTerrain]:
        """Create a vehicle and terrain for simulation."""
        
        # Create HMMWV (we'll use this for all vehicles for now - it's the most complete)
        hmmwv = veh.HMMWV_Full()
        hmmwv.SetContactMethod(chrono.ChContactMethod_NSC)
        hmmwv.SetChassisCollisionType(veh.CollisionType_NONE)
        hmmwv.SetChassisFixed(False)
        hmmwv.SetInitPosition(chrono.ChCoordsysd(
            chrono.ChVector3d(0, 0, 1.6),
            chrono.ChQuaterniond(1, 0, 0, 0)
        ))
        hmmwv.SetEngineType(veh.EngineModelType_SIMPLE_MAP)
        hmmwv.SetTransmissionType(veh.TransmissionModelType_AUTOMATIC_SIMPLE_MAP)
        hmmwv.SetDriveType(veh.DrivelineTypeWV_AWD)
        hmmwv.SetTireType(veh.TireModelType_TMEASY)
        hmmwv.SetTireStepSize(1e-3)
        hmmwv.Initialize()
        
        # Create terrain
        terrain = veh.RigidTerrain(hmmwv.GetSystem())
        patch_mat = chrono.ChContactMaterialNSC()
        patch_mat.SetFriction(0.9)
        patch_mat.SetRestitution(0.01)
        terrain.AddPatch(patch_mat, chrono.CSYSNORM, 500, 500)
        terrain.Initialize()
        
        return hmmwv, terrain
    
    def run_simulation(self, config: SimulationConfig) -> SimulationResult:
        """Run a single simulation with fault injection."""
        
        # Get fault simulation
        fault_sim = FAILURE_SIMULATIONS.get(config.failure_mode_id)
        if not fault_sim:
            raise ValueError(f"Unknown failure mode: {config.failure_mode_id}")
        
        # Create fault injector
        injector = ChronoFaultInjector(fault_sim, config.severity)
        
        # Create vehicle
        hmmwv, terrain = self.create_vehicle(config.vehicle_type)
        
        # Simulation parameters
        step_size = 2e-3  # 2ms for speed
        scenario_config = self.SCENARIOS[config.scenario]
        target_throttle = scenario_config["throttle"]
        duration = scenario_config.get("duration", config.duration)
        
        # Run simulation
        time = 0
        time_series = []
        sample_interval = 0.1  # Sample every 100ms
        last_sample_time = -sample_interval
        cycle_count = 0
        
        # Base sensor values (will be modified by injector)
        base_coolant_temp = config.ambient_temp + 125  # Normal operating temp ~195F
        
        while time < duration:
            # Determine throttle based on scenario
            if config.scenario == "deceleration":
                # Start at speed, then coast
                if time < 2.0:
                    throttle = 0.5  # Get up to speed
                else:
                    throttle = 0.0  # Coast
            else:
                # Ramp up throttle over first 2 seconds
                ramp = min(1.0, time / 2.0)
                throttle = target_throttle * ramp
            
            # Apply fault injection to inputs
            modified_inputs = injector.modify_inputs(
                {"throttle": throttle, "steering": 0.0, "braking": 0.0},
                time
            )
            
            # Create driver inputs
            driver_inputs = veh.DriverInputs()
            driver_inputs.m_throttle = modified_inputs["throttle"]
            driver_inputs.m_steering = modified_inputs.get("steering", 0.0)
            driver_inputs.m_braking = modified_inputs.get("braking", 0.0)
            
            # Synchronize and advance
            terrain.Synchronize(time)
            hmmwv.Synchronize(time, driver_inputs, terrain)
            terrain.Advance(step_size)
            hmmwv.Advance(step_size)
            
            time += step_size
            cycle_count += 1
            
            # Sample sensor data
            if time - last_sample_time >= sample_interval:
                last_sample_time = time
                
                vehicle = hmmwv.GetVehicle()
                engine = vehicle.GetEngine()
                trans = vehicle.GetTransmission()
                
                # Get raw sensor data
                raw_rpm = engine.GetMotorSpeed() * 60 / (2 * math.pi) if engine else 750
                raw_torque = engine.GetOutputMotorshaftTorque() if engine else 0
                
                # Apply fault injection to torque (simulates power loss)
                modified_torque = injector.modify_torque(raw_torque, time, cycle_count)
                
                # Calculate derived values
                max_torque = 400  # Approximate max for HMMWV engine
                engine_load = abs(modified_torque) / max_torque * 100 if max_torque > 0 else 0
                
                # Raw sensor readings (base values before fault injection)
                raw_sensors = {
                    "rpm": raw_rpm,
                    "speed_kmh": vehicle.GetSpeed() * 3.6,
                    "throttle_pct": modified_inputs["throttle"] * 100,
                    "engine_torque_nm": modified_torque,
                    "gear": trans.GetCurrentGear() if trans else 1,
                    "coolant_temp": base_coolant_temp,
                    "stft_b1": 0.0,
                    "stft_b2": 0.0,
                    "ltft_b1": 0.0,
                    "ltft_b2": 0.0,
                    "engine_load": engine_load,
                    "fuel_pressure": 45.0,  # Normal ~45 PSI
                    "tire_pressure": 35.0,  # Normal ~35 PSI
                    # Extended sensors for tire/brake/trans faults
                    "wheel_slip_events": 0.0,   # TCS activations
                    "tire_wear_index": 0.0,     # 0=new, 1=bald
                    "brake_temp": 200.0,        # Normal brake temp ~200F
                    "decel_rate": 0.0,          # Current decel (g)
                    "brake_pedal_travel": 0.0,  # Pedal position
                    "trans_slip_ratio": 0.0,    # RPM/speed mismatch
                    "trans_temp": 180.0,        # Normal ATF ~180F
                    "shift_quality": 0.0,       # -1=harsh, 0=normal, 1=smooth
                    
                    # --- STEERING SYSTEM ---
                    "steering_effort": 1.0,      # Normal effort (lbf)
                    "ps_pump_pressure": 1200.0,  # Normal PS pressure (PSI)
                    "ps_fluid_temp": 150.0,      # Normal PS fluid temp (°F)
                    "steering_assist": 1.0,      # Normalized 0-1
                    "ps_fluid_level": 1.0,       # Normalized 0-1
                    "steering_play": 0.0,        # Degrees of play
                    "toe_angle": 0.0,            # Alignment (degrees)
                    "camber_angle": 0.0,         # Alignment (degrees)
                    "steering_wheel_offset": 0.0, # Degrees off center
                    
                    # --- SUSPENSION SYSTEM ---
                    "suspension_oscillation": 0.0, # Extra bounce cycles
                    "body_roll": 0.0,            # Roll angle (degrees)
                    "nose_dive": 0.0,            # Dive on braking
                    "ride_height_variance": 0.0,  # Ride height diff (inches)
                    "strut_noise_level": 0.0,    # Noise 0-1
                    "steering_feel": 1.0,        # Feel quality 0-1
                    "alignment_drift": 0.0,      # Alignment change
                    "suspension_play": 0.0,      # Play (inches)
                    "camber_variance": 0.0,      # Changes with load
                    "clunk_frequency": 0.0,      # Noise over bumps 0-1
                    "sway_bar_noise": 0.0,       # Rattle 0-1
                    "cornering_stability": 1.0,  # Stability 0-1
                    "ride_height_fl": 0.0,       # Corner ride height
                    
                    # --- HVAC SYSTEM ---
                    "ac_pressure_high": 250.0,   # High side pressure (PSI)
                    "ac_pressure_low": 35.0,     # Low side pressure (PSI)
                    "cabin_temp_delta": 0.0,     # Delta from target (°F)
                    "ac_clutch_cycling": 0.0,    # Excessive cycling 0-1
                    "ac_superheat": 10.0,        # Superheat (°F)
                    "blend_door_position": 0.5,  # Actual position 0-1
                    "blend_door_commanded": 0.5, # Commanded position 0-1
                    "cabin_temp_error": 0.0,     # Error from target (°F)
                    "blower_speed_actual": 1.0,  # Actual speed ratio 0-1
                    "blower_current": 8.0,       # Normal current (A)
                    "airflow_volume": 1.0,       # Normalized 0-1
                    "heater_inlet_temp": 195.0,  # Inlet temp (°F)
                    "heater_outlet_temp": 185.0, # Outlet temp (°F)
                    "cabin_heat_output": 1.0,    # Heat output 0-1
                    
                    # --- ABS SYSTEM ---
                    "wss_fl": 0.0,               # Wheel speed FL (mph)
                    "wss_fr": 0.0,               # Wheel speed FR (mph)
                    "wss_rl": 0.0,               # Wheel speed RL (mph)
                    "wss_rr": 0.0,               # Wheel speed RR (mph)
                    "wss_variance": 0.0,         # Variance between wheels
                    "abs_activation_false": 0.0, # False activations
                    "abs_lamp": 0.0,             # ABS light on 0-1
                    "abs_pump_pressure": 1.0,    # Pump pressure ratio 0-1
                    "abs_pump_current": 10.0,    # Current (A)
                    "abs_response_time": 0.0,    # Response delay (s)
                    "can_bus_errors_abs": 0.0,   # CAN errors
                    "traction_lamp": 0.0,        # TCS light
                    "stability_lamp": 0.0,       # ESC light
                    "wss_rr_variance": 0.0,      # RR sensor variance
                    "wss_rr_dropouts": 0.0,      # Signal dropouts
                    
                    # --- AIRBAG/SRS SYSTEM ---
                    "airbag_lamp": 0.0,          # SRS light
                    "driver_airbag_resistance": 2.5, # Normal ohms
                    "horn_function": 1.0,        # Horn working 0-1
                    "cruise_buttons": 1.0,       # Buttons working 0-1
                    "seat_occupancy_detected": 1.0, # Sensor working
                    "passenger_airbag_status": 1.0, # Enabled
                    "srs_dtc_count": 0.0,        # DTC count
                    "srs_readiness": 1.0,        # System ready 0-1
                    "can_bus_errors_srs": 0.0,   # CAN errors
                    
                    # --- LIGHTING SYSTEM ---
                    "headlight_fl_current": 4.5,  # Normal bulb current (A)
                    "headlight_fl_status": 1.0,   # Working 0-1
                    "headlight_fr_status": 1.0,
                    "lighting_dtc": 0.0,          # DTC stored
                    "hid_ballast_output": 85.0,   # Output voltage
                    "hid_igniter_attempts": 0.0,  # Ignition attempts
                    "turn_signal_frequency": 1.0, # Hz
                    "turn_signal_rr_current": 2.0, # Normal (A)
                    "turn_signal_load": 1.0,      # Load ratio
                    "bcm_lighting_status": 1.0,   # BCM status
                    "auto_headlight_function": 1.0, # Working 0-1
                    "daytime_running_lights": 1.0,  # Working 0-1
                    "can_bus_errors_bcm": 0.0,    # CAN errors
                    
                    # --- BODY ELECTRICAL ---
                    "window_fl_speed": 1.0,       # Speed ratio 0-1
                    "window_fl_current": 5.0,     # Normal current (A)
                    "window_fl_position_error": 0.0, # Position error
                    "door_fl_lock_status": 1.0,   # Status 0-1
                    "door_fl_lock_current": 0.5,  # Current (A)
                    "central_lock_error": 0.0,    # Error flag
                    "bcm_status": 1.0,            # BCM healthy 0-1
                    "interior_lights_error": 0.0, # Error flag
                    "wiper_error": 0.0,           # Error flag
                    "accessory_power_error": 0.0, # Error flag
                    "key_off_current": 0.030,     # Normal parasitic (A)
                    "battery_voltage_overnight": 0.0, # Drop (V)
                    "battery_state_of_charge": 1.0, # SOC 0-1
                    "relay_state_error": 0.0,     # Error flag
                    "controlled_circuit_status": 1.0, # Healthy 0-1
                    "relay_coil_resistance": 75.0, # Normal ohms
                    
                    # --- HYBRID SYSTEM ---
                    "hv_battery_soc_max": 1.0,    # Max SOC achievable 0-1
                    "hv_battery_capacity": 1.0,   # Capacity ratio 0-1
                    "ev_range_estimate": 1.0,     # Range ratio 0-1
                    "hv_battery_temp": 30.0,      # Normal temp (°C)
                    "cell_voltage_variance": 0.0, # Cell imbalance (V)
                    "inverter_temp": 50.0,        # Normal temp (°C)
                    "hv_system_lamp": 0.0,        # Warning light
                    "electric_motor_available": 1.0, # Available 0-1
                    "regenerative_braking": 1.0,  # Available 0-1
                    "hv_coolant_flow": 1.0,       # Flow ratio 0-1
                    "power_limit_active": 0.0,    # Power limited flag
                    "aux_battery_voltage": 12.6,  # 12V battery (V)
                    "aux_battery_cca": 1.0,       # CCA ratio 0-1
                    "ready_light_delay": 0.0,     # Delay to ready (s)
                    
                    # --- EV SYSTEM ---
                    "charge_port_status": 1.0,    # Port healthy 0-1
                    "charge_pilot_signal": 1.0,   # Signal present 0-1
                    "charge_session_error": 0.0,  # Error flag
                    "ac_charge_power": 7.2,       # AC charge rate (kW)
                    "charger_temp": 40.0,         # Charger temp (°C)
                    "charge_rate_ac": 7.2,        # AC rate (kW)
                    "dcdc_output_voltage": 14.2,  # DC-DC output (V)
                    "dcdc_status": 1.0,           # Healthy 0-1
                    
                    # --- ADDITIONAL BRAKES ---
                    "brake_temp_fl": 200.0,       # FL brake temp (°F)
                    "brake_drag": 0.0,            # Drag indicator
                    "fuel_economy_loss": 0.0,     # MPG loss
                    "wheel_pull": 0.0,            # Pull direction
                    "brake_pressure": 1.0,        # Pressure ratio 0-1
                    "brake_fluid_level": 1.0,     # Level ratio 0-1
                    "brake_vibration": 0.0,       # Vibration level
                    "steering_wheel_shake": 0.0,  # Shake level
                    "rotor_runout": 0.0,          # Runout (inches)
                    
                    # --- ADDITIONAL STARTING ---
                    "starter_engage_time": 0.0,   # Engage delay (s)
                    "solenoid_click": 1.0,        # Click + crank 0-1
                    "starting_current": 200.0,    # Normal draw (A)
                    "gear_position_signal": 1.0,  # Signal present 0-1
                    "starter_enable": 1.0,        # Enabled 0-1
                    "shift_indicator_error": 0.0, # Error flag
                }
                
                # Apply sensor biases/noise from fault injection
                modified_sensors = injector.modify_outputs(raw_sensors, time)
                
                # Add some realistic noise
                for key in ["rpm", "engine_torque_nm", "engine_load"]:
                    if key in modified_sensors:
                        modified_sensors[key] += random.gauss(0, modified_sensors[key] * 0.02)
                
                # Record timestep
                reading = {"t": round(time, 2)}
                reading.update({k: round(v, 2) for k, v in modified_sensors.items()})
                time_series.append(reading)
        
        # Build result
        result = SimulationResult(
            failure_mode_id=config.failure_mode_id,
            failure_mode_name=config.failure_mode_name,
            vehicle=config.vehicle_type,
            severity=config.severity,
            scenario=config.scenario,
            conditions={
                "ambient_temp": config.ambient_temp,
                "road_surface": config.road_surface,
            },
            time_series=time_series,
            metadata={
                "simulator": "pychrono",
                "version": "8.0.0",
                "generated": datetime.now().isoformat(),
                "step_size": step_size,
                "sample_interval": sample_interval,
            }
        )
        
        return result
    
    def generate_configs(self, count_per_failure: int = 10) -> List[SimulationConfig]:
        """Generate simulation configurations for all failure modes."""
        configs = []
        
        for sim in get_all_simulations():
            # Generate the requested number of variations (ignore sim.n_variations cap)
            for i in range(count_per_failure):
                # Random severity within range
                severity = random.uniform(*sim.severity_range)
                
                # Random scenario
                scenario = random.choice(list(self.SCENARIOS.keys()))
                
                # Random vehicle
                vehicle = random.choice(self.VEHICLES)
                
                # Random conditions
                ambient_temp = random.uniform(40, 100)  # 40-100°F
                road_surface = random.choice(["asphalt", "concrete", "gravel"])
                
                config = SimulationConfig(
                    failure_mode_id=sim.failure_mode_id,
                    failure_mode_name=sim.failure_mode_name,
                    vehicle_type=vehicle,
                    severity=round(severity, 3),
                    duration=30.0,
                    scenario=scenario,
                    ambient_temp=round(ambient_temp, 1),
                    road_surface=road_surface,
                )
                configs.append(config)
        
        return configs
    
    def save_result(self, result: SimulationResult, index: int) -> str:
        """Save a simulation result to JSON file."""
        # Create filename
        safe_id = result.failure_mode_id.replace(".", "_")
        filename = f"{safe_id}_{index:04d}.json"
        filepath = self.output_dir / filename
        
        # Convert to dict
        data = {
            "failure_mode_id": result.failure_mode_id,
            "failure_mode_name": result.failure_mode_name,
            "vehicle": result.vehicle,
            "severity": result.severity,
            "scenario": result.scenario,
            "conditions": result.conditions,
            "time_series": result.time_series,
            "metadata": result.metadata,
        }
        
        # Save
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Add to manifest
        self.manifest.append({
            "file": filename,
            "failure_mode_id": result.failure_mode_id,
            "failure_mode_name": result.failure_mode_name,
            "vehicle": result.vehicle,
            "severity": result.severity,
            "scenario": result.scenario,
            "n_samples": len(result.time_series),
        })
        
        return filename
    
    def save_manifest(self):
        """Save manifest CSV with all generated files."""
        manifest_path = self.output_dir / "manifest.csv"
        
        if self.manifest:
            with open(manifest_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.manifest[0].keys())
                writer.writeheader()
                writer.writerows(self.manifest)
        
        self.log(f"Saved manifest: {manifest_path}")
    
    def get_existing_counts(self) -> Dict[str, int]:
        """Count existing files per failure mode for resume capability."""
        counts = {}
        for f in self.output_dir.glob("*.json"):
            # Parse failure_mode_id from filename (e.g., "fuel_vacuum_leak_0001.json")
            parts = f.stem.rsplit("_", 1)  # Split off the index
            if len(parts) == 2 and parts[1].isdigit():
                # Reconstruct the failure_mode_id (convert underscores back to dots)
                # e.g., "fuel_vacuum_leak" -> "fuel.vacuum_leak"  
                name_parts = parts[0].split("_", 1)
                if len(name_parts) == 2:
                    failure_id = f"{name_parts[0]}.{name_parts[1]}"
                    counts[failure_id] = counts.get(failure_id, 0) + 1
        return counts
    
    def generate_batch(self, total_count: int = 1000, resume: bool = True):
        """Generate a batch of training data.
        
        Args:
            total_count: Target number of scenarios to generate
            resume: If True, skip failure modes that already have enough files
        """
        
        self.log(f"=" * 60)
        self.log(f"Batch Generator - Synthetic Diagnostic Training Data")
        self.log(f"=" * 60)
        self.log(f"Output directory: {self.output_dir}")
        self.log(f"Target count: {total_count}")
        self.log(f"Resume mode: {resume}")
        
        # Calculate how many per failure mode
        n_failures = len(get_all_simulations())
        count_per_failure = max(1, total_count // n_failures)
        actual_total = count_per_failure * n_failures
        
        self.log(f"Failure modes: {n_failures}")
        self.log(f"Scenarios per failure: {count_per_failure}")
        self.log(f"Actual total: {actual_total}")
        
        # Check for existing files if resuming
        existing_counts = {}
        if resume:
            existing_counts = self.get_existing_counts()
            total_existing = sum(existing_counts.values())
            self.log(f"Existing files found: {total_existing}")
            if total_existing > 0:
                self.log(f"Will skip already-generated scenarios")
        self.log(f"")
        
        # Generate configs
        configs = self.generate_configs(count_per_failure)
        random.shuffle(configs)  # Randomize order
        
        # Track progress
        counters = {}  # failure_mode_id -> count (for this run)
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        self.log(f"Starting generation...")
        self.log(f"-" * 60)
        
        for i, config in enumerate(configs):
            # Track per-failure count
            if config.failure_mode_id not in counters:
                counters[config.failure_mode_id] = 0
            counters[config.failure_mode_id] += 1
            
            # Calculate actual index including existing files
            existing = existing_counts.get(config.failure_mode_id, 0)
            idx = existing + counters[config.failure_mode_id]
            
            # Skip if we already have enough for this failure mode
            if resume and existing >= count_per_failure:
                skipped_count += 1
                continue
            
            try:
                # Run simulation
                result = self.run_simulation(config)
                
                # Save result
                filename = self.save_result(result, idx)
                success_count += 1
                
                # Progress update
                if (i + 1) % 10 == 0 or i == 0:
                    self.log(f"[{i+1}/{len(configs)}] {config.failure_mode_id} "
                            f"(severity={config.severity:.2f}, {config.scenario}) -> {filename}")
                    
            except Exception as e:
                error_count += 1
                self.log(f"[{i+1}/{len(configs)}] ERROR: {config.failure_mode_id} - {e}")
        
        # Save manifest
        self.save_manifest()
        
        # Summary
        self.log(f"")
        self.log(f"=" * 60)
        self.log(f"COMPLETE!")
        self.log(f"=" * 60)
        self.log(f"Success: {success_count}")
        self.log(f"Skipped (already existed): {skipped_count}")
        self.log(f"Errors: {error_count}")
        self.log(f"Output: {self.output_dir}")
        self.log(f"Manifest: {self.output_dir / 'manifest.csv'}")
        
        # Per-failure breakdown
        self.log(f"")
        self.log(f"Per-failure counts:")
        for fid, count in sorted(counters.items()):
            self.log(f"  {fid}: {count}")
        
        return success_count


def _run_single_simulation(args: Tuple) -> Tuple[bool, str, Optional[Dict]]:
    """Worker function for multiprocessing - runs a single simulation.
    
    Returns (success, message, manifest_entry)
    """
    config_dict, output_dir, idx = args
    
    try:
        # Reconstruct config from dict
        config = SimulationConfig(**config_dict)
        
        # Create a generator instance for this worker
        generator = BatchGenerator(output_dir, verbose=False)
        
        # Run simulation
        result = generator.run_simulation(config)
        
        # Save result
        filename = generator.save_result(result, idx)
        
        manifest_entry = {
            "file": filename,
            "failure_mode_id": result.failure_mode_id,
            "failure_mode_name": result.failure_mode_name,
            "vehicle": result.vehicle,
            "severity": result.severity,
            "scenario": result.scenario,
            "n_samples": len(result.time_series),
        }
        
        return (True, f"{config.failure_mode_id} (severity={config.severity:.2f}, {config.scenario}) -> {filename}", manifest_entry)
        
    except Exception as e:
        return (False, f"ERROR: {config_dict.get('failure_mode_id', 'unknown')} - {e}", None)


class BatchGeneratorMP(BatchGenerator):
    """Multiprocessing-enabled batch generator."""
    
    def generate_batch_parallel(self, total_count: int = 1000, workers: int = 4, resume: bool = True):
        """Generate a batch of training data using multiprocessing.
        
        Args:
            total_count: Target number of scenarios to generate
            workers: Number of parallel workers
            resume: If True, skip failure modes that already have enough files
        """
        
        self.log(f"=" * 60)
        self.log(f"Batch Generator - Parallel Mode ({workers} workers)")
        self.log(f"=" * 60)
        self.log(f"Output directory: {self.output_dir}")
        self.log(f"Target count: {total_count}")
        self.log(f"Resume mode: {resume}")
        
        # Calculate how many per failure mode
        n_failures = len(get_all_simulations())
        count_per_failure = max(1, total_count // n_failures)
        actual_total = count_per_failure * n_failures
        
        self.log(f"Failure modes: {n_failures}")
        self.log(f"Scenarios per failure: {count_per_failure}")
        self.log(f"Actual total: {actual_total}")
        
        # Check for existing files if resuming
        existing_counts = {}
        if resume:
            existing_counts = self.get_existing_counts()
            total_existing = sum(existing_counts.values())
            self.log(f"Existing files found: {total_existing}")
            if total_existing > 0:
                self.log(f"Will skip already-generated scenarios")
        self.log(f"")
        
        # Generate configs
        configs = self.generate_configs(count_per_failure)
        random.shuffle(configs)
        
        # Build work queue - filter out already completed
        work_queue = []
        counters = {}
        skipped_count = 0
        
        for config in configs:
            if config.failure_mode_id not in counters:
                counters[config.failure_mode_id] = 0
            counters[config.failure_mode_id] += 1
            
            existing = existing_counts.get(config.failure_mode_id, 0)
            idx = existing + counters[config.failure_mode_id]
            
            if resume and existing >= count_per_failure:
                skipped_count += 1
                continue
            
            # Convert config to dict for pickling
            config_dict = asdict(config)
            work_queue.append((config_dict, str(self.output_dir), idx))
        
        self.log(f"Work queue: {len(work_queue)} simulations")
        self.log(f"Skipped (already existed): {skipped_count}")
        self.log(f"Starting parallel generation with {workers} workers...")
        self.log(f"-" * 60)
        
        # Run with multiprocessing pool
        success_count = 0
        error_count = 0
        all_manifest_entries = []
        
        with mp.Pool(processes=workers) as pool:
            results = pool.imap_unordered(_run_single_simulation, work_queue)
            
            for i, (success, msg, manifest_entry) in enumerate(results):
                if success:
                    success_count += 1
                    if manifest_entry:
                        all_manifest_entries.append(manifest_entry)
                else:
                    error_count += 1
                
                # Progress update every 10 or at key intervals
                if (i + 1) % 10 == 0 or i == 0 or (i + 1) == len(work_queue):
                    self.log(f"[{i+1}/{len(work_queue)}] {msg}")
        
        # Save combined manifest
        self.manifest = all_manifest_entries
        self.save_manifest()
        
        # Summary
        self.log(f"")
        self.log(f"=" * 60)
        self.log(f"COMPLETE!")
        self.log(f"=" * 60)
        self.log(f"Success: {success_count}")
        self.log(f"Skipped (already existed): {skipped_count}")
        self.log(f"Errors: {error_count}")
        self.log(f"Output: {self.output_dir}")
        self.log(f"Manifest: {self.output_dir / 'manifest.csv'}")
        
        return success_count


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic diagnostic training data")
    parser.add_argument("--count", type=int, default=100, 
                       help="Total number of scenarios to generate")
    parser.add_argument("--output", type=str, 
                       default="../training_data/chrono_synthetic",
                       help="Output directory")
    parser.add_argument("--workers", type=int, default=1,
                       help="Number of parallel workers (default: 1 = single process)")
    parser.add_argument("--quiet", action="store_true",
                       help="Suppress progress output")
    parser.add_argument("--no-resume", action="store_true",
                       help="Don't skip existing files, regenerate all")
    args = parser.parse_args()
    
    # Resolve output path relative to this script
    script_dir = Path(__file__).parent
    output_dir = script_dir / args.output
    
    # Generate - use parallel version if workers > 1
    if args.workers > 1:
        generator = BatchGeneratorMP(output_dir, verbose=not args.quiet)
        generator.generate_batch_parallel(args.count, workers=args.workers, resume=not args.no_resume)
    else:
        generator = BatchGenerator(output_dir, verbose=not args.quiet)
        generator.generate_batch(args.count, resume=not args.no_resume)


if __name__ == "__main__":
    main()
