#!/usr/bin/env python3
"""
Train ML model from PyChrono synthetic data.

Loads the generated chrono_synthetic data and trains both:
1. Random Forest classifier (fast, interpretable)
2. Saves to the models/ directory for use by DiagnosticEngine

Usage:
    conda activate chrono_test
    python train_from_chrono.py
    
    # Or with specific output:
    python train_from_chrono.py --output ../models
"""

import json
import pickle
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

import warnings
warnings.filterwarnings('ignore')

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "training_data" / "chrono_synthetic"
MODELS_DIR = SCRIPT_DIR.parent / "models"


def extract_features(time_series: list) -> dict:
    """
    Extract statistical features from time series data.
    
    These features capture:
    - Steady-state values (mean, final)
    - Variability (std, range)
    - Trends (delta from start to end)
    - Extremes (min, max)
    """
    if not time_series:
        return {}
    
    df = pd.DataFrame(time_series)
    features = {}
    
    # All numeric sensor columns
    sensor_cols = [
        # Core engine/powertrain
        'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
        # Cooling system
        'coolant_temp',
        # Fuel system
        'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2', 'fuel_pressure',
        # Tires
        'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
        # Brakes
        'brake_temp', 'decel_rate', 'brake_pedal_travel',
        # Transmission
        'trans_slip_ratio', 'trans_temp', 'shift_quality',
    ]
    
    for col in sensor_cols:
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


def load_all_json_files() -> Tuple[pd.DataFrame, np.ndarray]:
    """
    Load ALL JSON files directly (not just from manifest).
    
    This handles cases where manifest is incomplete.
    """
    json_files = list(DATA_DIR.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")
    
    all_features = []
    labels = []
    
    for json_path in json_files:
        try:
            with open(json_path) as f:
                data = json.load(f)
            
            features = extract_features(data['time_series'])
            features['severity'] = data.get('severity', 0.5)
            features['scenario'] = data.get('scenario', 'unknown')
            
            all_features.append(features)
            labels.append(data['failure_mode_id'])
        except Exception as e:
            print(f"  Warning: Could not load {json_path.name}: {e}")
            continue
    
    X = pd.DataFrame(all_features)
    y = np.array(labels)
    
    return X, y


def train_random_forest(
    X: pd.DataFrame, 
    y: np.ndarray,
    label_encoder: LabelEncoder,
    n_estimators: int = 200,
    max_depth: int = 20,
) -> Tuple[RandomForestClassifier, Dict]:
    """
    Train Random Forest classifier.
    
    Returns trained model and metrics dict.
    """
    print("\n" + "=" * 60)
    print("TRAINING RANDOM FOREST")
    print("=" * 60)
    
    # Encode categorical
    X_train = X.copy()
    scenario_encoder = LabelEncoder()
    X_train['scenario'] = scenario_encoder.fit_transform(X_train['scenario'].fillna('unknown'))
    X_train = X_train.fillna(0)
    
    # Encode labels
    y_encoded = label_encoder.transform(y)
    
    # Train/test split
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_train, y_encoded, 
        test_size=0.2, 
        random_state=42, 
        stratify=y_encoded
    )
    
    print(f"Train samples: {len(X_tr)}")
    print(f"Test samples: {len(X_te)}")
    print(f"Features: {X_train.shape[1]}")
    print(f"Classes: {len(label_encoder.classes_)}")
    
    # Train
    print(f"\nTraining with n_estimators={n_estimators}, max_depth={max_depth}...")
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=3,
        min_samples_split=5,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_tr, y_tr)
    
    # Evaluate
    y_pred_train = clf.predict(X_tr)
    y_pred_test = clf.predict(X_te)
    
    train_acc = accuracy_score(y_tr, y_pred_train)
    test_acc = accuracy_score(y_te, y_pred_test)
    
    # Cross-validation
    cv_scores = cross_val_score(clf, X_train, y_encoded, cv=5)
    
    print(f"\nResults:")
    print(f"  Train Accuracy: {train_acc:.1%}")
    print(f"  Test Accuracy: {test_acc:.1%}")
    print(f"  CV Accuracy: {cv_scores.mean():.1%} (+/- {cv_scores.std():.1%})")
    
    # Classification report
    print("\n" + "-" * 60)
    print("CLASSIFICATION REPORT")
    print("-" * 60)
    print(classification_report(
        y_te, y_pred_test,
        target_names=label_encoder.classes_,
        zero_division=0
    ))
    
    # Feature importance
    print("\n" + "-" * 60)
    print("TOP 15 FEATURE IMPORTANCES")
    print("-" * 60)
    importances = pd.Series(clf.feature_importances_, index=X_train.columns)
    top_features = importances.sort_values(ascending=False).head(15)
    for feat, imp in top_features.items():
        print(f"  {feat}: {imp:.4f}")
    
    metrics = {
        'train_accuracy': train_acc,
        'test_accuracy': test_acc,
        'cv_accuracy_mean': cv_scores.mean(),
        'cv_accuracy_std': cv_scores.std(),
        'n_samples': len(X_train),
        'n_features': X_train.shape[1],
        'n_classes': len(label_encoder.classes_),
        'feature_names': list(X_train.columns),
        'class_names': list(label_encoder.classes_),
    }
    
    return clf, metrics


