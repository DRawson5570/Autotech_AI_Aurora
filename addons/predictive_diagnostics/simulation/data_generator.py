"""
Training data generator for ML model.

Generates diverse training samples by:
1. Simulating each failure mode under various conditions
2. Simulating normal operation for contrast
3. Adding realistic noise and variation
4. Producing labeled datasets for supervised learning
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Iterator
import random
import json
from pathlib import Path

from .engine import SimulationEngine, SimulationConfig, OperatingCondition, SimulationResult
from .thermal import CoolingSystemSimulator
from ..knowledge.failures import get_failure_modes_for_system, get_all_failure_modes


@dataclass
class DataGeneratorConfig:
    """Configuration for training data generation."""
    
    # Number of samples per failure mode
    samples_per_failure: int = 50
    
    # Number of normal (no failure) samples
    normal_samples: int = 100
    
    # Simulation duration range (seconds)
    min_duration: float = 120.0   # 2 minutes
    max_duration: float = 600.0   # 10 minutes
    
    # Operating conditions to simulate
    operating_conditions: List[OperatingCondition] = field(default_factory=lambda: [
        OperatingCondition.COLD_START,
        OperatingCondition.IDLE,
        OperatingCondition.CITY_DRIVING,
        OperatingCondition.HIGHWAY,
        OperatingCondition.HEAVY_LOAD,
        OperatingCondition.HOT_AMBIENT,
    ])
    
    # Ambient temperature range (°C)
    min_ambient_temp: float = -10.0
    max_ambient_temp: float = 40.0
    
    # Failure severity range (for partial failures)
    min_severity: float = 0.5
    max_severity: float = 1.0
    
    # Noise settings
    add_noise: bool = True
    noise_level_range: tuple = (0.01, 0.05)  # 1-5% noise
    
    # Output settings
    output_format: str = "json"  # "json" or "numpy"


class TrainingDataGenerator:
    """
    Generates training data for the diagnostic ML model.
    
    Creates a diverse dataset of simulated failures and normal operation
    suitable for training a model to recognize failure patterns.
    """
    
    def __init__(self, config: Optional[DataGeneratorConfig] = None):
        self.config = config or DataGeneratorConfig()
        
        # Initialize simulation engine
        self.engine = SimulationEngine()
        
        # Register simulators for all systems
        self.engine.register_simulator("cooling", CoolingSystemSimulator())
        
        # Register multi-system simulators
        try:
            from .multi_system_simulator import (
                FuelSystemSimulator,
                IgnitionSystemSimulator,
                ChargingSystemSimulator,
                TransmissionSystemSimulator,
                BrakingSystemSimulator,
                EngineSystemSimulator,
                SteeringSystemSimulator,
                SuspensionSystemSimulator,
                HVACSystemSimulator,
                EmissionsSystemSimulator,
            )
            self.engine.register_simulator("fuel", FuelSystemSimulator())
            self.engine.register_simulator("ignition", IgnitionSystemSimulator())
            self.engine.register_simulator("charging", ChargingSystemSimulator())
            self.engine.register_simulator("transmission", TransmissionSystemSimulator())
            self.engine.register_simulator("brakes", BrakingSystemSimulator())
            self.engine.register_simulator("engine", EngineSystemSimulator())
            self.engine.register_simulator("steering", SteeringSystemSimulator())
            self.engine.register_simulator("suspension", SuspensionSystemSimulator())
            self.engine.register_simulator("hvac", HVACSystemSimulator())
            self.engine.register_simulator("emissions", EmissionsSystemSimulator())
        except ImportError as e:
            print(f"Warning: Some simulators not available: {e}")
    
    def generate_sample(self, system_id: str, failure_id: Optional[str],
                        operating_condition: Optional[OperatingCondition] = None,
                        ambient_temp: Optional[float] = None,
                        duration: Optional[float] = None,
                        severity: Optional[float] = None) -> SimulationResult:
        """
        Generate a single training sample.
        
        Args:
            system_id: System to simulate
            failure_id: Failure to inject (None for normal operation)
            operating_condition: Condition to simulate (random if None)
            ambient_temp: Ambient temperature (random if None)
            duration: Simulation duration (random if None)
            severity: Failure severity (random if None)
            
        Returns:
            SimulationResult that can be converted to training data
        """
        cfg = self.config
        
        # Randomize parameters if not specified
        if operating_condition is None:
            operating_condition = random.choice(cfg.operating_conditions)
        
        if ambient_temp is None:
            ambient_temp = random.uniform(cfg.min_ambient_temp, cfg.max_ambient_temp)
        
        if duration is None:
            duration = random.uniform(cfg.min_duration, cfg.max_duration)
        
        if severity is None and failure_id:
            severity = random.uniform(cfg.min_severity, cfg.max_severity)
        
        noise_level = random.uniform(*cfg.noise_level_range) if cfg.add_noise else 0.0
        
        # Create simulation config
        sim_config = SimulationConfig(
            duration_seconds=duration,
            time_step=1.0,
            operating_condition=operating_condition,
            ambient_temp_c=ambient_temp,
            add_noise=cfg.add_noise,
            noise_level=noise_level,
            failure_id=failure_id,
            failure_severity=severity or 1.0,
            failure_onset_time=0.0,  # Failure present from start
        )
        
        # Run simulation
        result = self.engine.run(system_id, sim_config)
        
        return result
    
    def generate_dataset_for_system(self, system_id: str) -> List[Dict[str, Any]]:
        """
        Generate full training dataset for a system.
        
        Returns list of training samples as dictionaries.
        """
        cfg = self.config
        samples = []
        
        # Get all failure modes for this system
        failures = get_failure_modes_for_system(system_id)
        
        print(f"Generating data for {system_id} system...")
        print(f"  - {len(failures)} failure modes")
        print(f"  - {cfg.samples_per_failure} samples per failure")
        print(f"  - {cfg.normal_samples} normal samples")
        
        # Generate failure samples
        for failure in failures:
            print(f"  Generating {cfg.samples_per_failure} samples for: {failure.id}")
            for i in range(cfg.samples_per_failure):
                try:
                    result = self.generate_sample(system_id, failure.id)
                    sample = result.to_training_sample()
                    sample["label"] = failure.id
                    sample["is_failure"] = True
                    samples.append(sample)
                except Exception as e:
                    print(f"    Warning: Failed to generate sample: {e}")
        
        # Generate normal samples
        print(f"  Generating {cfg.normal_samples} normal samples")
        for i in range(cfg.normal_samples):
            try:
                result = self.generate_sample(system_id, None)
                sample = result.to_training_sample()
                sample["label"] = "normal"
                sample["is_failure"] = False
                samples.append(sample)
            except Exception as e:
                print(f"    Warning: Failed to generate sample: {e}")
        
        print(f"  Generated {len(samples)} total samples")
        return samples
    
    def generate_all_datasets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate datasets for all registered systems."""
        datasets = {}
        
        for system_id in self.engine._simulators.keys():
            datasets[system_id] = self.generate_dataset_for_system(system_id)
        
        return datasets
    
    def save_dataset(self, samples: List[Dict[str, Any]], 
                     output_path: str, format: str = "json") -> None:
        """
        Save dataset to file.
        
        Args:
            samples: List of training samples
            output_path: Path to save file
            format: "json" or "jsonl" (JSON lines)
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(path, 'w') as f:
                json.dump(samples, f, indent=2)
        elif format == "jsonl":
            with open(path, 'w') as f:
                for sample in samples:
                    f.write(json.dumps(sample) + '\n')
        else:
            raise ValueError(f"Unknown format: {format}")
        
        print(f"Saved {len(samples)} samples to {path}")
    
    def stream_samples(self, system_id: str, 
                       n_samples: int) -> Iterator[Dict[str, Any]]:
        """
        Stream training samples one at a time (memory efficient).
        
        Yields random mix of failure and normal samples.
        """
        failures = get_failure_modes_for_system(system_id)
        failure_ids = [f.id for f in failures] + [None]  # Include normal
        
        for _ in range(n_samples):
            failure_id = random.choice(failure_ids)
            result = self.generate_sample(system_id, failure_id)
            sample = result.to_training_sample()
            sample["label"] = failure_id or "normal"
            sample["is_failure"] = failure_id is not None
            yield sample


# ==============================================================================
# QUICK GENERATION FUNCTIONS
# ==============================================================================

def generate_cooling_dataset(n_per_failure: int = 50, 
                              n_normal: int = 100,
                              output_path: Optional[str] = None) -> List[Dict]:
    """
    Quick function to generate cooling system dataset.
    
    Args:
        n_per_failure: Samples per failure mode
        n_normal: Normal operation samples
        output_path: Optional path to save dataset
        
    Returns:
        List of training samples
    """
    config = DataGeneratorConfig(
        samples_per_failure=n_per_failure,
        normal_samples=n_normal,
    )
    
    generator = TrainingDataGenerator(config)
    samples = generator.generate_dataset_for_system("cooling")
    
    if output_path:
        generator.save_dataset(samples, output_path)
    
    return samples


def visualize_simulation(result: SimulationResult) -> str:
    """
    Create a text-based visualization of simulation results.
    
    Returns ASCII chart showing temperature evolution.
    """
    times = result.get_times()
    temps = result.get_variable_series("coolant_temp")
    
    if not temps:
        return "No data to visualize"
    
    # Normalize to chart height
    min_temp = min(temps)
    max_temp = max(temps)
    height = 20
    width = min(len(temps), 60)
    
    # Sample if too many points
    step = max(1, len(temps) // width)
    sampled_temps = temps[::step][:width]
    sampled_times = times[::step][:width]
    
    # Build chart
    lines = []
    lines.append(f"Coolant Temperature (failure: {result.failure_id or 'None'})")
    lines.append(f"DTCs: {result.triggered_dtcs or 'None'}")
    lines.append("")
    
    for row in range(height, -1, -1):
        threshold = min_temp + (max_temp - min_temp) * row / height
        line = f"{threshold:6.1f}°C |"
        for temp in sampled_temps:
            if temp >= threshold:
                line += "*"
            else:
                line += " "
        lines.append(line)
    
    # X-axis
    lines.append("        +" + "-" * len(sampled_temps))
    lines.append(f"         0s{' ' * (len(sampled_temps) - 10)}{sampled_times[-1]:.0f}s")
    
    return "\n".join(lines)
