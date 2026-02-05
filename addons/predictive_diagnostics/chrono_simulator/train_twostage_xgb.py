#!/usr/bin/env python3
"""
Two-Stage XGBoost Classifier for Vehicle Diagnostics

Stage 1: Predict which SYSTEM has the fault (10 classes)
Stage 2: Predict which FAILURE MODE within that system (2-10 classes each)

This approach:
- Matches how technicians diagnose (system first, then specific fault)
- Reduces problem complexity (10 classes then 2-10, instead of 45 at once)
- Should significantly improve accuracy

Usage:
    python train_twostage_xgb.py
    
Output:
    ../models/twostage_xgb.pkl
"""

import json
import pickle
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, accuracy_score
import xgboost as xgb

import warnings
warnings.filterwarnings('ignore')

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "training_data" / "chrono_synthetic"
MODELS_DIR = SCRIPT_DIR.parent / "models"

# System mapping - maps failure mode prefixes to canonical system names
SYSTEM_MAP = {
    'cooling': 'cooling',
    'ect': 'cooling',
    'radiator': 'cooling',
    'water': 'cooling',
    'fuel': 'fuel',
    'ignition': 'ignition',
    'alternator': 'charging',
    'battery': 'charging',
    'brakes': 'brakes',
    'tires': 'tires',
    'trans': 'transmission',
    'tcc': 'transmission',
    'transmission': 'transmission',
    'starter': 'starting',
    'starting': 'starting',
    'oil': 'engine',
    'engine': 'engine',
    'tesla': 'ev',
    'ev': 'ev',
    'emissions': 'emissions',
    'exhaust': 'emissions',
    # New systems
    'steering': 'steering',
    'suspension': 'suspension',
    'hvac': 'hvac',
    'abs': 'abs',
    'airbag': 'airbag',
    'lighting': 'lighting',
    'body_electrical': 'body_electrical',
    'hybrid': 'hybrid',
}

# Sensors for feature extraction - comprehensive list for all systems
SENSOR_COLS = [
    # Core engine/powertrain
    'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
    'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2',
    'fuel_pressure', 'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
    'brake_temp', 'decel_rate', 'brake_pedal_travel',
    'trans_slip_ratio', 'trans_temp', 'shift_quality',
    
    # Steering system
    'steering_effort', 'ps_pump_pressure', 'ps_fluid_temp', 'steering_assist',
    'ps_fluid_level', 'steering_play', 'toe_angle', 'camber_angle',
    'steering_wheel_offset',
    
    # Suspension system
    'suspension_oscillation', 'body_roll', 'nose_dive', 'ride_height_variance',
    'strut_noise_level', 'steering_feel', 'alignment_drift', 'suspension_play',
    'camber_variance', 'clunk_frequency', 'sway_bar_noise', 'cornering_stability',
    'ride_height_fl',
    
    # HVAC system
    'ac_pressure_high', 'ac_pressure_low', 'cabin_temp_delta', 'ac_clutch_cycling',
    'ac_superheat', 'blend_door_position', 'blend_door_commanded', 'cabin_temp_error',
    'blower_speed_actual', 'blower_current', 'airflow_volume',
    'heater_inlet_temp', 'heater_outlet_temp', 'cabin_heat_output',
    
    # ABS system
    'wss_fl', 'wss_fr', 'wss_rl', 'wss_rr', 'wss_variance', 'abs_activation_false',
    'abs_lamp', 'abs_pump_pressure', 'abs_pump_current', 'abs_response_time',
    'can_bus_errors_abs', 'traction_lamp', 'stability_lamp',
    'wss_rr_variance', 'wss_rr_dropouts',
    
    # Airbag/SRS system
    'airbag_lamp', 'driver_airbag_resistance', 'horn_function', 'cruise_buttons',
    'seat_occupancy_detected', 'passenger_airbag_status', 'srs_dtc_count',
    'srs_readiness', 'can_bus_errors_srs',
    
    # Lighting system
    'headlight_fl_current', 'headlight_fl_status', 'headlight_fr_status',
    'lighting_dtc', 'hid_ballast_output', 'hid_igniter_attempts',
    'turn_signal_frequency', 'turn_signal_rr_current', 'turn_signal_load',
    'bcm_lighting_status', 'auto_headlight_function', 'daytime_running_lights',
    'can_bus_errors_bcm',
    
    # Body electrical
    'window_fl_speed', 'window_fl_current', 'window_fl_position_error',
    'door_fl_lock_status', 'door_fl_lock_current', 'central_lock_error',
    'bcm_status', 'interior_lights_error', 'wiper_error', 'accessory_power_error',
    'key_off_current', 'battery_voltage_overnight', 'battery_state_of_charge',
    'relay_state_error', 'controlled_circuit_status', 'relay_coil_resistance',
    
    # Hybrid system
    'hv_battery_soc_max', 'hv_battery_capacity', 'ev_range_estimate',
    'hv_battery_temp', 'cell_voltage_variance', 'inverter_temp', 'hv_system_lamp',
    'electric_motor_available', 'regenerative_braking', 'hv_coolant_flow',
    'power_limit_active', 'aux_battery_voltage', 'aux_battery_cca', 'ready_light_delay',
    
    # EV system
    'charge_port_status', 'charge_pilot_signal', 'charge_session_error',
    'ac_charge_power', 'charger_temp', 'charge_rate_ac',
    'dcdc_output_voltage', 'dcdc_status',
    
    # Additional brake sensors
    'brake_temp_fl', 'brake_drag', 'fuel_economy_loss', 'wheel_pull',
    'brake_pressure', 'brake_fluid_level', 'brake_vibration',
    'steering_wheel_shake', 'rotor_runout',
    
    # Additional starting sensors
    'starter_engage_time', 'solenoid_click', 'starting_current',
    'gear_position_signal', 'starter_enable', 'shift_indicator_error',
]


