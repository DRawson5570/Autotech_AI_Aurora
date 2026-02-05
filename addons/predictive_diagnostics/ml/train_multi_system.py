#!/usr/bin/env python3
"""
Train Multi-System Diagnostic Model

Generates training data from physics simulations across all systems
and trains a unified diagnostic model.

Systems covered:
- Cooling (12 failures)
- Fuel (6 failures)
- Ignition (4 failures)
- Charging (3 failures)
- Transmission (3 failures)
- Brakes (5 failures)
- Engine (5 failures - will add simulator)

Total: 33+ failure modes + normal operation
"""

import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple

sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.simulation import (
    TrainingDataGenerator,
    DataGeneratorConfig,
)


def generate_multi_system_dataset(
    samples_per_failure: int = 100,
    normal_samples_per_system: int = 200,
    output_dir: str = "/tmp/pd_multi_system",
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Generate training data for all systems.
    
    Returns:
        all_samples: Combined list of all samples
        stats: Dictionary of statistics
    """
    print("=" * 60)
    print("GENERATING MULTI-SYSTEM TRAINING DATA")
    print("=" * 60)
    
    config = DataGeneratorConfig(
        samples_per_failure=samples_per_failure,
        normal_samples=normal_samples_per_system,
        min_duration=180.0,   # 3 min
        max_duration=600.0,   # 10 min
        min_severity=0.5,
        max_severity=1.0,
    )
    
    generator = TrainingDataGenerator(config)
    systems = list(generator.engine._simulators.keys())
    
    print(f"\nSystems available: {systems}")
    
    all_samples = []
    stats = {"systems": {}, "total_failures": 0, "total_samples": 0}
    
    for system_id in systems:
        print(f"\n--- Generating {system_id} data ---")
        start = time.time()
        
        samples = generator.generate_dataset_for_system(system_id)
        elapsed = time.time() - start
        
        # Add system prefix to labels for unified model
        for s in samples:
            # Add system context to sensor data
            s["system_id"] = system_id
            # Keep original label (already unique across systems)
        
        all_samples.extend(samples)
        
        # Count labels
        labels = {}
        for s in samples:
            labels[s["label"]] = labels.get(s["label"], 0) + 1
        
        stats["systems"][system_id] = {
            "samples": len(samples),
            "failures": len(labels) - 1,  # Exclude normal
            "time_sec": elapsed,
        }
        stats["total_failures"] += len(labels) - 1
        stats["total_samples"] += len(samples)
        
        print(f"  Generated {len(samples)} samples in {elapsed:.1f}s")
    
    # Save combined dataset
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/multi_system_dataset.json"
    
    with open(output_path, 'w') as f:
        json.dump(all_samples, f)
    
    file_size = Path(output_path).stat().st_size / 1024 / 1024
    print(f"\n✓ Saved to {output_path} ({file_size:.1f} MB)")
    
    # Print summary
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    
    labels = {}
    for s in all_samples:
        labels[s["label"]] = labels.get(s["label"], 0) + 1
    
    print(f"\nTotal samples: {len(all_samples)}")
    print(f"Total classes: {len(labels)}")
    
    for system_id, system_stats in stats["systems"].items():
        print(f"\n{system_id}:")
        print(f"  Samples: {system_stats['samples']}")
        print(f"  Failures: {system_stats['failures']}")
    
    return all_samples, stats


def train_unified_model(
    dataset_path: str,
    epochs: int = 100,
    output_path: str = "/tmp/pd_multi_system/unified_model.pt",
) -> Dict[str, Any]:
    """
    Train a unified model on multi-system data.
    """
    import torch
    from addons.predictive_diagnostics.ml import (
        SimpleDiagnosticModel,
        ModelConfig,
        ModelTrainer,
        TrainingConfig,
    )
    
    print("\n" + "=" * 60)
    print("TRAINING UNIFIED MODEL")
    print("=" * 60)
    
    # Load dataset
    with open(dataset_path) as f:
        samples = json.load(f)
    
    print(f"Loaded {len(samples)} samples")
    
    # Get all unique labels
    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)
    print(f"Classes: {num_classes}")
    
    # Get all unique sensor names across all systems
    all_sensors = set()
    for s in samples:
        if "sensor_data" in s:
            all_sensors.update(s["sensor_data"].keys())
        elif "time_series" in s:
            all_sensors.update(s["time_series"].keys())
    
    # Filter to numeric sensors (exclude internal tracking vars)
    sensor_names = sorted([n for n in all_sensors if not n.startswith("_")])
    print(f"Sensors: {len(sensor_names)}")
    print(f"  {sensor_names[:5]}... ")
    
    # Use SimpleDiagnosticModel (feature-based) for now
    # This is simpler than CNN+LSTM and works across different sensor sets
    config = ModelConfig(
        num_classes=num_classes,
        input_features=sensor_names,
        dense_sizes=[256, 128],
        dropout=0.3,
    )
    model = SimpleDiagnosticModel(config)
    
    params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {params:,}")
    
    # Training config
    train_config = TrainingConfig(
        epochs=epochs,
        patience=25,
        batch_size=64,
        learning_rate=1e-3,
        weight_decay=1e-4,
        train_split=0.8,
        log_interval=10,
        checkpoint_dir="/tmp/pd_multi_system/checkpoints",
    )
    trainer = ModelTrainer(train_config)
    
    # Load data with statistical features
    print("\nPreparing training data...")
    trainer.load_data(samples, feature_names=sensor_names, use_features=True)
    
    # Train
    print("\nStarting training...")
    start = time.time()
    metrics = trainer.train(model)
    elapsed = time.time() - start
    
    print(f"\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Epochs: {metrics.get('num_epochs', 'N/A')}")
    print(f"Train accuracy: {metrics.get('final_train_acc', 0):.1%}")
    print(f"Val accuracy: {metrics.get('final_val_acc', 0):.1%}")
    
    # Save model
    model.save(output_path)
    print(f"\n✓ Saved model to {output_path}")
    
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train multi-system diagnostic model")
    parser.add_argument("--samples-per-failure", type=int, default=100)
    parser.add_argument("--normal-samples", type=int, default=200)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--dataset-path", type=str, 
                       default="/tmp/pd_multi_system/multi_system_dataset.json")
    parser.add_argument("--model-output", type=str,
                       default="/tmp/pd_multi_system/unified_model.pt")
    
    args = parser.parse_args()
    
    # Generate data
    if not args.skip_generation:
        samples, stats = generate_multi_system_dataset(
            samples_per_failure=args.samples_per_failure,
            normal_samples_per_system=args.normal_samples,
        )
        dataset_path = "/tmp/pd_multi_system/multi_system_dataset.json"
    else:
        dataset_path = args.dataset_path
    
    # Train model
    metrics = train_unified_model(
        dataset_path,
        epochs=args.epochs,
        output_path=args.model_output,
    )
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    
    val_acc = metrics.get('final_val_acc', 0)
    if val_acc >= 0.75:
        print(f"✅ Good accuracy: {val_acc:.1%}")
    elif val_acc >= 0.60:
        print(f"⚠️ Moderate accuracy: {val_acc:.1%} - may need more data")
    else:
        print(f"❌ Low accuracy: {val_acc:.1%} - needs investigation")
