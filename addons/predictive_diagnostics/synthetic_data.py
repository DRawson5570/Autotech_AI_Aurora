"""
Synthetic Data Generator

Generates synthetic training examples for the RF classifier.

TWO APPROACHES (both available):
1. PHYSICS-BASED (NEW): Uses PhysicsSimulator to generate realistic PID patterns
   - Based on actual physics of automotive systems
   - "IF thermostat stuck open THEN coolant won't reach operating temp"
   - More accurate for failure mode recognition

2. FAULT-TREE-BASED (LEGACY): Uses fault tree + signatures
   - Good for generating data when physics model not available
   - Uses signatures to apply effects

Benefits:
- Don't need to wait for real failures to train
- Can generate rare failure cases
- Control over class balance
- Augment limited real data
"""

import random
import logging
import json
import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime

# Import physics simulator (for new approach)
try:
    from .physics_simulator import PhysicsSimulator, SimulationConfig
except ImportError:
    try:
        from physics_simulator import PhysicsSimulator, SimulationConfig
    except ImportError:
        PhysicsSimulator = None
        SimulationConfig = None

# Import fault tree stuff (for legacy approach)
_have_fault_tree = False
try:
    from .fault_tree import FaultTree, FaultNode, Component
    from .taxonomy import ComponentType
    from .signatures import (
        FailureSignature, 
        SignalPattern, 
        PatternType,
        FAILURE_SIGNATURES,
        get_signature
    )
    _have_fault_tree = True
except ImportError:
    try:
        from fault_tree import FaultTree, FaultNode, Component
        from taxonomy import ComponentType
        from signatures import (
            FailureSignature,
            SignalPattern,
            PatternType,
            FAILURE_SIGNATURES,
            get_signature
        )
        _have_fault_tree = True
    except ImportError:
        FaultTree = None
        FaultNode = None
        SignalPattern = None
        PatternType = None
        get_signature = None

try:
    from .classifier import TrainingExample, COMMON_PID_FEATURES, PIDFeature
except ImportError:
    from classifier import TrainingExample, COMMON_PID_FEATURES, PIDFeature

logger = logging.getLogger(__name__)


# =============================================================================
# PHYSICS-BASED DATA GENERATION (NEW APPROACH)
# =============================================================================

# Failure modes supported by physics simulator
PHYSICS_FAILURE_MODES = {
    "cooling": [
        "thermostat_stuck_open",
        "thermostat_stuck_closed",
        "water_pump_failure",
        "cooling_fan_failure",
        "coolant_leak",
    ],
    "fuel": [
        "fuel_pump_weak",
        "fuel_pressure_regulator_failure",
        "vacuum_leak",
        "injector_clogged",
        "injector_leaking",
        "maf_sensor_dirty",
    ],
    "o2_sensor": [
        "o2_sensor_stuck_lean",
        "o2_sensor_stuck_rich",
        "o2_sensor_lazy",
    ],
    "electrical": [
        "alternator_failure",
        "voltage_regulator_failure",
        "battery_weak",
    ],
    "intake": [
        "maf_sensor_failure",
        "air_filter_clogged",
        "pcv_valve_stuck_open",
        "iat_sensor_failure",
    ],
    "ignition": [
        "knock_sensor_failure",
    ],
    "normal": [
        "normal",
    ],
}


@dataclass
class PhysicsDataConfig:
    """Configuration for physics-based data generation."""
    samples_per_class: int = 100
    duration_range: Tuple[float, float] = (180, 600)     # 3-10 minutes
    ambient_temp_range: Tuple[float, float] = (40, 95)   # °F
    noise_range: Tuple[float, float] = (0.01, 0.05)      # 1-5%
    idle_probability: float = 0.2
    highway_probability: float = 0.3
    output_dir: str = "training_data"
    random_seed: Optional[int] = 42


