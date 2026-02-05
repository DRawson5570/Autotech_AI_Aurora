#!/usr/bin/env python3
"""
Test ML classifier on the generated PyChrono synthetic training data.
Quick experiment to see if the fault signatures are learnable.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / "training_data" / "chrono_synthetic"


def extract_features(time_series: list) -> dict:
    """Extract statistical features from time series data."""
    if not time_series:
        return {}
    
    df = pd.DataFrame(time_series)
    features = {}
    
    # For each numeric column, compute stats
    numeric_cols = ['rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 
                    'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2',
                    'engine_load', 'fuel_pressure', 'tire_pressure',
                    # Extended sensors for tire/brake/trans faults
                    'wheel_slip_events', 'tire_wear_index', 'brake_temp',
                    'decel_rate', 'brake_pedal_travel', 'trans_slip_ratio',
                    'trans_temp', 'shift_quality']
    
    for col in numeric_cols:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                features[f'{col}_mean'] = values.mean()
                features[f'{col}_std'] = values.std()
                features[f'{col}_min'] = values.min()
                features[f'{col}_max'] = values.max()
                features[f'{col}_range'] = values.max() - values.min()
                # Rate of change (derivative)
                if len(values) > 1:
                    features[f'{col}_delta'] = values.iloc[-1] - values.iloc[0]
    
    return features


def load_dataset():
    """Load all JSON files and extract features."""
    manifest_path = DATA_DIR / "manifest.csv"
    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}")
        return None, None
    
    manifest = pd.read_csv(manifest_path)
    print(f"Loading {len(manifest)} samples from manifest...")
    
    all_features = []
    labels = []
    
    for _, row in manifest.iterrows():
        json_path = DATA_DIR / row['file']
        if not json_path.exists():
            continue
            
        with open(json_path) as f:
            data = json.load(f)
        
        features = extract_features(data['time_series'])
        features['severity'] = row['severity']
        features['scenario'] = row['scenario']
        
        all_features.append(features)
        labels.append(row['failure_mode_id'])
    
    X = pd.DataFrame(all_features)
    y = np.array(labels)
    
    return X, y


def main():
    print("=" * 60)
    print("PyChrono Synthetic Data - ML Classification Test")
    print("=" * 60)
    
    # Load data
    X, y = load_dataset()
    if X is None:
        return
    
    print(f"\nDataset: {len(X)} samples, {len(X.columns)} features")
    print(f"Classes: {len(np.unique(y))} failure modes")
    print(f"\nClass distribution:")
    for label, count in pd.Series(y).value_counts().items():
        print(f"  {label}: {count}")
    
    # Encode categorical features
    scenario_encoder = LabelEncoder()
    X['scenario'] = scenario_encoder.fit_transform(X['scenario'].fillna('unknown'))
    
    # Fill NaN with 0
    X = X.fillna(0)
    
    # Encode labels
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )
    
    print(f"\nTrain: {len(X_train)}, Test: {len(X_test)}")
    
    # Train Random Forest
    print("\nTraining Random Forest classifier...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)
    
    # Predict
    y_pred = clf.predict(X_test)
    
    # Results
    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(classification_report(
        y_test, y_pred, 
        target_names=label_encoder.classes_,
        zero_division=0
    ))
    
    # Confusion matrix
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)
    
    # Feature importance
    print("\n" + "=" * 60)
    print("TOP 15 FEATURE IMPORTANCES")
    print("=" * 60)
    importances = pd.Series(clf.feature_importances_, index=X.columns)
    top_features = importances.sort_values(ascending=False).head(15)
    for feat, imp in top_features.items():
        print(f"  {feat}: {imp:.4f}")
    
    # Overall accuracy
    accuracy = (y_pred == y_test).mean()
    print(f"\n{'=' * 60}")
    print(f"OVERALL ACCURACY: {accuracy:.1%}")
    print(f"{'=' * 60}")
    
    return clf, label_encoder


if __name__ == "__main__":
    main()
