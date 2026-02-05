#!/usr/bin/env python3
"""
Generate Large Training Dataset and Train Model

This uses the physics engine to generate thousands of training samples
across all failure modes, then trains the ML model properly.

Goal: Generate enough data for 85%+ validation accuracy
"""

import sys
import os
import time
import json
from pathlib import Path

sys.path.insert(0, "/home/drawson/autotech_ai")

def generate_large_dataset(samples_per_failure: int = 200, 
                           normal_samples: int = 400,
                           output_dir: str = "/tmp/pd_training_data"):
    """Generate large physics-based training dataset."""
    
    from addons.predictive_diagnostics.simulation import (
        TrainingDataGenerator,
        DataGeneratorConfig,
    )
    from addons.predictive_diagnostics.knowledge.failures import get_all_failure_modes
    
    print("=" * 60)
    print("GENERATING LARGE TRAINING DATASET")
    print("=" * 60)
    
    all_failures = get_all_failure_modes()
    print(f"\nTotal failure modes: {len(all_failures)}")
    print(f"Samples per failure: {samples_per_failure}")
    print(f"Normal samples: {normal_samples}")
    expected_total = len(all_failures) * samples_per_failure + normal_samples
    print(f"Expected total samples: {expected_total:,}")
    print()
    
    config = DataGeneratorConfig(
        samples_per_failure=samples_per_failure,
        normal_samples=normal_samples,
        min_duration=300.0,   # 5 min - longer to see failure effects
        max_duration=900.0,   # 15 min
        min_severity=0.5,     # Higher min severity - make failures obvious
        max_severity=1.0,
    )
    
    generator = TrainingDataGenerator(config)
    
    # Generate for cooling system (it has the simulator)
    all_samples = []
    
    start = time.time()
    samples = generator.generate_dataset_for_system("cooling")
    elapsed = time.time() - start
    
    all_samples.extend(samples)
    print(f"\nGenerated {len(samples)} cooling samples in {elapsed:.1f}s")
    
    # Save dataset
    os.makedirs(output_dir, exist_ok=True)
    output_path = f"{output_dir}/cooling_dataset.json"
    
    with open(output_path, 'w') as f:
        json.dump(all_samples, f)
    
    print(f"\nSaved dataset to {output_path}")
    print(f"File size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB")
    
    # Summary
    labels = {}
    for s in all_samples:
        label = s['label']
        labels[label] = labels.get(label, 0) + 1
    
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    for label, count in sorted(labels.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")
    
    return all_samples, output_path


def train_model_on_dataset(dataset_path: str, 
                            epochs: int = 100,
                            output_path: str = "/tmp/pd_trained_model.pt"):
    """Train ML model on generated dataset."""
    
    import torch
    from addons.predictive_diagnostics.ml import (
        DiagnosticModel,  # Full CNN+LSTM model
        SimpleDiagnosticModel,
        ModelConfig,
        ModelTrainer,
        TrainingConfig,
    )
    
    print("\n" + "=" * 60)
    print("TRAINING ML MODEL")
    print("=" * 60)
    
    # Load dataset
    with open(dataset_path) as f:
        samples = json.load(f)
    
    print(f"Loaded {len(samples)} samples")
    
    # Count classes
    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)
    print(f"Classes: {num_classes}")
    
    # Create CNN+LSTM model (better for temporal patterns)
    config = ModelConfig(
        num_classes=num_classes,
        cnn_channels=[64, 128, 128],
        lstm_hidden_size=256,
        lstm_num_layers=2,
        dense_sizes=[256, 128],
        dropout=0.3,
    )
    model = DiagnosticModel(config)
    
    # Count parameters
    params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {params:,}")
    
    # Create trainer
    train_config = TrainingConfig(
        epochs=epochs,
        patience=30,  # More patience
        batch_size=32,  # Smaller batch for better generalization
        learning_rate=5e-4,  # Lower LR
        weight_decay=1e-3,  # More regularization
        log_interval=10,
        checkpoint_dir="/tmp/pd_checkpoints",
        train_split=0.8,  # 80% train, 20% val
    )
    trainer = ModelTrainer(train_config)
    
    # Train
    print("\nStarting training...")
    start = time.time()
    
    trainer.load_data(samples, use_features=False)  # Use raw sequences for CNN+LSTM
    metrics = trainer.train(model)
    
    elapsed = time.time() - start
    
    print(f"\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Epochs: {metrics.get('num_epochs', 'N/A')}")
    print(f"Train accuracy: {metrics.get('final_train_acc', 0):.1%}")
    print(f"Val accuracy: {metrics.get('final_val_acc', 0):.1%}")
    print(f"Best val loss: {metrics.get('best_val_loss', 'N/A')}")
    
    # Save model
    model.save(output_path)
    print(f"\nSaved model to {output_path}")
    
    return model, metrics


def evaluate_model(model_path: str, test_samples: list):
    """Evaluate model on test samples."""
    
    from addons.predictive_diagnostics.ml import DiagnosticInference
    
    print("\n" + "=" * 60)
    print("EVALUATING MODEL")
    print("=" * 60)
    
    inference = DiagnosticInference.load(model_path)
    
    correct = 0
    total = 0
    
    # Group by actual label for per-class accuracy
    by_class = {}
    
    for sample in test_samples:
        true_label = sample['label']
        
        # Convert to sensor data format
        sensor_data = {}
        for key, values in sample['sensor_data'].items():
            if isinstance(values, list):
                sensor_data[key] = values
        
        try:
            result = inference.diagnose(sensor_data)
            pred_label = result.hypotheses[0]['failure_id']
            
            if true_label not in by_class:
                by_class[true_label] = {'correct': 0, 'total': 0}
            by_class[true_label]['total'] += 1
            
            if pred_label == true_label:
                correct += 1
                by_class[true_label]['correct'] += 1
            
            total += 1
        except Exception as e:
            print(f"Error on sample: {e}")
    
    accuracy = correct / total if total > 0 else 0
    print(f"\nOverall Accuracy: {accuracy:.1%} ({correct}/{total})")
    
    print("\nPer-class accuracy:")
    for label in sorted(by_class.keys()):
        stats = by_class[label]
        acc = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        print(f"  {label}: {acc:.1%} ({stats['correct']}/{stats['total']})")
    
    return accuracy, by_class


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-failure", type=int, default=200)
    parser.add_argument("--normal-samples", type=int, default=400)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--skip-generation", action="store_true")
    parser.add_argument("--dataset-path", type=str, default="/tmp/pd_training_data/cooling_dataset.json")
    parser.add_argument("--model-output", type=str, default="/tmp/pd_trained_model.pt")
    
    args = parser.parse_args()
    
    # Generate dataset
    if not args.skip_generation:
        samples, dataset_path = generate_large_dataset(
            samples_per_failure=args.samples_per_failure,
            normal_samples=args.normal_samples,
        )
    else:
        dataset_path = args.dataset_path
        with open(dataset_path) as f:
            samples = json.load(f)
    
    # Train model
    model, metrics = train_model_on_dataset(
        dataset_path,
        epochs=args.epochs,
        output_path=args.model_output,
    )
    
    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"\nFinal validation accuracy: {metrics['final_val_acc']:.1%}")
    
    if metrics['final_val_acc'] >= 0.85:
        print("✅ TARGET ACHIEVED: 85%+ accuracy!")
    elif metrics['final_val_acc'] >= 0.70:
        print("⚠️ Good progress, but need more data or tuning for 85%")
    else:
        print("❌ Needs more work - consider more data or model architecture changes")
