#!/usr/bin/env python3
"""
Hierarchical Multi-System Diagnostic Model

Two-level classification:
1. First identify the SYSTEM (cooling, fuel, ignition, etc.)
2. Then identify the FAILURE within that system

This approach works better when systems have non-overlapping sensors.
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, "/home/drawson/autotech_ai")

import torch
import torch.nn as nn
import numpy as np

from addons.predictive_diagnostics.simulation import (
    TrainingDataGenerator,
    DataGeneratorConfig,
)
from addons.predictive_diagnostics.ml import (
    SimpleDiagnosticModel,
    ModelConfig,
    ModelTrainer,
    TrainingConfig,
)


class HierarchicalDiagnosticModel(nn.Module):
    """
    Two-stage model:
    1. System classifier (which system has the problem?)
    2. Per-system failure classifiers (what's the specific failure?)
    """
    
    def __init__(
        self,
        system_sensors: Dict[str, List[str]],  # sensors per system
        system_failures: Dict[str, List[str]],  # failures per system
    ):
        super().__init__()
        
        self.systems = sorted(system_sensors.keys())
        self.system_sensors = system_sensors
        self.system_failures = system_failures
        
        # System classifier - uses presence/absence of sensor readings
        self.system_classifier = nn.Sequential(
            nn.Linear(len(self.systems), 32),
            nn.ReLU(),
            nn.Linear(32, len(self.systems)),
        )
        
        # Per-system failure classifiers
        self.failure_classifiers = nn.ModuleDict()
        for system_id in self.systems:
            n_sensors = len(system_sensors[system_id])
            # Input: 4 stats per sensor (mean, std, min, max)
            input_dim = n_sensors * 4
            n_classes = len(system_failures[system_id]) + 1  # +1 for normal
            
            self.failure_classifiers[system_id] = nn.Sequential(
                nn.Linear(input_dim, 128),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(64, n_classes),
            )
    
    def forward(self, x: torch.Tensor, system_id: Optional[str] = None):
        """
        If system_id is provided, only run failure classifier for that system.
        Otherwise, run system classifier first.
        """
        # For now, assume system_id is always provided during training
        if system_id is None:
            raise NotImplementedError("Auto system detection not implemented yet")
        
        return self.failure_classifiers[system_id](x)
    
    def save(self, path: str):
        """Save model with metadata."""
        torch.save({
            'state_dict': self.state_dict(),
            'systems': self.systems,
            'system_sensors': self.system_sensors,
            'system_failures': self.system_failures,
        }, path)
    
    @classmethod
    def load(cls, path: str) -> 'HierarchicalDiagnosticModel':
        """Load model from checkpoint."""
        checkpoint = torch.load(path, map_location='cpu')
        model = cls(
            checkpoint['system_sensors'],
            checkpoint['system_failures'],
        )
        model.load_state_dict(checkpoint['state_dict'])
        return model


def extract_features(sample: Dict, sensor_names: List[str]) -> np.ndarray:
    """Extract statistical features from time series."""
    features = []
    
    # Get time series data
    ts_data = sample.get("time_series") or sample.get("sensor_data", {})
    
    for sensor in sensor_names:
        if sensor in ts_data:
            values = ts_data[sensor]
            if isinstance(values, list) and len(values) > 0:
                arr = np.array(values)
                features.extend([
                    np.mean(arr),
                    np.std(arr),
                    np.min(arr),
                    np.max(arr),
                ])
            else:
                features.extend([0.0, 0.0, 0.0, 0.0])
        else:
            features.extend([0.0, 0.0, 0.0, 0.0])
    
    return np.array(features, dtype=np.float32)


def train_system_model(
    samples: List[Dict],
    system_id: str,
    sensor_names: List[str],
    epochs: int = 100,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Train a single system's failure classifier."""
    
    # Get unique labels for this system
    labels = sorted(set(s["label"] for s in samples))
    label_to_idx = {l: i for i, l in enumerate(labels)}
    n_classes = len(labels)
    
    print(f"\n  Training {system_id} classifier:")
    print(f"    Samples: {len(samples)}")
    print(f"    Classes: {n_classes}")
    print(f"    Sensors: {len(sensor_names)}")
    
    # Extract features
    X = np.array([extract_features(s, sensor_names) for s in samples])
    y = np.array([label_to_idx[s["label"]] for s in samples])
    
    # Normalize features
    mean = X.mean(axis=0)
    std = X.std(axis=0) + 1e-8
    X = (X - mean) / std
    
    # Split data
    n_train = int(len(X) * 0.8)
    indices = np.random.permutation(len(X))
    train_idx, val_idx = indices[:n_train], indices[n_train:]
    
    X_train, X_val = X[train_idx], X[val_idx]
    y_train, y_val = y[train_idx], y[val_idx]
    
    # Create model - larger capacity for complex patterns
    input_dim = X.shape[1]
    model = nn.Sequential(
        nn.Linear(input_dim, 256),
        nn.ReLU(),
        nn.BatchNorm1d(256),
        nn.Dropout(0.3),
        nn.Linear(256, 128),
        nn.ReLU(),
        nn.BatchNorm1d(128),
        nn.Dropout(0.3),
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(64, n_classes),
    ).to(device)
    
    # Training
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    
    X_train_t = torch.tensor(X_train).to(device)
    y_train_t = torch.tensor(y_train, dtype=torch.long).to(device)
    X_val_t = torch.tensor(X_val).to(device)
    y_val_t = torch.tensor(y_val, dtype=torch.long).to(device)
    
    best_val_acc = 0
    patience_counter = 0
    patience = 20
    
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train_t)
        loss = criterion(outputs, y_train_t)
        loss.backward()
        optimizer.step()
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val_t)
            val_preds = val_outputs.argmax(dim=1)
            val_acc = (val_preds == y_val_t).float().mean().item()
            
            train_preds = model(X_train_t).argmax(dim=1)
            train_acc = (train_preds == y_train_t).float().mean().item()
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"    Early stop at epoch {epoch+1}")
                break
        
        if (epoch + 1) % 25 == 0:
            print(f"    Epoch {epoch+1}: train={train_acc:.1%}, val={val_acc:.1%}")
    
    print(f"    Final: train={train_acc:.1%}, val={best_val_acc:.1%}")
    
    # Return model and metadata
    return model, {
        "labels": labels,
        "label_to_idx": label_to_idx,
        "mean": mean,
        "std": std,
        "train_acc": train_acc,
        "val_acc": best_val_acc,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-failure", type=int, default=100)
    parser.add_argument("--normal-samples", type=int, default=200)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args()
    
    output_dir = "/tmp/pd_hierarchical"
    os.makedirs(output_dir, exist_ok=True)
    dataset_path = f"{output_dir}/dataset.json"
    
    # Define sensors per system (must match simulator output)
    SYSTEM_SENSORS = {
        "cooling": [
            "coolant_temp", "oil_temp", "fan_state", "thermostat_position",
            "radiator_delta_t", "flow_rate", "system_pressure", "ambient_temp",
        ],
        "fuel": [
            "fuel_pressure", "stft", "ltft", "afr", "injector_pw", "maf_reading",
        ],
        "ignition": [
            "spark_advance", "misfire_count", "knock_sensor", "coil_dwell", 
            "battery_voltage", "rpm_stability", "timing_variance",
            "secondary_ignition", "coil_primary_current",
        ],
        "charging": [
            "battery_voltage", "alternator_output_v", "charge_current", "battery_soc",
        ],
        "starting": [
            "cranking_rpm", "cranking_voltage", "starter_current", "crank_time",
            "battery_voltage_cranking",
        ],
        "transmission": [
            "trans_temp", "line_pressure", "slip_percent", "shift_time", "current_gear",
            "tcc_slip", "input_speed", "output_speed", "commanded_gear",
        ],
        "brakes": [
            "brake_pressure", "rotor_temp", "pad_thickness", "abs_active", 
            "pedal_travel", "pedal_feel", "stopping_distance",
            "wheel_speed_lf", "wheel_speed_rf", "wheel_speed_lr", "wheel_speed_rr",
        ],
        "engine": [
            "oil_pressure", "manifold_vacuum", "compression_variation",
            "blow_by_pressure", "timing_deviation", "power_balance",
            "cam_timing_actual", "cam_timing_target", "vvt_position",
        ],
        "steering": [
            "steering_assist", "ps_pressure", "steering_effort", "steering_play",
            "steering_noise", "steering_response",
        ],
        "suspension": [
            "ride_height", "damping_coefficient", "body_roll", "bounce_count",
            "suspension_noise", "wheel_bearing_temp",
        ],
        "hvac": [
            "vent_temp", "refrigerant_pressure_high", "refrigerant_pressure_low",
            "compressor_clutch", "blower_speed", "cabin_temp",
        ],
        "emissions": [
            "catalyst_efficiency", "o2_upstream_mv", "o2_downstream_mv",
            "egr_flow", "evap_pressure", "nox_level",
        ],
        "turbo": [
            "boost_pressure", "boost_target", "wastegate_position", "iat_post_ic",
            "compressor_inlet_temp", "egt", "turbo_speed",
        ],
    }
    
    # Generate or load data
    if not args.skip_generation:
        print("=" * 60)
        print("GENERATING DATA")
        print("=" * 60)
        
        config = DataGeneratorConfig(
            samples_per_failure=args.samples_per_failure,
            normal_samples=args.normal_samples,
            min_duration=180.0,
            max_duration=600.0,
        )
        generator = TrainingDataGenerator(config)
        
        all_samples = []
        for system_id in generator.engine._simulators.keys():
            print(f"\nGenerating {system_id}...")
            samples = generator.generate_dataset_for_system(system_id)
            for s in samples:
                s["system_id"] = system_id
            all_samples.extend(samples)
            print(f"  {len(samples)} samples")
        
        with open(dataset_path, 'w') as f:
            json.dump(all_samples, f)
        print(f"\n✓ Saved {len(all_samples)} samples")
    else:
        with open(dataset_path) as f:
            all_samples = json.load(f)
        print(f"Loaded {len(all_samples)} samples")
    
    # Group by system
    by_system = defaultdict(list)
    for s in all_samples:
        by_system[s["system_id"]].append(s)
    
    # Train per-system models
    print("\n" + "=" * 60)
    print("TRAINING PER-SYSTEM MODELS")
    print("=" * 60)
    
    models = {}
    metadata = {}
    
    for system_id, samples in by_system.items():
        sensors = SYSTEM_SENSORS.get(system_id, [])
        if not sensors:
            print(f"\nSkipping {system_id} - no sensor definition")
            continue
        
        model, meta = train_system_model(
            samples,
            system_id,
            sensors,
            epochs=args.epochs,
        )
        models[system_id] = model
        metadata[system_id] = meta
    
    # Save all models
    save_path = f"{output_dir}/hierarchical_models.pt"
    torch.save({
        "models": {k: v.state_dict() for k, v in models.items()},
        "metadata": metadata,
        "sensors": SYSTEM_SENSORS,
    }, save_path)
    print(f"\n✓ Saved to {save_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    
    total_val_acc = 0
    for system_id, meta in metadata.items():
        print(f"\n{system_id}:")
        print(f"  Classes: {len(meta['labels'])}")
        print(f"  Accuracy: {meta['val_acc']:.1%}")
        total_val_acc += meta['val_acc']
    
    avg_acc = total_val_acc / len(metadata)
    print(f"\n{'=' * 60}")
    print(f"AVERAGE ACCURACY: {avg_acc:.1%}")
    print(f"{'=' * 60}")
    
    if avg_acc >= 0.80:
        print("✅ Excellent - Ready for production")
    elif avg_acc >= 0.70:
        print("✅ Good - May benefit from more data")
    elif avg_acc >= 0.60:
        print("⚠️ Moderate - Needs improvement")
    else:
        print("❌ Low - Needs investigation")


if __name__ == "__main__":
    main()