def get_system(failure_mode_id: str) -> str:
    """Map failure mode to system."""
    prefix = failure_mode_id.split('.')[0]
    return SYSTEM_MAP.get(prefix, 'other')


def extract_features(time_series: list) -> Dict[str, float]:
    """Extract statistical features from time series."""
    if not time_series:
        return {}
    
    df = pd.DataFrame(time_series)
    features = {}
    
    for col in SENSOR_COLS:
        if col in df.columns:
            values = df[col].dropna()
            if len(values) > 0:
                features[f'{col}_mean'] = values.mean()
                features[f'{col}_std'] = values.std() if len(values) > 1 else 0.0
                features[f'{col}_min'] = values.min()
                features[f'{col}_max'] = values.max()
                features[f'{col}_range'] = values.max() - values.min()
                features[f'{col}_final'] = values.iloc[-1]
                if len(values) > 1:
                    features[f'{col}_delta'] = values.iloc[-1] - values.iloc[0]
                    diff = values.diff().abs()
                    features[f'{col}_rate_max'] = diff.max() if len(diff) > 0 else 0.0
    
    return features


def load_data() -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Load all data and return features, failure_modes, systems."""
    json_files = list(DATA_DIR.glob("*.json"))
    print(f"Loading {len(json_files)} files...")
    
    all_features = []
    failure_modes = []
    systems = []
    
    for i, json_path in enumerate(json_files):
        if i % 5000 == 0:
            print(f"  Loaded {i}/{len(json_files)}...")
        
        try:
            with open(json_path) as f:
                data = json.load(f)
            
            features = extract_features(data['time_series'])
            features['severity'] = data.get('severity', 0.5)
            
            failure_id = data['failure_mode_id']
            system = get_system(failure_id)
            
            all_features.append(features)
            failure_modes.append(failure_id)
            systems.append(system)
            
        except Exception as e:
            continue
    
    X = pd.DataFrame(all_features).fillna(0)
    y_failure = np.array(failure_modes)
    y_system = np.array(systems)
    
    print(f"Loaded {len(X)} samples")
    print(f"Systems: {np.unique(y_system)}")
    print(f"Failure modes: {len(np.unique(y_failure))}")
    
    return X, y_failure, y_system


def train_system_classifier(X: pd.DataFrame, y_system: np.ndarray) -> Tuple[xgb.XGBClassifier, LabelEncoder, StandardScaler, float]:
    """Train Stage 1: System classifier."""
    print("\n" + "="*60)
    print("STAGE 1: Training SYSTEM Classifier")
    print("="*60)
    
    # Encode labels
    le = LabelEncoder()
    y_encoded = le.fit_transform(y_system)
    
    print(f"Classes: {list(le.classes_)}")
    print(f"Class distribution:")
    for cls in le.classes_:
        count = (y_system == cls).sum()
        print(f"  {cls}: {count} ({100*count/len(y_system):.1f}%)")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
    )
    
    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train XGBoost
    clf = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    
    clf.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\nSystem classifier accuracy: {accuracy:.1%}")
    print("\nPer-system accuracy:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))
    
    return clf, le, scaler, accuracy


def train_failure_classifiers(
    X: pd.DataFrame, 
    y_failure: np.ndarray, 
    y_system: np.ndarray
) -> Dict[str, Tuple[xgb.XGBClassifier, LabelEncoder, StandardScaler, float]]:
    """Train Stage 2: Per-system failure mode classifiers."""
    print("\n" + "="*60)
    print("STAGE 2: Training Per-System FAILURE MODE Classifiers")
    print("="*60)
    
    system_models = {}
    
    for system in np.unique(y_system):
        mask = y_system == system
        X_sys = X[mask]
        y_sys = y_failure[mask]
        
        unique_failures = np.unique(y_sys)
        
        # Skip systems with only 1 failure mode
        if len(unique_failures) < 2:
            print(f"\n{system}: Only 1 failure mode ({unique_failures[0]}), skipping")
            continue
        
        print(f"\n{system}: {len(X_sys)} samples, {len(unique_failures)} failure modes")
        
        # Encode
        le = LabelEncoder()
        y_encoded = le.fit_transform(y_sys)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X_sys, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # Scale
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train
        clf = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        
        clf.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = clf.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"  Accuracy: {accuracy:.1%}")
        for fm in le.classes_:
            count = (y_sys == fm).sum()
            print(f"    {fm}: {count}")
        
        system_models[system] = (clf, le, scaler, accuracy)
    
    return system_models


def evaluate_twostage(
    X: pd.DataFrame,
    y_failure: np.ndarray,
    y_system: np.ndarray,
    system_clf: xgb.XGBClassifier,
    system_le: LabelEncoder,
    system_scaler: StandardScaler,
    failure_models: Dict,
) -> float:
    """Evaluate complete two-stage pipeline."""
    print("\n" + "="*60)
    print("EVALUATING COMPLETE TWO-STAGE PIPELINE")
    print("="*60)
    
    # Use same test split
    _, X_test, _, y_fail_test, _, y_sys_test = train_test_split(
        X, y_failure, y_system, test_size=0.2, random_state=42, stratify=y_system
    )
    
    # Stage 1: Predict system
    X_test_scaled = system_scaler.transform(X_test)
    predicted_systems = system_le.inverse_transform(system_clf.predict(X_test_scaled))
    
    # Stage 2: Predict failure mode within predicted system
    correct = 0
    total = 0
    
    for i, (pred_sys, true_fail) in enumerate(zip(predicted_systems, y_fail_test)):
        if pred_sys in failure_models:
            clf, le, scaler, _ = failure_models[pred_sys]
            x_scaled = scaler.transform(X_test.iloc[[i]])
            pred_fail = le.inverse_transform(clf.predict(x_scaled))[0]
        else:
            # System with single failure mode - use the system name to infer
            pred_fail = pred_sys
        
        if pred_fail == true_fail:
            correct += 1
        total += 1
    
    accuracy = correct / total
    print(f"\nTwo-stage pipeline accuracy: {accuracy:.1%}")
    print(f"Correct: {correct}/{total}")
    
    # Compare with actual system accuracy
    sys_correct = (predicted_systems == y_sys_test).sum()
    print(f"System prediction accuracy: {100*sys_correct/len(y_sys_test):.1%}")
    
    return accuracy


def save_model(
    system_clf: xgb.XGBClassifier,
    system_le: LabelEncoder,
    system_scaler: StandardScaler,
    failure_models: Dict,
    feature_names: List[str],
    metrics: Dict,
):
    """Save the complete two-stage model."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    model_data = {
        'system_clf': system_clf,
        'system_le': system_le,
        'system_scaler': system_scaler,
        'failure_models': failure_models,
        'feature_names': feature_names,
        'metrics': metrics,
        'timestamp': datetime.now().isoformat(),
    }
    
    output_path = MODELS_DIR / "twostage_xgb.pkl"
    with open(output_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"\n✓ Saved model: {output_path}")
    
    # Save metadata
    meta_path = MODELS_DIR / "twostage_xgb_metadata.json"
    meta = {
        'timestamp': model_data['timestamp'],
        'systems': list(system_le.classes_),
        'failure_modes_per_system': {
            sys: list(fm[1].classes_) for sys, fm in failure_models.items()
        },
        'metrics': metrics,
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"✓ Saved metadata: {meta_path}")