def save_model(
    clf: RandomForestClassifier,
    metrics: Dict,
    output_dir: Path,
    label_encoder: LabelEncoder,
):
    """Save trained model and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save model
    model_path = output_dir / f"rf_chrono_{timestamp}.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(clf, f)
    print(f"\n✓ Saved model: {model_path}")
    
    # Save latest symlink-style
    latest_path = output_dir / "rf_chrono_latest.pkl"
    with open(latest_path, 'wb') as f:
        pickle.dump(clf, f)
    print(f"✓ Saved model: {latest_path}")
    
    # Save label encoder
    encoder_path = output_dir / "rf_chrono_label_encoder.pkl"
    with open(encoder_path, 'wb') as f:
        pickle.dump(label_encoder, f)
    print(f"✓ Saved encoder: {encoder_path}")
    
    # Save metadata
    metadata = {
        'timestamp': timestamp,
        'source': 'chrono_synthetic',
        **metrics
    }
    
    metadata_path = output_dir / f"rf_chrono_metadata_{timestamp}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata: {metadata_path}")
    
    # Latest metadata
    latest_meta_path = output_dir / "rf_chrono_metadata_latest.json"
    with open(latest_meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Saved metadata: {latest_meta_path}")


def main():
    parser = argparse.ArgumentParser(description="Train ML model from chrono synthetic data")
    parser.add_argument("--output", type=str, default=str(MODELS_DIR),
                       help="Output directory for models")
    parser.add_argument("--n-estimators", type=int, default=200,
                       help="Number of trees in Random Forest")
    parser.add_argument("--max-depth", type=int, default=20,
                       help="Maximum tree depth")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    print("=" * 60)
    print("CHRONO SYNTHETIC DATA - ML TRAINING PIPELINE")
    print("=" * 60)
    print(f"Data directory: {DATA_DIR}")
    print(f"Output directory: {output_dir}")
    
    # Check data exists
    if not DATA_DIR.exists():
        print(f"\n✗ Data directory not found: {DATA_DIR}")
        return 1
    
    # Load data
    print("\n--- Loading Data ---")
    X, y = load_all_json_files()
    
    if len(X) < 100:
        print(f"\n✗ Insufficient data: {len(X)} samples (need at least 100)")
        return 1
    
    print(f"\nLoaded {len(X)} samples with {X.shape[1]} features")
    print(f"\nClass distribution:")
    for label, count in pd.Series(y).value_counts().head(15).items():
        print(f"  {label}: {count}")
    if len(pd.Series(y).value_counts()) > 15:
        print(f"  ... and {len(pd.Series(y).value_counts()) - 15} more classes")
    
    # Fit label encoder on all classes
    label_encoder = LabelEncoder()
    label_encoder.fit(y)
    
    # Train Random Forest
    clf, metrics = train_random_forest(
        X, y, label_encoder,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
    )
    
    # Save
    save_model(clf, metrics, output_dir, label_encoder)
    
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE!")
    print("=" * 60)
    print(f"Final Test Accuracy: {metrics['test_accuracy']:.1%}")
    print(f"Models saved to: {output_dir}")
    
    return 0


if __name__ == "__main__":
    exit(main())
