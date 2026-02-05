"""
Runtime Inference Engine

This module takes real-time PID data from a vehicle and predicts
the most likely failure modes using trained ML models.

Architecture:
    Real PIDs → Feature Extraction → Hierarchical Models → Top 3-4 Causes

Supports two model types:
    1. RF Classifier (legacy): Single model predicting all failure modes
    2. Hierarchical (new): Per-system neural networks for better accuracy

Usage:
    from inference_engine import InferenceEngine
    
    engine = InferenceEngine()  # Auto-loads best available model
    
    # From feature dict
    results = engine.diagnose({"coolant_temp_final": 145, "stft_b1_mean": 15.2, ...})
    
    # From raw PID stream
    results = engine.diagnose_from_pids({
        "coolant_temp": [(0, 70), (10, 120), (30, 145), ...],
        "stft_b1": [(0, 0.5), (10, 12.3), ...],
    })
    
    for cause, probability, explanation in results:
        print(f"{cause}: {probability:.1%} - {explanation}")
"""

import os
import pickle
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import numpy as np

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from .rf_trainer import RFTrainer, RFPredictor
except ImportError:
    try:
        from rf_trainer import RFTrainer, RFPredictor
    except ImportError:
        RFPredictor = None

logger = logging.getLogger(__name__)


# =============================================================================
# CHRONO RF PREDICTOR (for models trained by train_from_chrono.py)
# =============================================================================

class ChronoRFPredictor:
    """
    Predictor for RF models trained on Chrono synthetic data.
    
    The chrono training saves just the model + separate encoder file,
    not the dict format that RFTrainer expects.
    """
    
    # Sensors used in chrono training
    SENSOR_COLS = [
        'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
        'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2',
        'fuel_pressure', 'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
        'brake_temp', 'decel_rate', 'brake_pedal_travel',
        'trans_slip_ratio', 'trans_temp', 'shift_quality',
    ]
    
    def __init__(self, model_path: str):
        """Load model and encoder from disk."""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Load encoder from same directory
        model_dir = os.path.dirname(model_path)
        encoder_path = os.path.join(model_dir, "rf_chrono_label_encoder.pkl")
        if os.path.exists(encoder_path):
            with open(encoder_path, 'rb') as f:
                self.label_encoder = pickle.load(f)
            self.class_names = list(self.label_encoder.classes_)
        else:
            # Fall back to model's classes_ if no encoder
            self.class_names = [str(c) for c in self.model.classes_]
            self.label_encoder = None
        
        # Build feature names from sensors (same order as training)
        self.feature_names = []
        for col in self.SENSOR_COLS:
            self.feature_names.extend([
                f'{col}_mean', f'{col}_std', f'{col}_min', f'{col}_max',
                f'{col}_range', f'{col}_final', f'{col}_delta', f'{col}_rate_max'
            ])
        # Add severity and scenario
        self.feature_names.extend(['severity', 'scenario'])
        
        logger.info(f"Loaded ChronoRF with {len(self.class_names)} classes")
    
    def predict(
        self,
        features: Dict[str, float],
        top_k: int = 3,
    ) -> List[Tuple[str, float]]:
        """
        Predict failure modes from features.
        
        Returns list of (failure_mode, probability) tuples.
        """
        import pandas as pd
        
        # Build feature vector - must match training feature order
        feature_row = {}
        for fname in self.feature_names:
            if fname == 'scenario':
                # Skip scenario - it's categorical and causes issues
                feature_row[fname] = 0
            else:
                feature_row[fname] = features.get(fname, 0.0)
        
        X = pd.DataFrame([feature_row])
        
        # Ensure columns are in right order
        X = X.reindex(columns=self.feature_names, fill_value=0.0)
        
        # Handle scenario column (it's categorical)
        if 'scenario' in X.columns:
            X['scenario'] = 0  # Drop it effectively
        
        # Get probabilities
        try:
            probs = self.model.predict_proba(X)[0]
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return [(self.class_names[0], 0.5)] if self.class_names else []
        
        # Sort by probability
        sorted_indices = np.argsort(probs)[::-1]
        
        results = []
        for idx in sorted_indices[:top_k]:
            results.append((self.class_names[idx], float(probs[idx])))
        
        return results