def main():
    parser = argparse.ArgumentParser(description="Train two-stage XGBoost classifier")
    args = parser.parse_args()
    
    print("="*60)
    print("TWO-STAGE XGBOOST CLASSIFIER")
    print("="*60)
    
    # Load data
    X, y_failure, y_system = load_data()
    
    # Train Stage 1
    system_clf, system_le, system_scaler, sys_acc = train_system_classifier(X, y_system)
    
    # Train Stage 2
    failure_models = train_failure_classifiers(X, y_failure, y_system)
    
    # Evaluate combined pipeline
    pipeline_acc = evaluate_twostage(
        X, y_failure, y_system,
        system_clf, system_le, system_scaler,
        failure_models
    )
    
    # Save
    metrics = {
        'system_accuracy': sys_acc,
        'pipeline_accuracy': pipeline_acc,
        'n_samples': len(X),
        'n_systems': len(system_le.classes_),
        'n_failure_modes': len(np.unique(y_failure)),
    }
    
    save_model(
        system_clf, system_le, system_scaler,
        failure_models, list(X.columns), metrics
    )
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"System classifier: {sys_acc:.1%}")
    print(f"Two-stage pipeline: {pipeline_acc:.1%}")
    print(f"Improvement over RF (55%): {pipeline_acc - 0.55:+.1%}")


if __name__ == "__main__":
    main()
