"""
Random Forest Diagnostic Classifier

This module implements a Random Forest ensemble classifier for automotive diagnostics.
The classifier takes scanner data (PIDs, DTCs) and predicts the most likely fault.

Key features:
- Handles 50+ PID features simultaneously
- Provides feature importance (which PIDs matter most)
- Interpretable predictions with probability estimates
- Fast inference (no Mitchell queries at runtime)

Training data comes from:
1. Synthetic data generated from fault trees
2. Real shop data (when available)
3. TSB-based cases with elevated weights
"""

import json
import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PIDFeature:
    """Definition of a PID feature for the classifier."""
    pid_id: str              # OBD-II PID code or name
    name: str                # Human-readable name
    unit: str                # Unit of measurement
    min_value: float         # Expected minimum
    max_value: float         # Expected maximum
    normal_range: Tuple[float, float]  # Normal operating range
    
    def normalize(self, value: float) -> float:
        """Normalize value to 0-1 range."""
        if self.max_value == self.min_value:
            return 0.5
        return (value - self.min_value) / (self.max_value - self.min_value)
    
    def is_abnormal(self, value: float) -> bool:
        """Check if value is outside normal range."""
        return value < self.normal_range[0] or value > self.normal_range[1]


# Common PID features used for diagnostics
COMMON_PID_FEATURES: Dict[str, PIDFeature] = {
    "ENGINE_RPM": PIDFeature(
        pid_id="0x0C",
        name="Engine RPM",
        unit="RPM",
        min_value=0,
        max_value=8000,
        normal_range=(650, 7000)
    ),
    "COOLANT_TEMP": PIDFeature(
        pid_id="0x05",
        name="Engine Coolant Temperature",
        unit="°C",
        min_value=-40,
        max_value=215,
        normal_range=(80, 105)
    ),
    "INTAKE_AIR_TEMP": PIDFeature(
        pid_id="0x0F",
        name="Intake Air Temperature",
        unit="°C",
        min_value=-40,
        max_value=215,
        normal_range=(-20, 80)
    ),
    "MAP": PIDFeature(
        pid_id="0x0B",
        name="Manifold Absolute Pressure",
        unit="kPa",
        min_value=0,
        max_value=255,
        normal_range=(20, 105)
    ),
    "THROTTLE_POS": PIDFeature(
        pid_id="0x11",
        name="Throttle Position",
        unit="%",
        min_value=0,
        max_value=100,
        normal_range=(0, 100)
    ),
    "VEHICLE_SPEED": PIDFeature(
        pid_id="0x0D",
        name="Vehicle Speed",
        unit="km/h",
        min_value=0,
        max_value=255,
        normal_range=(0, 200)
    ),
    "SHORT_FUEL_TRIM_1": PIDFeature(
        pid_id="0x06",
        name="Short Term Fuel Trim - Bank 1",
        unit="%",
        min_value=-100,
        max_value=99.2,
        normal_range=(-10, 10)
    ),
    "LONG_FUEL_TRIM_1": PIDFeature(
        pid_id="0x07",
        name="Long Term Fuel Trim - Bank 1",
        unit="%",
        min_value=-100,
        max_value=99.2,
        normal_range=(-10, 10)
    ),
    "O2_VOLTAGE_B1S1": PIDFeature(
        pid_id="0x14",
        name="O2 Sensor Voltage - Bank 1 Sensor 1",
        unit="V",
        min_value=0,
        max_value=1.275,
        normal_range=(0.1, 0.9)
    ),
    "FUEL_PRESSURE": PIDFeature(
        pid_id="0x0A",
        name="Fuel Pressure",
        unit="kPa",
        min_value=0,
        max_value=765,
        normal_range=(250, 500)
    ),
    "TIMING_ADVANCE": PIDFeature(
        pid_id="0x0E",
        name="Timing Advance",
        unit="°",
        min_value=-64,
        max_value=63.5,
        normal_range=(-10, 40)
    ),
    "MAF": PIDFeature(
        pid_id="0x10",
        name="Mass Air Flow Rate",
        unit="g/s",
        min_value=0,
        max_value=655.35,
        normal_range=(2, 200)
    ),
    "CONTROL_MODULE_VOLTAGE": PIDFeature(
        pid_id="0x42",
        name="Control Module Voltage",
        unit="V",
        min_value=0,
        max_value=65.535,
        normal_range=(13.5, 14.8)
    ),
    "CATALYST_TEMP_B1S1": PIDFeature(
        pid_id="0x3C",
        name="Catalyst Temperature - Bank 1 Sensor 1",
        unit="°C",
        min_value=-40,
        max_value=6513.5,
        normal_range=(300, 800)
    ),
    "BAROMETRIC_PRESSURE": PIDFeature(
        pid_id="0x33",
        name="Barometric Pressure",
        unit="kPa",
        min_value=0,
        max_value=255,
        normal_range=(90, 105)
    ),
    # EV-specific PIDs
    "BATTERY_SOC": PIDFeature(
        pid_id="EV_SOC",
        name="Battery State of Charge",
        unit="%",
        min_value=0,
        max_value=100,
        normal_range=(10, 100)
    ),
    "BATTERY_VOLTAGE": PIDFeature(
        pid_id="EV_BATT_V",
        name="HV Battery Voltage",
        unit="V",
        min_value=0,
        max_value=500,
        normal_range=(300, 420)
    ),
    "BATTERY_CURRENT": PIDFeature(
        pid_id="EV_BATT_A",
        name="HV Battery Current",
        unit="A",
        min_value=-500,
        max_value=500,
        normal_range=(-300, 300)
    ),
    "BATTERY_TEMP": PIDFeature(
        pid_id="EV_BATT_TEMP",
        name="HV Battery Temperature",
        unit="°C",
        min_value=-40,
        max_value=100,
        normal_range=(15, 45)
    ),
    "MOTOR_TEMP": PIDFeature(
        pid_id="EV_MOTOR_TEMP",
        name="Drive Motor Temperature",
        unit="°C",
        min_value=-40,
        max_value=200,
        normal_range=(20, 100)
    ),
    "INVERTER_TEMP": PIDFeature(
        pid_id="EV_INV_TEMP",
        name="Inverter Temperature",
        unit="°C",
        min_value=-40,
        max_value=150,
        normal_range=(20, 80)
    ),
}