# =============================================================================
# TWO-STAGE XGBOOST PREDICTOR (77% accuracy - BEST)
# =============================================================================

class TwoStageXGBPredictor:
    """
    Two-stage XGBoost predictor for vehicle diagnostics.
    
    Stage 1: Predict which SYSTEM has the fault
    Stage 2: Predict which FAILURE MODE within that system
    
    This achieves 77% accuracy vs 55% for single-stage RF.
    """
    
    SENSOR_COLS = [
        'rpm', 'speed_kmh', 'throttle_pct', 'engine_torque_nm', 'engine_load',
        'coolant_temp', 'stft_b1', 'stft_b2', 'ltft_b1', 'ltft_b2',
        'fuel_pressure', 'tire_pressure', 'wheel_slip_events', 'tire_wear_index',
        'brake_temp', 'decel_rate', 'brake_pedal_travel',
        'trans_slip_ratio', 'trans_temp', 'shift_quality',
    ]
    
    def __init__(self, model_path: str):
        """Load two-stage model from disk."""
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
        
        self.system_clf = data['system_clf']
        self.system_le = data['system_le']
        self.system_scaler = data['system_scaler']
        self.failure_models = data['failure_models']
        self.feature_names = data['feature_names']
        self.metrics = data.get('metrics', {})
        
        logger.info(f"Loaded TwoStageXGB: {len(self.system_le.classes_)} systems, "
                   f"{self.metrics.get('pipeline_accuracy', 0):.1%} accuracy")
    
    def _build_features(self, features: Dict[str, float]) -> "pd.DataFrame":
        """Build feature DataFrame matching training format."""
        import pandas as pd
        
        feature_row = {}
        for fname in self.feature_names:
            if fname == 'scenario':
                feature_row[fname] = 0
            else:
                feature_row[fname] = features.get(fname, 0.0)
        
        X = pd.DataFrame([feature_row])
        X = X.reindex(columns=self.feature_names, fill_value=0.0)
        return X
    
    def predict(
        self,
        features: Dict[str, float],
        top_k: int = 4,
    ) -> List[Tuple[str, float, str]]:
        """
        Predict failure modes using two-stage approach.
        
        Returns list of (failure_mode, probability, system) tuples.
        """
        X = self._build_features(features)
        
        # Stage 1: Predict system with probabilities
        X_scaled = self.system_scaler.transform(X)
        system_probs = self.system_clf.predict_proba(X_scaled)[0]
        
        # Get top systems to consider
        top_system_indices = np.argsort(system_probs)[::-1][:3]
        
        all_predictions = []
        
        for sys_idx in top_system_indices:
            system = str(self.system_le.classes_[sys_idx])
            sys_prob = system_probs[sys_idx]
            
            if sys_prob < 0.05:  # Skip very unlikely systems
                continue
            
            if system in self.failure_models:
                # Stage 2: Predict failure mode within this system
                clf, le, scaler, _ = self.failure_models[system]
                X_sys_scaled = scaler.transform(X)
                fail_probs = clf.predict_proba(X_sys_scaled)[0]
                
                for i, fail_prob in enumerate(fail_probs):
                    failure_mode = str(le.classes_[i])
                    # Combined probability = P(system) * P(failure|system)
                    combined_prob = sys_prob * fail_prob
                    all_predictions.append((failure_mode, combined_prob, system))
            else:
                # Single-failure system (brakes, ev, starting)
                # Infer failure mode from system
                single_failure_map = {
                    'brakes': 'brakes.brake_fade',
                    'ev': 'tesla.hv_isolation_fault',
                    'starting': 'starter.motor_failing',
                }
                failure_mode = single_failure_map.get(system, f"{system}.unknown")
                all_predictions.append((failure_mode, sys_prob, system))
        
        # Sort by combined probability
        all_predictions.sort(key=lambda x: x[1], reverse=True)
        return all_predictions[:top_k]


# =============================================================================
# FAILURE MODE EXPLANATIONS
# =============================================================================

