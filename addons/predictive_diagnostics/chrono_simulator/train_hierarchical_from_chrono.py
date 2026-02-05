#!/usr/bin/env python3
"""
Train Hierarchical PyTorch Model from PyChrono Synthetic Data

This trains the hierarchical models that DiagnosticEngine actually uses.
Each system gets its own model with system-specific features.

Usage:
    python train_hierarchical_from_chrono.py
    
Output:
    ../models/hierarchical_models.pt (replaces existing)
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

import warnings
warnings.filterwarnings('ignore')

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "training_data" / "chrono_synthetic"
MODELS_DIR = SCRIPT_DIR.parent / "models"

# System to failure mode prefix mapping
# Based on the chrono_synthetic file naming convention
SYSTEM_PREFIXES = {
    "cooling": ["cooling", "radiator", "ect", "water"],
    "fuel": ["fuel"],
    "ignition": ["ignition"],
    "charging": ["alternator", "battery"],
    "transmission": ["transmission", "trans", "tcc"],
    "brakes": ["brakes"],
    "engine": ["oil"],
    "tires": ["tires"],
    "ev": ["tesla"],
    "starting": ["starter"],
}

# Sensors available from chrono simulation
CHRONO_SENSORS = [
    # Core powertrain
    'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
    # Cooling
    'coolant_temp',
    # Fuel
    'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2', 'fuel_pressure',
    # Tires/brakes
    'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
    'brake_temp', 'decel_rate', 'brake_pedal_travel',
    # Transmission
    'trans_slip_ratio', 'trans_temp', 'shift_quality',
]


def get_system_for_failure(failure_mode_id: str) -> str:
    """Map a failure mode ID to its system."""
    # Handle both 'cooling_thermostat_stuck' and 'cooling.thermostat_stuck' formats
    prefix = failure_mode_id.split('.')[0] if '.' in failure_mode_id else failure_mode_id.split('_')[0]
    
    for system, prefixes in SYSTEM_PREFIXES.items():
        if prefix in prefixes:
            return system
        # Also check if the failure_mode_id starts with a system prefix
        for p in prefixes:
            if failure_mode_id.lower().startswith(p):
                return system
    
    return "unknown"


def extract_features(time_series: list) -> Dict[str, float]:
    """Extract statistical and temporal features from time series data."""
    if not time_series:
        return {}
    
    import pandas as pd
    df = pd.DataFrame(time_series)
    features = {}
    
    for col in CHRONO_SENSORS:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                # Basic stats
                features[f'{col}_mean'] = values.mean()
                features[f'{col}_std'] = values.std() if len(values) > 1 else 0.0
                features[f'{col}_min'] = values.min()
                features[f'{col}_max'] = values.max()
                
                # Temporal features (rate of change)
                if len(values) > 1:
                    diff = np.diff(values)
                    features[f'{col}_rate_mean'] = diff.mean()  # Average rate of change
                    features[f'{col}_rate_max'] = diff.max()    # Max increase rate
                    features[f'{col}_rate_min'] = diff.min()    # Max decrease rate
                    features[f'{col}_first'] = values.iloc[0]   # Initial value
                    features[f'{col}_last'] = values.iloc[-1]   # Final value
                    features[f'{col}_range'] = values.max() - values.min()  # Total range
                    
                    # Trend (linear regression slope)
                    x = np.arange(len(values))
                    if values.std() > 0:
                        features[f'{col}_trend'] = np.corrcoef(x, values)[0, 1]
                    else:
                        features[f'{col}_trend'] = 0.0
    
    return features


def load_data_by_system() -> Dict[str, List[Tuple[Dict, str]]]:
    """Load all chrono data and organize by system."""
    json_files = list(DATA_DIR.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    # Organize by system
    system_data = defaultdict(list)  # system -> [(features, label), ...]
    
    for json_path in json_files:
        try:
            with open(json_path) as f:
                data = json.load(f)
            
            failure_id = data['failure_mode_id']
            system = get_system_for_failure(failure_id)
            
            features = extract_features(data['time_series'])
            if features:
                system_data[system].append((features, failure_id))
                
        except Exception as e:
            continue
    
    print(f"\nData by system:")
    for system, samples in sorted(system_data.items(), key=lambda x: -len(x[1])):
        labels = set(s[1] for s in samples)
        print(f"  {system}: {len(samples)} samples, {len(labels)} failures")
    
    return dict(system_data)


def create_tensors(
    samples: List[Tuple[Dict, str]],
    label_encoder: LabelEncoder
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Convert samples to tensors."""
    feature_names = sorted(samples[0][0].keys())
    
    X = []
    y = []
    
    for features, label in samples:
        row = [features.get(f, 0.0) for f in feature_names]
        X.append(row)
        y.append(label)
    
    X = np.array(X, dtype=np.float32)
    y = label_encoder.transform(y)
    
    return torch.tensor(X), torch.tensor(y, dtype=torch.long), feature_names