@dataclass
class TrainingExample:
    """A single training example for the classifier."""
    example_id: str
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    pid_values: Dict[str, float]  # PID name -> value
    dtc_codes: List[str]          # Active DTCs
    fault_label: str              # Ground truth fault node ID
    source: str = "synthetic"     # "synthetic", "real", "tsb"
    weight: float = 1.0           # Sample weight for training
    
    def to_feature_vector(self, feature_names: List[str]) -> np.ndarray:
        """Convert to numpy feature vector."""
        vector = []
        for name in feature_names:
            if name in self.pid_values:
                feature = COMMON_PID_FEATURES.get(name)
                if feature:
                    vector.append(feature.normalize(self.pid_values[name]))
                else:
                    vector.append(self.pid_values[name])
            elif name.startswith("DTC_"):
                # Binary feature for DTC presence
                dtc = name[4:]  # Remove "DTC_" prefix
                vector.append(1.0 if dtc in self.dtc_codes else 0.0)
            else:
                vector.append(0.0)  # Missing value
        return np.array(vector)


class DiagnosticClassifier:
    """
    Random Forest classifier for fault diagnosis.
    
    Uses scikit-learn RandomForestClassifier internally but wraps it
    with automotive-specific feature engineering and interpretation.
    """
    
    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 15,
        min_samples_leaf: int = 5,
        class_weight: str = "balanced"
    ):
        """
        Initialize the classifier.
        
        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum tree depth (prevents overfitting)
            min_samples_leaf: Minimum samples required at leaf
            class_weight: How to handle class imbalance
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.class_weight = class_weight
        
        self.model = None
        self.feature_names: List[str] = []
        self.label_encoder: Dict[str, int] = {}
        self.label_decoder: Dict[int, str] = {}
        self.feature_importances: Dict[str, float] = {}
        
        self.is_trained = False
        self.training_stats: Dict[str, Any] = {}
    
    def _prepare_features(
        self, 
        examples: List[TrainingExample]
    ) -> Tuple[np.ndarray, np.ndarray, List[float]]:
        """
        Prepare feature matrix and labels from training examples.
        
        Returns:
            X: Feature matrix (n_samples x n_features)
            y: Label vector (n_samples,)
            weights: Sample weights (n_samples,)
        """
        # Determine feature names from all examples
        all_pids = set()
        all_dtcs = set()
        all_labels = set()
        
        for ex in examples:
            all_pids.update(ex.pid_values.keys())
            all_dtcs.update(ex.dtc_codes)
            all_labels.add(ex.fault_label)
        
        # Build feature names: PIDs first, then DTCs
        self.feature_names = sorted(list(all_pids)) + [f"DTC_{dtc}" for dtc in sorted(all_dtcs)]
        
        # Build label encoding
        self.label_encoder = {label: i for i, label in enumerate(sorted(all_labels))}
        self.label_decoder = {i: label for label, i in self.label_encoder.items()}
        
        # Build feature matrix
        X = np.array([ex.to_feature_vector(self.feature_names) for ex in examples])
        y = np.array([self.label_encoder[ex.fault_label] for ex in examples])
        weights = [ex.weight for ex in examples]
        
        return X, y, weights
    
    def train(
        self, 
        examples: List[TrainingExample],
        validation_split: float = 0.2
    ) -> Dict[str, Any]:
        """
        Train the classifier on examples.
        
        Args:
            examples: List of training examples
            validation_split: Fraction of data for validation
            
        Returns:
            Training statistics including accuracy
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, classification_report
        except ImportError:
            raise ImportError("scikit-learn required. Install with: pip install scikit-learn")
        
        logger.info(f"Training classifier on {len(examples)} examples")
        
        # Prepare data
        X, y, weights = self._prepare_features(examples)
        
        # Split for validation
        X_train, X_val, y_train, y_val, w_train, w_val = train_test_split(
            X, y, weights,
            test_size=validation_split,
            random_state=42,
            stratify=y
        )
        
        # Train Random Forest
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            class_weight=self.class_weight,
            random_state=42,
            n_jobs=-1  # Use all cores
        )
        
        self.model.fit(X_train, y_train, sample_weight=w_train)
        
        # Evaluate
        y_pred_train = self.model.predict(X_train)
        y_pred_val = self.model.predict(X_val)
        
        train_acc = accuracy_score(y_train, y_pred_train)
        val_acc = accuracy_score(y_val, y_pred_val)
        
        # Feature importance
        self.feature_importances = {
            name: imp 
            for name, imp in zip(self.feature_names, self.model.feature_importances_)
        }
        
        # Sort by importance
        self.feature_importances = dict(
            sorted(self.feature_importances.items(), key=lambda x: x[1], reverse=True)
        )
        
        self.is_trained = True
        
        self.training_stats = {
            "n_examples": len(examples),
            "n_features": len(self.feature_names),
            "n_classes": len(self.label_encoder),
            "train_accuracy": train_acc,
            "validation_accuracy": val_acc,
            "top_features": list(self.feature_importances.items())[:10],
            "trained_at": datetime.now().isoformat(),
        }
        
        logger.info(f"Training complete. Train acc: {train_acc:.3f}, Val acc: {val_acc:.3f}")
        
        return self.training_stats
    
    def predict(
        self,
        pid_values: Dict[str, float],
        dtc_codes: List[str] = None,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Predict fault from scanner data.
        
        Args:
            pid_values: Dictionary of PID readings
            dtc_codes: List of active DTCs
            top_k: Number of top predictions to return
            
        Returns:
            List of (fault_id, probability) tuples
        """
        if not self.is_trained:
            raise RuntimeError("Classifier not trained. Call train() first.")
        
        # Create temporary example for feature extraction
        example = TrainingExample(
            example_id="predict",
            vehicle_year=0,
            vehicle_make="",
            vehicle_model="",
            pid_values=pid_values,
            dtc_codes=dtc_codes or [],
            fault_label=""  # Unknown
        )
        
        # Get feature vector
        X = example.to_feature_vector(self.feature_names).reshape(1, -1)
        
        # Get probability predictions
        probs = self.model.predict_proba(X)[0]
        
        # Get top-k predictions
        top_indices = np.argsort(probs)[::-1][:top_k]
        
        predictions = [
            (self.label_decoder[idx], probs[idx])
            for idx in top_indices
        ]
        
        return predictions
    
    def explain_prediction(
        self,
        pid_values: Dict[str, float],
        dtc_codes: List[str] = None,
        top_features: int = 5
    ) -> Dict[str, Any]:
        """
        Explain a prediction by showing contributing features.
        
        Returns:
            Dictionary with prediction, probabilities, and feature contributions
        """
        predictions = self.predict(pid_values, dtc_codes)
        
        # Find which features contributed most to this prediction
        # (simplified - full SHAP values would be better)
        contributing_features = []
        for name, importance in list(self.feature_importances.items())[:top_features]:
            if name in pid_values:
                feature = COMMON_PID_FEATURES.get(name)
                value = pid_values[name]
                is_abnormal = feature.is_abnormal(value) if feature else False
                contributing_features.append({
                    "feature": name,
                    "value": value,
                    "importance": importance,
                    "abnormal": is_abnormal
                })
            elif name.startswith("DTC_"):
                dtc = name[4:]
                if dtc in (dtc_codes or []):
                    contributing_features.append({
                        "feature": name,
                        "value": "present",
                        "importance": importance,
                        "abnormal": True
                    })
        
        return {
            "predictions": predictions,
            "most_likely": predictions[0] if predictions else None,
            "contributing_features": contributing_features,
        }
    
    def save(self, path: str) -> None:
        """Save trained model to file."""
        if not self.is_trained:
            raise RuntimeError("No trained model to save.")
        
        data = {
            "model": self.model,
            "feature_names": self.feature_names,
            "label_encoder": self.label_encoder,
            "label_decoder": self.label_decoder,
            "feature_importances": self.feature_importances,
            "training_stats": self.training_stats,
            "params": {
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "min_samples_leaf": self.min_samples_leaf,
                "class_weight": self.class_weight,
            }
        }
        
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"Model saved to {path}")
    
    def load(self, path: str) -> None:
        """Load trained model from file."""
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        self.model = data["model"]
        self.feature_names = data["feature_names"]
        self.label_encoder = data["label_encoder"]
        self.label_decoder = data["label_decoder"]
        self.feature_importances = data["feature_importances"]
        self.training_stats = data.get("training_stats", {})
        
        params = data.get("params", {})
        self.n_estimators = params.get("n_estimators", self.n_estimators)
        self.max_depth = params.get("max_depth", self.max_depth)
        self.min_samples_leaf = params.get("min_samples_leaf", self.min_samples_leaf)
        self.class_weight = params.get("class_weight", self.class_weight)
        
        self.is_trained = True
        logger.info(f"Model loaded from {path}")


class EnsembleClassifier:
    """
    Ensemble of multiple classifiers for improved accuracy.
    
    Combines Random Forest with XGBoost for better generalization.
    """
    
    def __init__(self):
        self.rf_classifier = DiagnosticClassifier()
        self.xgb_classifier = None  # Will initialize if xgboost available
        self.weights = {"rf": 0.6, "xgb": 0.4}
    
    def train(self, examples: List[TrainingExample]) -> Dict[str, Any]:
        """Train all classifiers in the ensemble."""
        stats = {}
        
        # Train Random Forest
        stats["rf"] = self.rf_classifier.train(examples)
        
        # Try to train XGBoost if available
        try:
            import xgboost as xgb
            # XGBoost training would go here
            stats["xgb"] = {"status": "not_implemented"}
        except ImportError:
            stats["xgb"] = {"status": "not_available"}
            self.weights = {"rf": 1.0}
        
        return stats
    
    def predict(
        self,
        pid_values: Dict[str, float],
        dtc_codes: List[str] = None,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Ensemble prediction combining all classifiers."""
        # Get RF predictions
        rf_preds = self.rf_classifier.predict(pid_values, dtc_codes, top_k=top_k * 2)
        
        # Combine predictions (weighted average)
        # For now, just return RF since XGBoost not implemented
        return rf_preds[:top_k]