FAILURE_EXPLANATIONS = {
    # Cooling system
    "thermostat_stuck_open": "Thermostat stuck OPEN - coolant flows continuously, preventing engine from reaching operating temperature. Causes: poor fuel economy, slow warmup, weak heater output.",
    "thermostat_stuck_closed": "Thermostat stuck CLOSED - coolant cannot circulate to radiator, causing rapid overheating. STOP DRIVING immediately to prevent engine damage.",
    "water_pump_failure": "Water pump failing or failed - coolant not circulating properly, causing overheating. May hear squealing or see coolant leak.",
    "cooling_fan_failure": "Electric cooling fan not working - can cause overheating at idle or low speeds. AC may still work. Check fan relay and motor.",
    "coolant_leak": "Coolant leak detected - system losing coolant, reducing heat transfer capacity. Check hoses, radiator, water pump, and heater core.",
    
    # Fuel system
    "fuel_pump_weak": "Fuel pump weak/failing - insufficient fuel pressure causing lean condition, hard starting, and loss of power under load.",
    "fuel_pressure_regulator_failure": "Fuel pressure regulator stuck - causing high fuel pressure and rich running condition. May cause black smoke and poor mileage.",
    "vacuum_leak": "Vacuum leak detected - unmetered air entering engine causing lean condition. Check intake manifold gaskets, vacuum hoses, PCV system.",
    "injector_clogged": "Fuel injector(s) clogged - not delivering enough fuel, causing lean condition. May cause misfire on specific cylinder(s).",
    "injector_leaking": "Fuel injector(s) leaking - delivering too much fuel, causing rich condition. May cause hard starting and black smoke.",
    "maf_sensor_dirty": "MAF sensor dirty/contaminated - underreporting airflow, causing lean fuel trim. Clean or replace MAF sensor.",
    
    # O2 sensors
    "o2_sensor_stuck_lean": "O2 sensor stuck lean - reporting constant lean even when mixture is correct. ECU may be overcompensating with fuel.",
    "o2_sensor_stuck_rich": "O2 sensor stuck rich - reporting constant rich even when mixture is correct. ECU may cut fuel excessively.",
    "o2_sensor_lazy": "O2 sensor slow/lazy - not switching fast enough, causing poor fuel control and emissions. Common on high-mileage vehicles.",
    
    # Electrical
    "alternator_failure": "Alternator failing - not maintaining charging voltage. Battery draining while driving. Will eventually stall.",
    "voltage_regulator_failure": "Voltage regulator failed - causing overcharging (>15V). Can damage battery and electronics.",
    "battery_weak": "Battery weak/failing - starting issues but alternator working. May need battery replacement.",
    
    # Intake/air
    "maf_sensor_failure": "MAF sensor failed completely - ECU using backup fuel maps, poor performance. Check connector first.",
    "air_filter_clogged": "Air filter severely restricted - reducing airflow and power. Simple fix: replace air filter.",
    "pcv_valve_stuck_open": "PCV valve stuck open - causing excessive crankcase ventilation, may affect idle and fuel trim.",
    "iat_sensor_failure": "Intake Air Temperature sensor failed - ECU not compensating for air density correctly.",
    
    # Ignition
    "knock_sensor_failure": "Knock sensor failed - ECU cannot detect detonation, may pull timing excessively or allow engine damage.",
    
    # Normal
    "normal": "No failure detected - system operating within normal parameters.",
}


