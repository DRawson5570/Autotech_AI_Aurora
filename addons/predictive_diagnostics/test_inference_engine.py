#!/usr/bin/env python3
"""
Test the inference engine with hierarchical models.

Usage:
    python test_inference_engine.py
"""

import sys
import json
import glob
import random
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from addons.predictive_diagnostics.inference_engine import InferenceEngine


# Sensors to extract features from (same as training)
CHRONO_SENSORS = [
    'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
    'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2', 'fuel_pressure',
    'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
    'brake_temp', 'decel_rate', 'brake_pedal_travel',
    'trans_slip_ratio', 'trans_temp', 'shift_quality',
]


def extract_features(time_series: list) -> dict:
    """Extract statistical features from time series (matches chrono train_from_chrono.py)."""
    if not time_series:
        return {}
    
    df = pd.DataFrame(time_series)
    features = {}
    
    for col in CHRONO_SENSORS:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                features[f'{col}_mean'] = values.mean()
                features[f'{col}_std'] = values.std() if len(values) > 1 else 0.0
                features[f'{col}_min'] = values.min()
                features[f'{col}_max'] = values.max()
                features[f'{col}_range'] = values.max() - values.min()
                features[f'{col}_final'] = values.iloc[-1]
                # Rate of change
                if len(values) > 1:
                    features[f'{col}_delta'] = values.iloc[-1] - values.iloc[0]
                    # Max absolute rate of change
                    diff = values.diff().abs()
                    features[f'{col}_rate_max'] = diff.max() if len(diff) > 0 else 0.0
    
    return features


def load_sample(sample_path: str) -> tuple:
    """Load a sample and return features + ground truth."""
    with open(sample_path) as f:
        data = json.load(f)
    
    # Extract features from time series
    time_series = data.get('time_series', [])
    features = extract_features(time_series)
    
    failure_mode = data.get('failure_mode_id', data.get('failure_mode', 'unknown'))
    
    # Get system from failure mode
    system = failure_mode.split('.')[0] if '.' in failure_mode else failure_mode.split('_')[0]
    
    return features, failure_mode, system


def main():
    print("=" * 60)
    print("INFERENCE ENGINE TEST - Hierarchical Models")
    print("=" * 60)
    
    # Initialize engine
    print("\n1. Loading inference engine...")
    try:
        engine = InferenceEngine(model_type="auto")
        print(f"   ✓ Loaded model type: {engine.model_type}")
        
        if engine.model_type == "hierarchical":
            systems = list(engine.predictor.models.keys())
            print(f"   ✓ Systems available: {', '.join(systems)}")
    except Exception as e:
        print(f"   ✗ Failed to load engine: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Find test samples
    print("\n2. Finding test samples...")
    sample_dir = Path(__file__).parent / "training_data" / "chrono_synthetic"
    
    if not sample_dir.exists():
        print(f"   ✗ Sample directory not found: {sample_dir}")
        sys.exit(1)
    
    samples = list(sample_dir.glob("*.json"))
    print(f"   Found {len(samples)} samples")
    
    # Test with random samples
    print("\n3. Testing with random samples...")
    test_samples = random.sample(samples, min(10, len(samples)))
    
    correct = 0
    total = 0
    
    for sample_path in test_samples:
        features, true_mode, true_system = load_sample(str(sample_path))
        
        if not features:
            print(f"   ⚠ Skipping {sample_path.name}: no features")
            continue
        
        results = engine.diagnose(features, top_k=4)
        
        if not results:
            print(f"   ⚠ Skipping {sample_path.name}: no predictions")
            continue
        
        # Check if ground truth is in top-k predictions
        top_predictions = [r.failure_mode for r in results]
        is_correct = true_mode in top_predictions
        
        total += 1
        if is_correct:
            correct += 1
        
        status = "✓" if is_correct else "✗"
        print(f"\n   {status} Sample: {sample_path.name}")
        print(f"     Ground truth: {true_mode} ({true_system})")
        print(f"     Top prediction: {results[0].failure_mode} ({results[0].probability:.1%})")
        if not is_correct:
            print(f"     All predictions: {top_predictions}")
    
    # Summary
    print("\n" + "=" * 60)
    if total > 0:
        print(f"SUMMARY: {correct}/{total} correct ({100*correct/total:.1f}% accuracy)")
    else:
        print("SUMMARY: No samples processed")
    print("=" * 60)
    
    # Interactive test
    if samples:
        print("\n4. Example diagnostic report:")
        sample_path = random.choice(samples)
        features, true_mode, true_system = load_sample(str(sample_path))
        
        results = engine.diagnose(features, top_k=4)
        report = engine.format_report(results)
        print(report)
        print(f"\n(Ground truth was: {true_mode} in {true_system} system)")


if __name__ == "__main__":
    main()
