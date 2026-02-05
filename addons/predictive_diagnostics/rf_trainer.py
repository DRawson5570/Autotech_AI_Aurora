"""
Random Forest Training Pipeline

This module trains a Random Forest classifier on physics-based synthetic data
to RECOGNIZE failure modes from PID patterns.

Key insight: The RF doesn't learn physics - it learns to pattern match.
The physics simulator tells it "this is what alternator failure looks like"
and the RF learns to recognize that pattern.

Usage:
    from rf_trainer import RFTrainer
    
    trainer = RFTrainer()
    model = trainer.train()
    trainer.save_model("models/rf_model.pkl")
    
    # Or CLI:
    python rf_trainer.py --samples 100 --output models/
"""

import os
import json
import pickle
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np

# Scikit-learn imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)
from sklearn.preprocessing import StandardScaler

try:
    from .synthetic_data import PhysicsBasedGenerator, PhysicsDataConfig, PHYSICS_FAILURE_MODES
except ImportError:
    from synthetic_data import PhysicsBasedGenerator, PhysicsDataConfig, PHYSICS_FAILURE_MODES

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for RF training."""
    # Data generation
    samples_per_class: int = 100
    test_split: float = 0.2
    random_seed: int = 42
    
    # RF hyperparameters
    n_estimators: int = 100
    max_depth: int = 15
    min_samples_leaf: int = 5
    min_samples_split: int = 10
    max_features: str = "sqrt"  # sqrt of n_features
    
    # Feature selection
    feature_importance_threshold: float = 0.001  # Drop features below this
    
    # Output
    output_dir: str = "models"


@dataclass
class TrainingResult:
    """Results from training run."""
    success: bool
    training_time_sec: float
    n_samples: int
    n_features: int
    n_classes: int
    
    # Performance metrics
    train_accuracy: float = 0.0
    test_accuracy: float = 0.0
    cv_accuracy_mean: float = 0.0
    cv_accuracy_std: float = 0.0
    f1_weighted: float = 0.0
    
    # Feature analysis
    top_features: List[Tuple[str, float]] = field(default_factory=list)
    
    # Model info
    model_path: Optional[str] = None
    class_names: List[str] = field(default_factory=list)
    feature_names: List[str] = field(default_factory=list)
    
    # Errors
    error_message: Optional[str] = None
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            "=== Training Results ===",
            f"Success: {self.success}",
            f"Samples: {self.n_samples}",
            f"Features: {self.n_features}",
            f"Classes: {self.n_classes}",
            "",
            "Performance:",
            f"  Train Accuracy: {self.train_accuracy:.2%}",
            f"  Test Accuracy: {self.test_accuracy:.2%}",
            f"  CV Accuracy: {self.cv_accuracy_mean:.2%} (+/- {self.cv_accuracy_std:.2%})",
            f"  F1 (weighted): {self.f1_weighted:.3f}",
            "",
            "Top 10 Features:",
        ]
        for fname, importance in self.top_features[:10]:
            lines.append(f"  {fname}: {importance:.4f}")
        
        return "\n".join(lines)


class RFTrainer:
    """
    Trains Random Forest on physics-based synthetic data.
    """
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()
        np.random.seed(self.config.random_seed)
        
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.class_names: List[str] = []
        
    def train(
        self,
        X: np.ndarray = None,
        y: np.ndarray = None,
        feature_names: List[str] = None,
        class_names: List[str] = None,
        verbose: bool = True,
    ) -> TrainingResult:
        """
        Train the Random Forest classifier.
        
        If X, y not provided, generates synthetic data first.
        """
        start_time = datetime.now()
        
        try:
            # Generate data if not provided
            if X is None or y is None:
                if verbose:
                    print("Generating synthetic training data...")
                
                gen_config = PhysicsDataConfig(
                    samples_per_class=self.config.samples_per_class,
                    random_seed=self.config.random_seed,
                )
                generator = PhysicsBasedGenerator(gen_config)
                X, y, feature_names, class_names = generator.generate_dataset(verbose=verbose)
            
            self.feature_names = feature_names
            self.class_names = class_names
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.config.test_split,
                random_state=self.config.random_seed,
                stratify=y,
            )
            
            if verbose:
                print(f"\nTraining on {len(X_train)} samples, testing on {len(X_test)}")
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train Random Forest
            if verbose:
                print("Training Random Forest...")
            
            self.model = RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                min_samples_leaf=self.config.min_samples_leaf,
                min_samples_split=self.config.min_samples_split,
                max_features=self.config.max_features,
                random_state=self.config.random_seed,
                n_jobs=-1,  # Use all cores
            )
            
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            train_acc = accuracy_score(y_train, self.model.predict(X_train_scaled))
            test_acc = accuracy_score(y_test, self.model.predict(X_test_scaled))
            
            # Cross-validation
            cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
            
            # F1 score
            y_pred = self.model.predict(X_test_scaled)
            f1 = f1_score(y_test, y_pred, average="weighted")
            
            # Feature importance
            importances = self.model.feature_importances_
            feature_importance = sorted(
                zip(feature_names, importances),
                key=lambda x: x[1],
                reverse=True
            )
            
            training_time = (datetime.now() - start_time).total_seconds()
            
            result = TrainingResult(
                success=True,
                training_time_sec=training_time,
                n_samples=len(X),
                n_features=len(feature_names),
                n_classes=len(class_names),
                train_accuracy=train_acc,
                test_accuracy=test_acc,
                cv_accuracy_mean=cv_scores.mean(),
                cv_accuracy_std=cv_scores.std(),
                f1_weighted=f1,
                top_features=feature_importance,
                class_names=class_names,
                feature_names=feature_names,
            )
            
            if verbose:
                print(result.summary())
                print("\nClassification Report:")
                print(classification_report(
                    y_test, y_pred,
                    target_names=class_names,
                    zero_division=0
                ))
            
            return result
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            training_time = (datetime.now() - start_time).total_seconds()
            return TrainingResult(
                success=False,
                training_time_sec=training_time,
                n_samples=0,
                n_features=0,
                n_classes=0,
                error_message=str(e),
            )
    
    def save_model(self, output_dir: str = None) -> str:
        """Save trained model to disk."""
        if self.model is None:
            raise ValueError("No trained model to save")
        
        output_dir = output_dir or self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save model
        model_path = os.path.join(output_dir, f"rf_model_{timestamp}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "class_names": self.class_names,
            }, f)
        
        # Save "latest" version
        latest_path = os.path.join(output_dir, "rf_model_latest.pkl")
        with open(latest_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "class_names": self.class_names,
            }, f)
        
        # Save metadata as JSON
        metadata = {
            "timestamp": timestamp,
            "n_estimators": self.config.n_estimators,
            "max_depth": self.config.max_depth,
            "n_features": len(self.feature_names),
            "n_classes": len(self.class_names),
            "class_names": self.class_names,
            "feature_names": self.feature_names,
        }
        
        with open(os.path.join(output_dir, f"rf_metadata_{timestamp}.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        with open(os.path.join(output_dir, "rf_metadata_latest.json"), "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Model saved to {model_path}")
        return model_path
    
    @staticmethod
    def load_model(model_path: str) -> Tuple[RandomForestClassifier, StandardScaler, List[str], List[str]]:
        """Load trained model from disk."""
        with open(model_path, "rb") as f:
            data = pickle.load(f)
        
        return (
            data["model"],
            data["scaler"],
            data["feature_names"],
            data["class_names"],
        )


class RFPredictor:
    """
    Makes predictions using trained RF model.
    
    This is the runtime inference engine.
    """
    
    def __init__(self, model_path: str):
        """Load model from disk."""
        self.model, self.scaler, self.feature_names, self.class_names = \
            RFTrainer.load_model(model_path)
    
    def predict(
        self,
        features: Dict[str, float],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        Predict failure modes from features.
        
        Args:
            features: Dict of feature_name -> value
            top_k: Return top K predictions
            
        Returns:
            List of (failure_mode, probability) tuples
        """
        # Build feature vector
        X = np.zeros((1, len(self.feature_names)))
        for i, fname in enumerate(self.feature_names):
            X[0, i] = features.get(fname, 0.0)
        
        # Scale
        X_scaled = self.scaler.transform(X)
        
        # Get probabilities
        probs = self.model.predict_proba(X_scaled)[0]
        
        # Sort by probability
        sorted_indices = np.argsort(probs)[::-1]
        
        results = []
        for idx in sorted_indices[:top_k]:
            results.append((self.class_names[idx], float(probs[idx])))
        
        return results
    
    def predict_from_pids(
        self,
        pid_series: Dict[str, List[Tuple[float, float]]],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        Predict from raw PID time series.
        
        Args:
            pid_series: Dict of pid_name -> [(time, value), ...]
            top_k: Return top K predictions
            
        Returns:
            List of (failure_mode, probability) tuples
        """
        # Extract features (same as physics simulator)
        features = {}
        
        for pid_name, series in pid_series.items():
            if len(series) < 2:
                continue
            
            values = np.array([v for t, v in series])
            times = np.array([t for t, v in series])
            
            # Basic statistics
            features[f"{pid_name}_mean"] = float(np.mean(values))
            features[f"{pid_name}_std"] = float(np.std(values))
            features[f"{pid_name}_min"] = float(np.min(values))
            features[f"{pid_name}_max"] = float(np.max(values))
            features[f"{pid_name}_range"] = float(np.max(values) - np.min(values))
            
            # Rate of change
            if len(values) > 1:
                dv = np.diff(values)
                dt = np.diff(times)
                rates = dv / np.maximum(dt, 0.001)
                features[f"{pid_name}_rate_mean"] = float(np.mean(rates))
                features[f"{pid_name}_rate_max"] = float(np.max(np.abs(rates)))
            
            # Final value
            features[f"{pid_name}_final"] = float(np.mean(values[-10:]))
            
            # Warmup time for coolant
            if pid_name == "coolant_temp":
                above_threshold = values >= 180
                if np.any(above_threshold):
                    idx = np.argmax(above_threshold)
                    features["coolant_warmup_time"] = float(times[idx])
                else:
                    features["coolant_warmup_time"] = float(times[-1])
        
        return self.predict(features, top_k)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train RF classifier on synthetic data")
    parser.add_argument("--samples", type=int, default=100, help="Samples per class")
    parser.add_argument("--output", type=str, default="models", help="Output directory")
    parser.add_argument("--n_estimators", type=int, default=100, help="Number of trees")
    parser.add_argument("--max_depth", type=int, default=15, help="Max tree depth")
    args = parser.parse_args()
    
    config = TrainingConfig(
        samples_per_class=args.samples,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        output_dir=args.output,
    )
    
    print(f"\n=== Training RF Classifier ===")
    print(f"Samples per class: {args.samples}")
    print(f"Estimators: {args.n_estimators}")
    print(f"Max depth: {args.max_depth}")
    print()
    
    trainer = RFTrainer(config)
    result = trainer.train()
    
    if result.success:
        model_path = trainer.save_model()
        print(f"\nModel saved to: {model_path}")
    else:
        print(f"\nTraining failed: {result.error_message}")