def get_system_from_failure_mode(failure_mode: str) -> str:
    """Extract system from failure mode name."""
    # Handle dotted format like "cooling.thermostat_stuck_closed"
    if '.' in failure_mode:
        prefix = failure_mode.split('.')[0]
        # Map some prefixes to canonical system names
        prefix_map = {
            'ect': 'cooling',
            'tcc': 'transmission',
            'trans': 'transmission',
            'tesla': 'ev',
            'radiator': 'cooling',
            'water': 'cooling',
            'oil': 'engine',
            'alternator': 'charging',
            'battery': 'charging',
            'starter': 'starting',
        }
        return prefix_map.get(prefix, prefix)
    
    # Legacy underscore format
    legacy_map = {
        "thermostat_stuck_open": "cooling",
        "thermostat_stuck_closed": "cooling",
        "water_pump_failure": "cooling",
        "cooling_fan_failure": "cooling",
        "coolant_leak": "cooling",
        "fuel_pump_weak": "fuel",
        "fuel_pressure_regulator_failure": "fuel",
        "vacuum_leak": "fuel",
        "injector_clogged": "fuel",
        "injector_leaking": "fuel",
        "maf_sensor_dirty": "fuel",
        "o2_sensor_stuck_lean": "fuel",
        "o2_sensor_stuck_rich": "fuel",
        "o2_sensor_lazy": "fuel",
        "alternator_failure": "charging",
        "voltage_regulator_failure": "charging",
        "battery_weak": "charging",
        "maf_sensor_failure": "intake",
        "air_filter_clogged": "intake",
        "pcv_valve_stuck_open": "intake",
        "iat_sensor_failure": "intake",
        "knock_sensor_failure": "ignition",
        "normal": "normal",
    }
    return legacy_map.get(failure_mode, "unknown")


@dataclass
class DiagnosticResult:
    """Result from diagnostic inference."""
    failure_mode: str
    probability: float
    system: str
    explanation: str
    confidence: str  # "high", "medium", "low"
    
    @property
    def is_urgent(self) -> bool:
        """Check if this is an urgent issue."""
        urgent_modes = {
            "thermostat_stuck_closed",
            "water_pump_failure",
            "alternator_failure",
            "cooling.water_pump_failure",
            "cooling.thermostat_stuck_closed",
            "alternator.failing",
        }
        return self.failure_mode in urgent_modes


# =============================================================================
# HIERARCHICAL MODEL PREDICTOR
# =============================================================================

def _build_model(input_dim: int, n_classes: int) -> "torch.nn.Sequential":
    """Build model architecture matching training script."""
    import torch.nn as nn
    return nn.Sequential(
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
    )


class HierarchicalPredictor:
    """
    Predictor using per-system hierarchical neural networks.
    
    Each automotive system (cooling, fuel, ignition, etc.) has its own
    trained neural network that specializes in that system's failure modes.
    """
    
    def __init__(self, model_path: str = None):
        """Load hierarchical models from file."""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for hierarchical models")
        
        if model_path is None:
            search_paths = [
                "models/hierarchical_chrono.pt",
                os.path.join(os.path.dirname(__file__), "models", "hierarchical_chrono.pt"),
            ]
            for path in search_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            else:
                raise FileNotFoundError("No hierarchical model found")
        
        # Load checkpoint
        data = torch.load(model_path, weights_only=False, map_location='cpu')
        self.metadata = data['metadata']
        self.sensors = data.get('sensors', {})
        self.systems = list(data['models'].keys())
        
        # Reconstruct models from state dicts
        self.models = {}
        for system, state_dict in data['models'].items():
            meta = self.metadata[system]
            input_dim = len(meta.get('features', []))
            n_classes = len(meta.get('labels', []))
            
            if input_dim == 0 or n_classes == 0:
                logger.warning(f"Skipping {system}: no features or labels")
                continue
            
            model = _build_model(input_dim, n_classes)
            model.load_state_dict(state_dict)
            model.eval()
            self.models[system] = model
        
        logger.info(f"Loaded hierarchical models for systems: {list(self.models.keys())}")
    
    def _extract_features(self, features: Dict[str, float], system: str) -> Optional[torch.Tensor]:
        """Extract and order features for a specific system's model."""
        if system not in self.metadata:
            return None
        
        expected_features = self.metadata[system].get('features', [])
        if not expected_features:
            return None
        
        # Build feature vector
        values = []
        for feat_name in expected_features:
            val = features.get(feat_name, 0.0)
            if val is None:
                val = 0.0
            values.append(float(val))
        
        return torch.tensor([values], dtype=torch.float32)
    
    def predict(self, features: Dict[str, float], top_k: int = 4) -> List[Tuple[str, float, str]]:
        """
        Predict failure modes from feature dictionary.
        
        Returns list of (failure_mode, probability, system) tuples.
        
        Note: Single-class systems are excluded since they always predict 100%.
        Multi-class systems provide meaningful probability distributions.
        """
        all_predictions = []
        
        for system in self.systems:
            model = self.models[system]
            meta = self.metadata[system]
            labels = meta.get('labels', [])
            
            # Skip single-class systems (always predict 100%)
            if len(labels) <= 1:
                continue
            
            # Get feature tensor
            x = self._extract_features(features, system)
            if x is None:
                continue
            
            # Run inference
            with torch.no_grad():
                logits = model(x)
                probs = torch.softmax(logits, dim=1)[0]
            
            # Collect predictions
            for i, label in enumerate(labels):
                prob = probs[i].item()
                # Convert numpy string to regular string
                label_str = str(label)
                all_predictions.append((label_str, prob, system))
        
        # Sort by probability and return top_k
        all_predictions.sort(key=lambda x: x[1], reverse=True)
        return all_predictions[:top_k]