class PhysicsBasedGenerator:
    """
    Generates training data using physics simulator.
    
    This is the NEW approach - uses actual physics models to generate
    realistic PID patterns for each failure mode.
    """
    
    def __init__(self, config: PhysicsDataConfig = None):
        if PhysicsSimulator is None:
            raise ImportError("physics_simulator module required for PhysicsBasedGenerator")
        
        self.config = config or PhysicsDataConfig()
        if self.config.random_seed:
            random.seed(self.config.random_seed)
            np.random.seed(self.config.random_seed)
        
        self.simulator = PhysicsSimulator()
        self._feature_names: List[str] = None
    
    def generate_sample(self, failure_mode: str) -> Dict[str, float]:
        """Generate a single training sample for a failure mode."""
        sim_config = SimulationConfig(
            duration_sec=random.uniform(*self.config.duration_range),
            ambient_temp_f=random.uniform(*self.config.ambient_temp_range),
            initial_coolant_f=random.uniform(*self.config.ambient_temp_range),
            noise_level=random.uniform(*self.config.noise_range),
        )
        
        # Random driving profile
        roll = random.random()
        if roll < self.config.idle_probability:
            sim_config.idle_only = True
        elif roll < self.config.idle_probability + self.config.highway_probability:
            sim_config.highway_cruise = True
        
        # Run simulation
        pid_series = self.simulator.simulate_failure(failure_mode, sim_config)
        
        # Extract features
        features = self.simulator.extract_features(pid_series)
        
        # Add metadata
        features["sim_duration"] = sim_config.duration_sec
        features["sim_ambient_temp"] = sim_config.ambient_temp_f
        features["sim_idle_only"] = float(sim_config.idle_only)
        features["sim_highway"] = float(sim_config.highway_cruise)
        
        return features
    
    def get_all_failure_modes(self) -> List[str]:
        """Get list of all failure modes supported by physics simulator."""
        modes = []
        for group_modes in PHYSICS_FAILURE_MODES.values():
            modes.extend(group_modes)
        return modes
    
    def generate_dataset(
        self,
        samples_per_class: int = None,
        failure_modes: List[str] = None,
        verbose: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """
        Generate complete training dataset.
        
        Returns:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - integer encoded
            feature_names: List of feature names
            class_names: List of failure mode names (label decoder)
        """
        samples_per_class = samples_per_class or self.config.samples_per_class
        
        if failure_modes is None:
            failure_modes = self.get_all_failure_modes()
        
        all_samples = []
        all_labels = []
        
        for mode_idx, mode in enumerate(failure_modes):
            if verbose:
                print(f"Generating {samples_per_class} samples for: {mode}")
            
            for i in range(samples_per_class):
                try:
                    features = self.generate_sample(mode)
                    all_samples.append(features)
                    all_labels.append(mode_idx)
                    
                    if verbose and (i + 1) % 25 == 0:
                        print(f"  ... {i + 1}/{samples_per_class}")
                except Exception as e:
                    logger.error(f"Error generating sample {i} for {mode}: {e}")
        
        if not all_samples:
            raise ValueError("No samples generated!")
        
        # Consistent feature ordering
        feature_names = sorted(all_samples[0].keys())
        self._feature_names = feature_names
        
        # Build feature matrix
        X = np.zeros((len(all_samples), len(feature_names)))
        for i, sample in enumerate(all_samples):
            for j, fname in enumerate(feature_names):
                X[i, j] = sample.get(fname, 0.0)
        
        y = np.array(all_labels)
        
        if verbose:
            print(f"\nGenerated dataset: {X.shape[0]} samples, {X.shape[1]} features, {len(failure_modes)} classes")
        
        return X, y, feature_names, failure_modes
    
    def save_dataset(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        class_names: List[str],
        output_dir: str = None,
    ) -> str:
        """Save generated dataset to disk."""
        output_dir = output_dir or self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save numpy arrays
        np.save(os.path.join(output_dir, f"X_{timestamp}.npy"), X)
        np.save(os.path.join(output_dir, f"y_{timestamp}.npy"), y)
        
        # Save metadata
        metadata = {
            "timestamp": timestamp,
            "n_samples": len(y),
            "n_features": len(feature_names),
            "n_classes": len(class_names),
            "feature_names": feature_names,
            "class_names": class_names,
            "config": {
                "samples_per_class": self.config.samples_per_class,
                "duration_range": self.config.duration_range,
                "ambient_temp_range": self.config.ambient_temp_range,
                "noise_range": self.config.noise_range,
            }
        }
        
        with open(os.path.join(output_dir, f"metadata_{timestamp}.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Save "latest" versions
        np.save(os.path.join(output_dir, "X_latest.npy"), X)
        np.save(os.path.join(output_dir, "y_latest.npy"), y)
        with open(os.path.join(output_dir, "metadata_latest.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Dataset saved to {output_dir}/ ({len(y)} samples)")
        return output_dir
    
    @staticmethod
    def load_dataset(
        data_dir: str,
        timestamp: str = "latest",
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """Load dataset from disk."""
        X = np.load(os.path.join(data_dir, f"X_{timestamp}.npy"))
        y = np.load(os.path.join(data_dir, f"y_{timestamp}.npy"))
        
        with open(os.path.join(data_dir, f"metadata_{timestamp}.json")) as f:
            metadata = json.load(f)
        
        return X, y, metadata["feature_names"], metadata["class_names"]


# =============================================================================
# FAULT-TREE-BASED DATA GENERATION (LEGACY APPROACH)
# =============================================================================


@dataclass
class SystemProfile:
    """
    Defines normal operating characteristics for a vehicle system.
    Used to generate realistic "normal" PID values.
    """
    system_name: str
    baseline_pids: Dict[str, Tuple[float, float]]  # PID -> (mean, std_dev)
    correlated_pids: List[Tuple[str, str, float]]  # (pid1, pid2, correlation)
    common_dtcs: List[str] = None
    
    def sample_normal(self) -> Dict[str, float]:
        """Sample normal PID values for this system."""
        values = {}
        for pid, (mean, std) in self.baseline_pids.items():
            # Sample from normal distribution
            value = np.random.normal(mean, std)
            
            # Clamp to valid range
            if pid in COMMON_PID_FEATURES:
                feature = COMMON_PID_FEATURES[pid]
                value = max(feature.min_value, min(feature.max_value, value))
            
            values[pid] = value
        
        return values


# Pre-defined system profiles
SYSTEM_PROFILES: Dict[str, SystemProfile] = {
    "engine_idle": SystemProfile(
        system_name="Engine at Idle",
        baseline_pids={
            "ENGINE_RPM": (750, 50),
            "COOLANT_TEMP": (90, 5),
            "INTAKE_AIR_TEMP": (30, 10),
            "MAP": (35, 5),
            "THROTTLE_POS": (5, 2),
            "VEHICLE_SPEED": (0, 0),
            "SHORT_FUEL_TRIM_1": (0, 3),
            "LONG_FUEL_TRIM_1": (0, 5),
            "O2_VOLTAGE_B1S1": (0.45, 0.3),
            "MAF": (3, 0.5),
            "TIMING_ADVANCE": (15, 5),
            "CONTROL_MODULE_VOLTAGE": (14.2, 0.3),
        },
        correlated_pids=[
            ("ENGINE_RPM", "MAP", 0.3),
            ("COOLANT_TEMP", "INTAKE_AIR_TEMP", 0.2),
        ],
    ),
    "engine_cruise": SystemProfile(
        system_name="Engine at Cruise",
        baseline_pids={
            "ENGINE_RPM": (2500, 200),
            "COOLANT_TEMP": (95, 3),
            "INTAKE_AIR_TEMP": (40, 10),
            "MAP": (70, 10),
            "THROTTLE_POS": (25, 5),
            "VEHICLE_SPEED": (100, 10),
            "SHORT_FUEL_TRIM_1": (0, 2),
            "LONG_FUEL_TRIM_1": (0, 4),
            "O2_VOLTAGE_B1S1": (0.45, 0.3),
            "MAF": (25, 5),
            "TIMING_ADVANCE": (25, 5),
            "CONTROL_MODULE_VOLTAGE": (14.4, 0.2),
        },
        correlated_pids=[
            ("ENGINE_RPM", "MAF", 0.8),
            ("THROTTLE_POS", "MAP", 0.7),
            ("VEHICLE_SPEED", "ENGINE_RPM", 0.6),
        ],
    ),
    "ev_driving": SystemProfile(
        system_name="EV Driving",
        baseline_pids={
            "BATTERY_SOC": (70, 20),
            "BATTERY_VOLTAGE": (380, 20),
            "BATTERY_CURRENT": (50, 100),
            "BATTERY_TEMP": (30, 5),
            "MOTOR_TEMP": (50, 15),
            "INVERTER_TEMP": (45, 10),
            "VEHICLE_SPEED": (60, 30),
        },
        correlated_pids=[
            ("BATTERY_CURRENT", "VEHICLE_SPEED", 0.5),
            ("BATTERY_TEMP", "MOTOR_TEMP", 0.4),
        ],
    ),
}


class SyntheticDataGenerator:
    """
    Generates synthetic training data from fault trees.
    """
    
    def __init__(
        self,
        noise_level: float = 0.1,
        include_normal_ratio: float = 0.2,  # Fraction of "normal" examples
        random_seed: int = None
    ):
        """
        Initialize the generator.
        
        Args:
            noise_level: Amount of random noise to add (0-1)
            include_normal_ratio: Fraction of examples that are "no fault"
            random_seed: Seed for reproducibility
        """
        self.noise_level = noise_level
        self.include_normal_ratio = include_normal_ratio
        
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)
        
        self._example_counter = 0
    
    def _generate_example_id(self) -> str:
        """Generate unique example ID."""
        self._example_counter += 1
        return f"synth_{self._example_counter:06d}"
    
    def _apply_fault_effects(
        self,
        base_pids: Dict[str, float],
        fault_node: FaultNode,
    ) -> Tuple[Dict[str, float], List[str]]:
        """
        Apply the effects of a fault to PID values.
        
        Returns modified PIDs and any DTCs that would be set.
        """
        pids = base_pids.copy()
        dtcs = []
        
        failure_mode = fault_node.failure_mode.id
        component_type = fault_node.component.component_type
        
        # Get signature for this failure mode
        signature = get_signature(failure_mode)
        
        if signature:
            # Apply primary signal patterns
            for pattern in signature.primary_signals:
                pid_name = self._map_signal_to_pid(pattern.signal_name, fault_node)
                if pid_name and pid_name in pids:
                    pids[pid_name] = self._apply_pattern(pids[pid_name], pattern)
            
            # Add associated DTCs
            for dtc_pattern in signature.associated_dtcs:
                # Generate a concrete DTC from pattern
                dtc = self._generate_dtc_from_pattern(dtc_pattern, fault_node)
                if dtc:
                    dtcs.append(dtc)
        
        # Apply component-specific effects
        pids, extra_dtcs = self._apply_component_effects(pids, fault_node)
        dtcs.extend(extra_dtcs)
        
        # Add noise
        pids = self._add_noise(pids)
        
        return pids, dtcs
    
    def _map_signal_to_pid(self, signal_name: str, fault_node: FaultNode) -> Optional[str]:
        """Map a generic signal name to a concrete PID."""
        component_name = fault_node.component.name.lower()
        
        # Handle sensor signals
        if "coolant" in component_name and "temp" in component_name:
            return "COOLANT_TEMP"
        if "intake" in component_name and "temp" in component_name:
            return "INTAKE_AIR_TEMP"
        if "map" in component_name or "manifold" in component_name:
            return "MAP"
        if "throttle" in component_name:
            return "THROTTLE_POS"
        if "maf" in component_name or "mass air" in component_name:
            return "MAF"
        if "o2" in component_name or "oxygen" in component_name:
            return "O2_VOLTAGE_B1S1"
        
        # Handle motor/pump signals
        if "pump" in component_name:
            if "fuel" in component_name:
                return "FUEL_PRESSURE"
            if "coolant" in component_name:
                return "COOLANT_TEMP"  # Indirect effect
        
        # Handle battery signals (EV)
        if "battery" in component_name:
            if "temp" in signal_name.lower():
                return "BATTERY_TEMP"
            if "voltage" in signal_name.lower():
                return "BATTERY_VOLTAGE"
            if "current" in signal_name.lower():
                return "BATTERY_CURRENT"
        
        return None
    
    def _apply_pattern(self, value: float, pattern: SignalPattern) -> float:
        """Apply a signal pattern to modify a value."""
        if pattern.pattern == PatternType.CONSTANT_MIN or pattern.pattern == PatternType.ZERO:
            return pattern.threshold_low or 0.0
        
        elif pattern.pattern == PatternType.CONSTANT_MAX:
            return pattern.threshold_high or 100.0
        
        elif pattern.pattern == PatternType.VERY_LOW:
            # Reduce to 20% of normal
            return value * 0.2
        
        elif pattern.pattern == PatternType.VERY_HIGH:
            # Increase to 180% of normal
            return value * 1.8
        
        elif pattern.pattern == PatternType.OFFSET_LOW:
            # Offset down by 20%
            return value * 0.8
        
        elif pattern.pattern == PatternType.OFFSET_HIGH:
            # Offset up by 20%
            return value * 1.2
        
        elif pattern.pattern == PatternType.ERRATIC:
            # Add random large deviation
            return value + random.gauss(0, value * 0.5)
        
        elif pattern.pattern == PatternType.RISING:
            # Above normal
            return value * 1.3
        
        elif pattern.pattern == PatternType.FALLING:
            # Below normal
            return value * 0.7
        
        return value
    
    def _apply_component_effects(
        self,
        pids: Dict[str, float],
        fault_node: FaultNode
    ) -> Tuple[Dict[str, float], List[str]]:
        """Apply component-type-specific effects."""
        dtcs = []
        component_type = fault_node.component.component_type
        failure_mode = fault_node.failure_mode.id
        
        # Sensor failures
        if component_type == ComponentType.SENSOR:
            if "stuck_low" in failure_mode:
                # Generic sensor stuck low
                if "COOLANT_TEMP" in pids:
                    pids["COOLANT_TEMP"] = -40  # Min value
                    dtcs.append("P0117")  # Coolant temp low
            elif "stuck_high" in failure_mode:
                if "COOLANT_TEMP" in pids:
                    pids["COOLANT_TEMP"] = 150  # Way too high
                    dtcs.append("P0118")  # Coolant temp high
        
        # Motor/pump failures
        elif component_type in [ComponentType.MOTOR, ComponentType.PUMP]:
            if "open" in failure_mode or "seized" in failure_mode:
                # Pump not working = system degradation
                if "COOLANT_TEMP" in pids:
                    # Cooling pump failure = overheating
                    pids["COOLANT_TEMP"] = min(130, pids.get("COOLANT_TEMP", 90) + 40)
                if "FUEL_PRESSURE" in pids:
                    # Fuel pump failure = low pressure
                    pids["FUEL_PRESSURE"] = 0
                    dtcs.append("P0230")  # Fuel pump circuit
        
        # Relay failures
        elif component_type == ComponentType.RELAY:
            if "welded" in failure_mode:
                # Always on
                dtcs.append("P0688")  # Generic relay stuck
            elif "open" in failure_mode or "coil_open" in failure_mode:
                # Never works
                dtcs.append("P0689")  # Generic relay open
        
        # Ignition failures
        elif component_type == ComponentType.IGNITION_COIL:
            if "open" in failure_mode or "weak" in failure_mode:
                # Misfire
                pids["ENGINE_RPM"] = pids.get("ENGINE_RPM", 750) * 0.9  # Rough idle
                dtcs.append("P0300")  # Random misfire
        
        # Injector failures
        elif component_type == ComponentType.FUEL_INJECTOR:
            if "clogged" in failure_mode:
                pids["LONG_FUEL_TRIM_1"] = 20  # Lean
                dtcs.append("P0171")  # System too lean
            elif "leaking" in failure_mode or "stuck_open" in failure_mode:
                pids["LONG_FUEL_TRIM_1"] = -20  # Rich
                dtcs.append("P0172")  # System too rich
        
        return pids, dtcs
    
    def _generate_dtc_from_pattern(
        self, 
        pattern: str, 
        fault_node: FaultNode
    ) -> Optional[str]:
        """Generate a concrete DTC from a regex pattern."""
        # Simplified: just generate common DTCs based on pattern
        if "P030" in pattern:
            cylinder = random.randint(1, 6)
            return f"P030{cylinder}"
        if "P017" in pattern:
            return random.choice(["P0171", "P0172", "P0174", "P0175"])
        if "P00" in pattern:
            return f"P0{random.randint(100, 199)}"
        
        return None
    
    def _add_noise(self, pids: Dict[str, float]) -> Dict[str, float]:
        """Add realistic noise to PID values."""
        noisy = {}
        for pid, value in pids.items():
            # Add Gaussian noise proportional to value
            noise = random.gauss(0, abs(value) * self.noise_level)
            noisy[pid] = value + noise
            
            # Clamp to valid range
            if pid in COMMON_PID_FEATURES:
                feature = COMMON_PID_FEATURES[pid]
                noisy[pid] = max(feature.min_value, min(feature.max_value, noisy[pid]))
        
        return noisy
    
    def generate_from_fault_tree(
        self,
        fault_tree: FaultTree,
        n_examples_per_fault: int = 100,
        system_profile: str = "engine_idle"
    ) -> List[TrainingExample]:
        """
        Generate synthetic examples from a fault tree.
        
        Args:
            fault_tree: The fault tree to generate from
            n_examples_per_fault: How many examples per fault node
            system_profile: Which baseline profile to use
            
        Returns:
            List of training examples
        """
        examples = []
        profile = SYSTEM_PROFILES.get(system_profile, SYSTEM_PROFILES["engine_idle"])
        
        # Generate normal examples
        n_normal = int(n_examples_per_fault * self.include_normal_ratio * len(fault_tree.fault_nodes))
        for _ in range(n_normal):
            base_pids = profile.sample_normal()
            noisy_pids = self._add_noise(base_pids)
            
            example = TrainingExample(
                example_id=self._generate_example_id(),
                vehicle_year=fault_tree.vehicle_year,
                vehicle_make=fault_tree.vehicle_make,
                vehicle_model=fault_tree.vehicle_model,
                pid_values=noisy_pids,
                dtc_codes=[],
                fault_label="NORMAL",
                source="synthetic",
                weight=1.0,
            )
            examples.append(example)
        
        # Generate fault examples
        for fault_node in fault_tree.fault_nodes.values():
            # Weight based on probability (TSB-related = more examples)
            weight = fault_node.effective_probability
            n_examples = int(n_examples_per_fault * weight * 2)  # Scale by probability
            n_examples = max(10, min(n_examples_per_fault * 3, n_examples))
            
            for _ in range(n_examples):
                base_pids = profile.sample_normal()
                modified_pids, dtcs = self._apply_fault_effects(base_pids, fault_node)
                
                example = TrainingExample(
                    example_id=self._generate_example_id(),
                    vehicle_year=fault_tree.vehicle_year,
                    vehicle_make=fault_tree.vehicle_make,
                    vehicle_model=fault_tree.vehicle_model,
                    pid_values=modified_pids,
                    dtc_codes=dtcs,
                    fault_label=fault_node.id,
                    source="synthetic",
                    weight=weight,  # Higher weight for common failures
                )
                examples.append(example)
        
        logger.info(f"Generated {len(examples)} synthetic examples from fault tree")
        return examples
    
    def generate_augmented(
        self,
        real_examples: List[TrainingExample],
        augmentation_factor: int = 5
    ) -> List[TrainingExample]:
        """
        Augment real examples with variations.
        
        Args:
            real_examples: Real training examples
            augmentation_factor: How many augmented versions per real example
            
        Returns:
            List including original and augmented examples
        """
        augmented = list(real_examples)  # Keep originals
        
        for example in real_examples:
            for _ in range(augmentation_factor):
                # Create variation with noise
                noisy_pids = self._add_noise(example.pid_values)
                
                # Randomly drop some DTCs (30% chance)
                dtcs = [dtc for dtc in example.dtc_codes if random.random() > 0.3]
                
                aug_example = TrainingExample(
                    example_id=self._generate_example_id(),
                    vehicle_year=example.vehicle_year,
                    vehicle_make=example.vehicle_make,
                    vehicle_model=example.vehicle_model,
                    pid_values=noisy_pids,
                    dtc_codes=dtcs,
                    fault_label=example.fault_label,
                    source="augmented",
                    weight=example.weight * 0.8,  # Slightly lower weight
                )
                augmented.append(aug_example)
        
        return augmented


# =============================================================================
# FEATURE ANALYSIS UTILITY
# =============================================================================

def analyze_features(
    X: np.ndarray, 
    y: np.ndarray, 
    feature_names: List[str], 
    class_names: List[str]
):
    """Analyze feature distributions by class."""
    print("\n=== Feature Analysis by Class ===\n")
    
    key_features = [
        "coolant_temp_final",
        "coolant_warmup_time",
        "stft_b1_mean",
        "ltft_b1_mean",
        "voltage_mean",
        "fuel_pressure_final",
        "map_mean",
        "o2_b1s1_mean",
    ]
    
    for fname in key_features:
        if fname not in feature_names:
            continue
        
        fidx = feature_names.index(fname)
        print(f"\n{fname}:")
        
        for cidx, cname in enumerate(class_names):
            mask = y == cidx
            if mask.sum() == 0:
                continue
            
            values = X[mask, fidx]
            print(f"  {cname:30s}: mean={np.mean(values):8.2f}, std={np.std(values):6.2f}")


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic training data")
    parser.add_argument("--samples", type=int, default=50, help="Samples per class")
    parser.add_argument("--output", type=str, default="training_data", help="Output directory")
    parser.add_argument("--analyze", action="store_true", help="Analyze generated data")
    parser.add_argument("--modes", type=str, nargs="*", help="Specific failure modes to include")
    args = parser.parse_args()
    
    config = PhysicsDataConfig(
        samples_per_class=args.samples,
        output_dir=args.output,
    )
    
    gen = PhysicsBasedGenerator(config)
    
    print(f"\n=== Generating Physics-Based Training Data ===")
    print(f"Samples per class: {args.samples}")
    print(f"Output directory: {args.output}")
    
    failure_modes = args.modes if args.modes else None
    if failure_modes is None:
        failure_modes = gen.get_all_failure_modes()
        print(f"Failure modes: {len(failure_modes)} total")
    else:
        print(f"Failure modes: {failure_modes}")
    
    print()
    
    X, y, feature_names, class_names = gen.generate_dataset(
        failure_modes=failure_modes
    )
    
    gen.save_dataset(X, y, feature_names, class_names)
    
    if args.analyze:
        analyze_features(X, y, feature_names, class_names)
    
    print("\n=== Class Distribution ===")
    for cidx, cname in enumerate(class_names):
        count = (y == cidx).sum()
        print(f"  {cname}: {count}")