def train_system_model(
    system_id: str,
    samples: List[Tuple[Dict, str]],
    epochs: int = 100,
    device: str = "cuda" if torch.cuda.is_available() else "cpu",
) -> Tuple[nn.Module, Dict[str, Any]]:
    """Train a model for one system."""
    
    if len(samples) < 20:
        print(f"  Skipping {system_id}: insufficient data ({len(samples)} samples)")
        return None, None
    
    # Get labels
    labels = sorted(set(s[1] for s in samples))
    label_encoder = LabelEncoder()
    label_encoder.fit(labels)
    
    # Create tensors
    X, y, feature_names = create_tensors(samples, label_encoder)
    
    # Split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y.numpy()
    )
    
    print(f"  Training {system_id}: {len(X_train)} train, {len(X_val)} val, {len(labels)} classes")
    
    # Create model
    input_dim = X.shape[1]
    n_classes = len(labels)
    
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
    
    train_dataset = TensorDataset(X_train.to(device), y_train.to(device))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True, drop_last=True)
    
    best_val_acc = 0
    best_state = None
    patience = 10
    no_improve = 0
    
    for epoch in range(epochs):
        model.train()
        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val.to(device))
            val_preds = val_outputs.argmax(dim=1)
            val_acc = (val_preds == y_val.to(device)).float().mean().item()
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = model.state_dict().copy()
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break
    
    # Restore best
    if best_state:
        model.load_state_dict(best_state)
    
    print(f"    Best validation accuracy: {best_val_acc:.1%}")
    
    # Metadata
    metadata = {
        'labels': list(label_encoder.classes_),
        'features': feature_names,
        'n_samples': len(samples),
        'val_accuracy': best_val_acc,
    }
    
    return model.cpu(), metadata


def main():
    parser = argparse.ArgumentParser(description="Train hierarchical models from chrono data")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--output", type=str, default=str(MODELS_DIR / "hierarchical_chrono.pt"),
                       help="Output model path")
    args = parser.parse_args()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    
    print("=" * 60)
    print("TRAINING HIERARCHICAL MODELS FROM CHRONO DATA")
    print("=" * 60)
    
    # Load data
    system_data = load_data_by_system()
    
    # Train per-system models
    models = {}
    metadata = {}
    sensors = {}
    
    print("\n" + "=" * 60)
    print("TRAINING PER-SYSTEM MODELS")
    print("=" * 60)
    
    for system_id, samples in sorted(system_data.items()):
        if system_id == "unknown":
            continue
            
        model, meta = train_system_model(system_id, samples, epochs=args.epochs, device=device)
        
        if model is not None:
            models[system_id] = model.state_dict()
            metadata[system_id] = meta
            sensors[system_id] = CHRONO_SENSORS
    
    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    checkpoint = {
        'models': models,
        'metadata': metadata,
        'sensors': sensors,
        'timestamp': datetime.now().isoformat(),
        'source': 'chrono_synthetic',
    }
    
    torch.save(checkpoint, output_path)
    print(f"\n✓ Saved to {output_path}")
    
    # Also save as the standard hierarchical_models.pt
    standard_path = MODELS_DIR / "hierarchical_models.pt"
    torch.save(checkpoint, standard_path)
    print(f"✓ Saved to {standard_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Systems trained: {list(models.keys())}")
    for sys_id, meta in metadata.items():
        print(f"  {sys_id}: {meta['val_accuracy']:.1%} accuracy, {len(meta['labels'])} classes")


if __name__ == "__main__":
    main()