class InferenceEngine:
    """
    Runtime inference engine for predictive diagnostics.
    
    Takes PID data and returns probable failure modes with explanations.
    
    Supports multiple model types:
    - TwoStageXGB (best): Two-stage XGBoost, 77% accuracy
    - ChronoRF: Single-stage Random Forest, 55% accuracy
    - Hierarchical (PyTorch): Per-system neural networks
    """
    
    def __init__(self, model_path: str = None, model_type: str = "auto"):
        """
        Initialize the inference engine.
        
        Args:
            model_path: Path to trained model file. If None, uses default location.
            model_type: "twostage", "rf", "hierarchical", or "auto" (prefers twostage)
        """
        self.predictor = None
        self.model_type = None
        
        # Auto-detect: prefer two-stage XGBoost (77% accuracy)
        if model_type == "auto":
            # Try two-stage first (best accuracy)
            try:
                self._load_twostage(model_path)
                return
            except FileNotFoundError:
                logger.debug("Two-stage model not found, trying RF")
            except Exception as e:
                logger.warning(f"Failed to load two-stage model: {e}")
            
            # Try RF next
            try:
                self._load_rf(model_path)
                return
            except FileNotFoundError:
                logger.debug("RF model not found, trying hierarchical")
            except Exception as e:
                logger.warning(f"Failed to load RF model: {e}")
            
            # Fall back to hierarchical
            if TORCH_AVAILABLE:
                self._load_hierarchical(model_path)
            else:
                raise FileNotFoundError("No model found")
        
        elif model_type == "twostage":
            self._load_twostage(model_path)
        
        elif model_type == "hierarchical":
            if not TORCH_AVAILABLE:
                raise ImportError("PyTorch required for hierarchical models")
            self._load_hierarchical(model_path)
        
        elif model_type == "rf":
            self._load_rf(model_path)
        
        else:
            raise ValueError(f"Unknown model_type: {model_type}")
    
    def _load_twostage(self, model_path: str = None):
        """Load Two-Stage XGBoost model (77% accuracy - BEST)."""
        if model_path is None:
            search_paths = [
                "models/twostage_xgb.pkl",
                os.path.join(os.path.dirname(__file__), "models", "twostage_xgb.pkl"),
            ]
            for path in search_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            else:
                raise FileNotFoundError("No two-stage model found")
        
        self.predictor = TwoStageXGBPredictor(model_path)
        self.model_type = "twostage"
        logger.info(f"Loaded two-stage XGBoost from {model_path}")
    
    def _load_hierarchical(self, model_path: str = None):
        """Load hierarchical PyTorch model."""
        if model_path is None:
            search_paths = [
                "models/hierarchical_chrono.pt",
                "/home/drawson/autotech_ai/addons/predictive_diagnostics/models/hierarchical_chrono.pt",
                os.path.join(os.path.dirname(__file__), "models", "hierarchical_chrono.pt"),
            ]
            for path in search_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            else:
                raise FileNotFoundError("No hierarchical model found")
        
        self.predictor = HierarchicalPredictor(model_path)
        self.model_type = "hierarchical"
        logger.info(f"Loaded hierarchical model from {model_path}")
    
    def _load_rf(self, model_path: str = None):
        """Load Random Forest model."""
        if model_path is None:
            search_paths = [
                # Prefer chrono-trained RF (55% accuracy)
                ("chrono", "models/rf_chrono_latest.pkl"),
                ("chrono", os.path.join(os.path.dirname(__file__), "models", "rf_chrono_latest.pkl")),
                # Fall back to original RF
                ("legacy", "models/rf_model_latest.pkl"),
                ("legacy", os.path.join(os.path.dirname(__file__), "models", "rf_model_latest.pkl")),
            ]
            for model_type, path in search_paths:
                if os.path.exists(path):
                    model_path = path
                    rf_type = model_type
                    break
            else:
                raise FileNotFoundError(
                    f"No RF model found. Train a model first with rf_trainer.py"
                )
        else:
            # Determine type from path
            rf_type = "chrono" if "chrono" in model_path else "legacy"
        
        # Load with appropriate predictor
        if rf_type == "chrono":
            self.predictor = ChronoRFPredictor(model_path)
        else:
            if RFPredictor is None:
                raise ImportError("RFPredictor not available")
            self.predictor = RFPredictor(model_path)
        
        self.model_type = "rf"
        logger.info(f"Loaded RF model ({rf_type}) from {model_path}")
    
    def diagnose(
        self,
        features: Dict[str, float],
        top_k: int = 4,
    ) -> List[DiagnosticResult]:
        """
        Diagnose from feature dictionary.
        
        Args:
            features: Dict of feature_name -> value (e.g., from physics simulator)
            top_k: Return top K predictions
            
        Returns:
            List of DiagnosticResult objects
        """
        predictions = self.predictor.predict(features, top_k)
        
        results = []
        for pred in predictions:
            # Hierarchical returns (failure_mode, prob, system)
            # RF returns (failure_mode, prob)
            if len(pred) == 3:
                failure_mode, probability, system = pred
            else:
                failure_mode, probability = pred
                system = get_system_from_failure_mode(failure_mode)
            
            # Convert numpy strings to regular strings
            failure_mode = str(failure_mode)
            
            result = DiagnosticResult(
                failure_mode=failure_mode,
                probability=probability,
                system=system,
                explanation=FAILURE_EXPLANATIONS.get(
                    failure_mode, 
                    f"Detected {failure_mode.replace('.', ' ').replace('_', ' ')} in {system} system"
                ),
                confidence=self._confidence_level(probability),
            )
            results.append(result)
        
        return results
    
    def diagnose_from_pids(
        self,
        pid_series: Dict[str, List[Tuple[float, float]]],
        top_k: int = 4,
    ) -> List[DiagnosticResult]:
        """
        Diagnose from raw PID time series.
        
        Args:
            pid_series: Dict of pid_name -> [(time, value), ...]
                PID names should match physics simulator output:
                - coolant_temp, oil_temp, iat
                - rpm, speed, throttle
                - stft_b1, ltft_b1, o2_b1s1
                - voltage, fuel_pressure
                - map, maf, timing_advance, load
            top_k: Return top K predictions
            
        Returns:
            List of DiagnosticResult objects
        """
        predictions = self.predictor.predict_from_pids(pid_series, top_k)
        
        results = []
        for failure_mode, probability in predictions:
            failure_mode = str(failure_mode)
            system = get_system_from_failure_mode(failure_mode)
            result = DiagnosticResult(
                failure_mode=failure_mode,
                probability=probability,
                system=system,
                explanation=FAILURE_EXPLANATIONS.get(
                    failure_mode,
                    f"Detected {failure_mode.replace('.', ' ').replace('_', ' ')} in {system} system"
                ),
                confidence=self._confidence_level(probability),
            )
            results.append(result)
        
        return results
    
    def _confidence_level(self, probability: float) -> str:
        """Convert probability to confidence level."""
        if probability >= 0.7:
            return "high"
        elif probability >= 0.4:
            return "medium"
        else:
            return "low"
    
    def format_report(
        self,
        results: List[DiagnosticResult],
        include_explanations: bool = True,
    ) -> str:
        """Format results as a human-readable report."""
        lines = ["=== Diagnostic Analysis Results ===", ""]
        
        if not results:
            return "No diagnostic results available."
        
        for i, result in enumerate(results, 1):
            urgent = " ⚠️ URGENT" if result.is_urgent else ""
            conf = {"high": "✓", "medium": "?", "low": "~"}[result.confidence]
            
            lines.append(f"{i}. [{conf}] {result.failure_mode}: {result.probability:.1%}{urgent}")
            lines.append(f"   System: {result.system}")
            
            if include_explanations:
                # Wrap explanation to ~70 chars
                words = result.explanation.split()
                line = "   "
                for word in words:
                    if len(line) + len(word) > 75:
                        lines.append(line)
                        line = "   " + word
                    else:
                        line += " " + word if line.strip() else word
                if line.strip():
                    lines.append(line)
            
            lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# INTEGRATION WITH OPENWEBUI TOOL
# =============================================================================

def diagnose_vehicle(
    pid_data: Dict[str, Any],
    model_path: str = None,
) -> Dict[str, Any]:
    """
    Main entry point for Open WebUI tool integration.
    
    Args:
        pid_data: Either:
            - Dict of features (feature_name -> value)
            - Dict of time series (pid_name -> [(time, value), ...])
        model_path: Optional path to model file
        
    Returns:
        Dict with:
            - success: bool
            - diagnoses: List of {failure_mode, probability, system, explanation, confidence}
            - report: Human-readable summary
    """
    try:
        engine = InferenceEngine(model_path)
        
        # Detect input type
        sample_value = next(iter(pid_data.values()))
        
        if isinstance(sample_value, list) and len(sample_value) > 0:
            # Time series format
            results = engine.diagnose_from_pids(pid_data)
        else:
            # Feature dict format
            results = engine.diagnose(pid_data)
        
        diagnoses = []
        for r in results:
            diagnoses.append({
                "failure_mode": r.failure_mode,
                "probability": r.probability,
                "system": r.system,
                "explanation": r.explanation,
                "confidence": r.confidence,
                "is_urgent": r.is_urgent,
            })
        
        return {
            "success": True,
            "diagnoses": diagnoses,
            "report": engine.format_report(results),
        }
        
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "diagnoses": [],
            "report": f"Diagnosis failed: {e}",
        }


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run diagnostic inference")
    parser.add_argument("--model", type=str, default="models/rf_model_latest.pkl", help="Model path")
    parser.add_argument("--simulate", type=str, help="Simulate a failure mode for testing")
    args = parser.parse_args()
    
    print("\n=== Predictive Diagnostics Inference Engine ===\n")
    
    if args.simulate:
        # Generate test data from physics simulator
        try:
            from physics_simulator import PhysicsSimulator, SimulationConfig
        except ImportError:
            from .physics_simulator import PhysicsSimulator, SimulationConfig
        
        print(f"Simulating failure mode: {args.simulate}")
        sim = PhysicsSimulator()
        config = SimulationConfig(duration_sec=300)
        
        pid_series = sim.simulate_failure(args.simulate, config)
        features = sim.extract_features(pid_series)
        
        print(f"Generated {len(features)} features from simulation")
        print()
        
        # Run inference
        engine = InferenceEngine(args.model)
        results = engine.diagnose(features, top_k=5)
        
        print(engine.format_report(results))
        
        # Show if correct
        top_prediction = results[0].failure_mode if results else None
        correct = "✓ CORRECT" if top_prediction == args.simulate else "✗ INCORRECT"
        print(f"\nActual: {args.simulate}")
        print(f"Predicted: {top_prediction}")
        print(f"Result: {correct}")
        
    else:
        # Demo with some hard-coded features
        print("No --simulate provided. Using demo features (thermostat_stuck_open pattern):")
        
        demo_features = {
            "coolant_temp_final": 145.0,
            "coolant_temp_mean": 125.0,
            "coolant_temp_max": 155.0,
            "coolant_warmup_time": 350.0,
            "stft_b1_mean": 0.5,
            "ltft_b1_mean": 2.0,
            "voltage_mean": 14.1,
            "o2_b1s1_mean": 0.45,
        }
        
        print(f"  coolant_temp_final: {demo_features['coolant_temp_final']}°F")
        print(f"  coolant_warmup_time: {demo_features['coolant_warmup_time']}s")
        print()
        
        engine = InferenceEngine(args.model)
        results = engine.diagnose(demo_features, top_k=5)
        
        print(engine.format_report(results))
