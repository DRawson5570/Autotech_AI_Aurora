"""
Runtime inference for diagnostic models.

Provides:
- Easy-to-use inference API
- Uncertainty quantification
- Integration with knowledge graph for explanation
- Discriminating test recommendations
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

try:
    import torch
    import torch.nn.functional as F
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .model import SimpleDiagnosticModel, DiagnosticModel, ModelConfig


@dataclass
class DiagnosticResult:
    """
    Result of diagnostic inference.
    
    Contains ranked failure hypotheses with probabilities
    and recommended discriminating tests.
    """
    # Top failure hypotheses
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    
    # Confidence in top diagnosis
    confidence: float = 0.0
    
    # Is there a clear winner or ambiguity?
    is_ambiguous: bool = False
    
    # Discriminating tests to narrow down
    recommended_tests: List[str] = field(default_factory=list)
    
    # Raw probabilities for all classes
    all_probabilities: Dict[str, float] = field(default_factory=dict)
    
    def __str__(self) -> str:
        lines = ["Diagnostic Results:"]
        lines.append("-" * 40)
        
        for i, hyp in enumerate(self.hypotheses[:5], 1):
            lines.append(f"{i}. {hyp['failure_id']}: {hyp['probability']:.1%}")
            if hyp.get('description'):
                lines.append(f"   {hyp['description']}")
        
        lines.append("")
        lines.append(f"Confidence: {self.confidence:.1%}")
        if self.is_ambiguous:
            lines.append("⚠️ Ambiguous - multiple failures possible")
        
        if self.recommended_tests:
            lines.append("")
            lines.append("Recommended tests:")
            for test in self.recommended_tests[:3]:
                lines.append(f"  • {test}")
        
        return "\n".join(lines)


class DiagnosticInference:
    """
    High-level inference interface.
    
    Usage:
        inference = DiagnosticInference.load("model.pt")
        result = inference.diagnose(sensor_data)
        print(result)
    """
    
    def __init__(self, model: SimpleDiagnosticModel,
                 knowledge_graph: Optional[Any] = None):
        """
        Args:
            model: Trained diagnostic model
            knowledge_graph: Optional CausalGraph for explanations
        """
        self.model = model
        self.model.eval()
        self.knowledge_graph = knowledge_graph
        
        # Get class labels
        self.class_labels = model.class_labels
        if not self.class_labels:
            raise ValueError("Model has no class labels - was it trained?")
    
    @classmethod
    def load(cls, model_path: str, 
             knowledge_graph: Optional[Any] = None) -> 'DiagnosticInference':
        """Load inference engine from saved model."""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required for inference")
        
        model = SimpleDiagnosticModel.load(model_path)
        return cls(model, knowledge_graph)
    
    def diagnose(self, sensor_data: Dict[str, List[float]],
                 top_k: int = 5,
                 ambiguity_threshold: float = 0.3) -> DiagnosticResult:
        """
        Diagnose failure from sensor time series.
        
        Args:
            sensor_data: Dict mapping sensor name to time series values
            top_k: Number of top hypotheses to return
            ambiguity_threshold: If gap between top 2 is less than this, flag ambiguous
            
        Returns:
            DiagnosticResult with ranked hypotheses
        """
        # Extract features
        features = self._extract_features(sensor_data)
        
        # Move features to same device as model
        device = next(self.model.parameters()).device
        features = features.to(device)
        
        # Get probabilities
        with torch.no_grad():
            probs = self.model.predict_proba(features.unsqueeze(0))
            probs = probs.squeeze(0).cpu().numpy()
        
        # Build probability dict
        all_probs = {
            label: float(probs[i])
            for i, label in enumerate(self.class_labels)
        }
        
        # Sort by probability
        sorted_probs = sorted(all_probs.items(), key=lambda x: -x[1])
        
        # Build hypotheses
        hypotheses = []
        for label, prob in sorted_probs[:top_k]:
            hyp = {
                "failure_id": label,
                "probability": prob,
                "description": self._get_failure_description(label),
            }
            hypotheses.append(hyp)
        
        # Compute confidence and ambiguity
        top_prob = sorted_probs[0][1]
        second_prob = sorted_probs[1][1] if len(sorted_probs) > 1 else 0
        
        confidence = top_prob
        is_ambiguous = (top_prob - second_prob) < ambiguity_threshold
        
        # Get discriminating tests
        if is_ambiguous:
            top_failures = [h["failure_id"] for h in hypotheses[:3]]
            recommended_tests = self._get_discriminating_tests(top_failures)
        else:
            recommended_tests = []
        
        return DiagnosticResult(
            hypotheses=hypotheses,
            confidence=confidence,
            is_ambiguous=is_ambiguous,
            recommended_tests=recommended_tests,
            all_probabilities=all_probs,
        )
    
    def diagnose_from_observations(self, observations: Dict[str, Any],
                                    top_k: int = 5) -> DiagnosticResult:
        """
        Diagnose from structured observations.
        
        Args:
            observations: Dict with keys like:
                - coolant_temp: current reading
                - dtcs: list of active DTCs
                - symptoms: list of reported symptoms
                
        Returns:
            DiagnosticResult
        """
        # Convert point observations to mock time series
        # (for real deployment, we'd want actual time series)
        sensor_data = {}
        
        if "coolant_temp" in observations:
            temp = observations["coolant_temp"]
            # Create a flat time series at the observed value
            sensor_data["coolant_temp"] = [temp] * 60
        
        # Add defaults for missing sensors
        defaults = {
            "engine_temp": 90.0,
            "thermostat_position": 1.0,
            "fan_state": 0.0,
            "coolant_flow": 30.0,
            "stft": 0.0,
            "ltft": 0.0,
        }
        
        for key, default in defaults.items():
            if key not in sensor_data:
                val = observations.get(key, default)
                sensor_data[key] = [val] * 60
        
        return self.diagnose(sensor_data, top_k=top_k)
    
    def _extract_features(self, time_series: Dict[str, List[float]]) -> 'torch.Tensor':
        """Extract statistical features from time series."""
        feature_names = [
            "coolant_temp", "engine_temp", "thermostat_position",
            "fan_state", "coolant_flow", "stft", "ltft"
        ]
        
        features = []
        for name in feature_names:
            values = time_series.get(name, [0.0])
            if not values:
                values = [0.0]
            arr = np.array(values)
            
            features.extend([
                np.mean(arr),
                np.std(arr) if len(arr) > 1 else 0.0,
                np.min(arr),
                np.max(arr),
                (arr[-1] - arr[0]) / max(len(arr), 1),
                arr[-1],
                np.max(arr) - np.min(arr),
                arr[-1] - arr[0],
            ])
        
        return torch.tensor(features, dtype=torch.float32)
    
    def _get_failure_description(self, failure_id: str) -> str:
        """Get human-readable description of failure."""
        descriptions = {
            "normal": "No failure detected - system operating normally",
            "thermostat_stuck_closed": "Thermostat stuck closed - engine overheating",
            "thermostat_stuck_open": "Thermostat stuck open - engine running cold",
            "water_pump_failure": "Water pump failure - no coolant circulation",
            "water_pump_belt_slipping": "Water pump belt slipping - reduced coolant flow",
            "radiator_blocked_external": "Radiator externally blocked - reduced airflow",
            "radiator_blocked_internal": "Radiator internally blocked - restricted flow",
            "radiator_blocked": "Radiator blocked - heat rejection impaired",
            "cooling_fan_not_operating": "Cooling fan not working - overheat at idle",
            "cooling_fan_always_on": "Cooling fan always on - possible sensor issue",
            "pressure_cap_faulty": "Pressure cap faulty - coolant boiling/loss",
            "ect_sensor_failed_high": "ECT sensor failed high - false hot reading",
            "ect_sensor_failed_low": "ECT sensor failed low - false cold reading",
            "coolant_leak": "Coolant leak - gradual system degradation",
        }
        return descriptions.get(failure_id, f"Failure: {failure_id}")
    
    def _get_discriminating_tests(self, failure_ids: List[str]) -> List[str]:
        """Get tests that can distinguish between the given failures."""
        # If we have a knowledge graph, use it
        if self.knowledge_graph is not None:
            try:
                return self.knowledge_graph.get_discriminating_tests(failure_ids)
            except:
                pass
        
        # Fallback: hardcoded discriminating tests
        test_database = {
            ("thermostat_stuck_closed", "radiator_blocked"): 
                "Check thermostat opens in hot water - if yes, radiator issue",
            ("thermostat_stuck_open", "ect_sensor_failed_low"):
                "Use infrared thermometer to verify actual coolant temperature",
            ("water_pump_failure", "thermostat_stuck_closed"):
                "Feel upper radiator hose - hot with no flow suggests pump",
            ("cooling_fan_not_operating", "radiator_blocked"):
                "Fan test: does fan run when AC is on or at hot temp?",
            ("radiator_blocked_external", "radiator_blocked_internal"):
                "Visual inspection of radiator fins vs pressure test",
        }
        
        tests = []
        for i, f1 in enumerate(failure_ids):
            for f2 in failure_ids[i+1:]:
                key = tuple(sorted([f1, f2]))
                if key in test_database:
                    tests.append(test_database[key])
        
        # Generic tests
        if not tests:
            tests = [
                "Compare actual vs reported coolant temperature with infrared",
                "Pressure test cooling system for leaks",
                "Check for DTCs related to cooling system",
            ]
        
        return tests[:5]


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def quick_diagnose(sensor_data: Dict[str, List[float]],
                   model_path: str) -> DiagnosticResult:
    """
    One-liner diagnosis from sensor data.
    
    Args:
        sensor_data: Dict of sensor time series
        model_path: Path to trained model
        
    Returns:
        DiagnosticResult
    """
    inference = DiagnosticInference.load(model_path)
    return inference.diagnose(sensor_data)


# ==============================================================================
# HIERARCHICAL MODEL INFERENCE
# ==============================================================================

# Default paths for hierarchical models
HIERARCHICAL_MODEL_PATH = Path(__file__).parent.parent / "models" / "hierarchical_models.pt"
HIERARCHICAL_FALLBACK_PATH = Path("/tmp/pd_hierarchical/hierarchical_models.pt")


class HierarchicalInference:
    """
    Inference engine for hierarchical diagnostic models.
    
    Uses per-system models trained on system-specific sensor data.
    Provides higher accuracy by leveraging domain-specific features.
    
    Usage:
        inference = HierarchicalInference()
        result = inference.predict("cooling", sensor_data)
    """
    
    # Sensor definitions per system (must match training)
    SYSTEM_SENSORS = {
        "cooling": [
            "coolant_temp", "oil_temp", "fan_state", "thermostat_position",
            "radiator_delta_t", "flow_rate", "system_pressure", "ambient_temp",
        ],
        "fuel": [
            "fuel_pressure", "stft", "ltft", "afr", "injector_pw", "maf_reading",
        ],
        "ignition": [
            "spark_advance", "misfire_count", "knock_sensor", "coil_dwell", 
            "battery_voltage", "rpm_stability", "timing_variance",
        ],
        "charging": [
            "battery_voltage", "alternator_output_v", "charge_current", "battery_soc",
        ],
        "transmission": [
            "trans_temp", "line_pressure", "slip_percent", "shift_time", "current_gear",
        ],
        "brakes": [
            "brake_pressure", "rotor_temp", "pad_thickness", "abs_active", 
            "pedal_travel", "pedal_feel", "stopping_distance",
        ],
        "engine": [
            "oil_pressure", "manifold_vacuum", "compression_variation",
            "blow_by_pressure", "timing_deviation", "power_balance",
        ],
        "steering": [
            "steering_assist", "ps_pressure", "steering_effort", "steering_play",
            "steering_noise", "steering_response",
        ],
        "suspension": [
            "ride_height", "damping_coefficient", "body_roll", "bounce_count",
            "suspension_noise", "wheel_bearing_temp",
        ],
        "hvac": [
            "vent_temp", "refrigerant_pressure_high", "refrigerant_pressure_low",
            "compressor_clutch", "blower_speed", "cabin_temp",
        ],
        "emissions": [
            "catalyst_efficiency", "o2_upstream_mv", "o2_downstream_mv",
            "egr_flow", "evap_pressure", "nox_level",
        ],
    }
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize inference engine.
        
        Args:
            model_path: Path to saved model file. If None, searches default locations.
        """
        self.model_path = self._find_model_path(model_path)
        self.models: Dict[str, 'torch.nn.Module'] = {}
        self.metadata: Dict[str, Dict] = {}
        self._loaded = False
        
    def _find_model_path(self, model_path: Optional[str]) -> Optional[Path]:
        """Find the model file."""
        if model_path:
            p = Path(model_path)
            if p.exists():
                return p
        
        # Try default paths
        if HIERARCHICAL_MODEL_PATH.exists():
            return HIERARCHICAL_MODEL_PATH
        if HIERARCHICAL_FALLBACK_PATH.exists():
            return HIERARCHICAL_FALLBACK_PATH
        
        return None
    
    def _load_models(self) -> bool:
        """Load models from checkpoint."""
        if self._loaded:
            return True
        
        if not TORCH_AVAILABLE:
            return False
        
        if not self.model_path or not self.model_path.exists():
            return False
        
        try:
            checkpoint = torch.load(self.model_path, map_location='cpu', weights_only=False)
            
            self.metadata = checkpoint.get('metadata', {})
            
            # Reconstruct models from state dicts
            for system_id, state_dict in checkpoint.get('models', {}).items():
                meta = self.metadata.get(system_id, {})
                
                # Use feature names from metadata to determine input_dim
                feature_names = meta.get('features', [])
                input_dim = len(feature_names)
                n_classes = len(meta.get('labels', []))
                
                if n_classes == 0:
                    continue
                
                # Recreate model architecture (must match training)
                import torch.nn as nn
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
                )
                
                model.load_state_dict(state_dict)
                model.eval()
                self.models[system_id] = model
            
            self._loaded = True
            return True
            
        except Exception as e:
            print(f"Error loading hierarchical models: {e}")
            return False
    
    @property
    def available_systems(self) -> List[str]:
        """Get list of systems with trained models."""
        self._load_models()
        return list(self.models.keys())
    
    def predict(
        self,
        system_id: str,
        sensor_readings: Dict[str, List[float]],
        top_k: int = 5,
    ) -> DiagnosticResult:
        """
        Predict failure for a specific system.
        
        Args:
            system_id: System to diagnose (cooling, fuel, ignition, etc.)
            sensor_readings: Dict mapping sensor names to time series values
            top_k: Number of top predictions to return
            
        Returns:
            DiagnosticResult with ranked hypotheses
        """
        if not self._load_models():
            return DiagnosticResult(
                hypotheses=[{"failure_id": "error", "probability": 0, 
                            "description": "Model not loaded"}],
                confidence=0.0,
                is_ambiguous=True,
            )
        
        if system_id not in self.models:
            return DiagnosticResult(
                hypotheses=[{"failure_id": "error", "probability": 0,
                            "description": f"No model for system: {system_id}"}],
                confidence=0.0,
                is_ambiguous=True,
            )
        
        model = self.models[system_id]
        meta = self.metadata[system_id]
        feature_names = meta.get('features', [])
        
        # Extract features
        features = self._extract_features(sensor_readings, feature_names)
        
        # Normalize using training stats
        mean = np.array(meta.get('mean', np.zeros_like(features)))
        std = np.array(meta.get('std', np.ones_like(features)))
        features = (features - mean) / (std + 1e-8)
        
        # Run inference
        with torch.no_grad():
            x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
            logits = model(x)
            probs = F.softmax(logits, dim=1).squeeze().numpy()
        
        # Map to labels
        labels = meta.get('labels', [])
        all_probs = {labels[i]: float(probs[i]) for i in range(len(labels))}
        
        # Sort and build hypotheses
        sorted_probs = sorted(all_probs.items(), key=lambda x: -x[1])
        
        hypotheses = []
        for label, prob in sorted_probs[:top_k]:
            hypotheses.append({
                "failure_id": label,
                "probability": prob,
                "description": self._get_failure_description(label),
            })
        
        # Compute confidence and ambiguity
        top_prob = sorted_probs[0][1] if sorted_probs else 0
        second_prob = sorted_probs[1][1] if len(sorted_probs) > 1 else 0
        
        confidence = top_prob
        is_ambiguous = (top_prob - second_prob) < 0.3
        
        # Get discriminating tests if ambiguous
        if is_ambiguous:
            top_failures = [h["failure_id"] for h in hypotheses[:3]]
            tests = self._get_discriminating_tests(system_id, top_failures)
        else:
            tests = []
        
        return DiagnosticResult(
            hypotheses=hypotheses,
            confidence=confidence,
            is_ambiguous=is_ambiguous,
            recommended_tests=tests,
            all_probabilities=all_probs,
        )
    
    def _extract_features(
        self,
        sensor_data: Dict[str, List[float]],
        feature_names: List[str],
    ) -> np.ndarray:
        """Extract statistical features from time series.
        
        Must match training exactly (train_hierarchical_from_chrono.py):
        11 features per sensor: mean, std, min, max, rate_mean, rate_max, 
        rate_min, first, last, range, trend
        """
        # Build features dict matching training format
        features_dict = {}
        
        # Get unique sensor names from feature names (e.g., 'coolant_temp_mean' -> 'coolant_temp')
        seen_sensors = set()
        for fn in feature_names:
            for suffix in ['_mean', '_std', '_min', '_max', '_rate_mean', '_rate_max', 
                          '_rate_min', '_first', '_last', '_range', '_trend']:
                if fn.endswith(suffix):
                    sensor = fn[:-len(suffix)]
                    seen_sensors.add(sensor)
                    break
        
        # Extract 11 features per sensor
        for sensor in seen_sensors:
            if sensor in sensor_data:
                values = sensor_data[sensor]
                if isinstance(values, list) and len(values) > 0:
                    arr = np.array(values, dtype=np.float64)
                    features_dict[f'{sensor}_mean'] = np.mean(arr)
                    features_dict[f'{sensor}_std'] = np.std(arr)
                    features_dict[f'{sensor}_min'] = np.min(arr)
                    features_dict[f'{sensor}_max'] = np.max(arr)
                    
                    if len(arr) > 1:
                        diff = np.diff(arr)
                        features_dict[f'{sensor}_rate_mean'] = np.mean(diff)
                        features_dict[f'{sensor}_rate_max'] = np.max(diff)
                        features_dict[f'{sensor}_rate_min'] = np.min(diff)
                        features_dict[f'{sensor}_first'] = arr[0]
                        features_dict[f'{sensor}_last'] = arr[-1]
                        features_dict[f'{sensor}_range'] = np.max(arr) - np.min(arr)
                        
                        x = np.arange(len(arr))
                        if np.std(arr) > 0:
                            features_dict[f'{sensor}_trend'] = np.corrcoef(x, arr)[0, 1]
                        else:
                            features_dict[f'{sensor}_trend'] = 0.0
                    else:
                        features_dict[f'{sensor}_rate_mean'] = 0.0
                        features_dict[f'{sensor}_rate_max'] = 0.0
                        features_dict[f'{sensor}_rate_min'] = 0.0
                        features_dict[f'{sensor}_first'] = arr[0]
                        features_dict[f'{sensor}_last'] = arr[0]
                        features_dict[f'{sensor}_range'] = 0.0
                        features_dict[f'{sensor}_trend'] = 0.0
                else:
                    for suffix in ['mean', 'std', 'min', 'max', 'rate_mean', 'rate_max',
                                   'rate_min', 'first', 'last', 'range', 'trend']:
                        features_dict[f'{sensor}_{suffix}'] = 0.0
            else:
                for suffix in ['mean', 'std', 'min', 'max', 'rate_mean', 'rate_max',
                               'rate_min', 'first', 'last', 'range', 'trend']:
                    features_dict[f'{sensor}_{suffix}'] = 0.0
        
        # Return features in sorted order (matching training)
        result = [features_dict.get(fn, 0.0) for fn in feature_names]
        return np.array(result, dtype=np.float32)
    
    def _get_failure_description(self, failure_id: str) -> str:
        """Get human-readable description of failure."""
        descriptions = {
            # Cooling
            "normal": "No failure detected - system operating normally",
            "thermostat_stuck_closed": "Thermostat stuck closed - engine overheating",
            "thermostat_stuck_open": "Thermostat stuck open - engine running cold",
            "water_pump_failure": "Water pump failure - no coolant circulation",
            "water_pump_belt_slipping": "Water pump belt slipping - reduced coolant flow",
            "radiator_blocked_external": "Radiator externally blocked - reduced airflow",
            "radiator_blocked_internal": "Radiator internally blocked - restricted flow",
            "radiator_blocked": "Radiator blocked - heat rejection impaired",
            "cooling_fan_not_operating": "Cooling fan not working - overheat at idle",
            "cooling_fan_always_on": "Cooling fan always on - possible sensor issue",
            "pressure_cap_faulty": "Pressure cap faulty - coolant boiling/loss",
            "ect_sensor_failed_high": "ECT sensor failed high - false hot reading",
            "ect_sensor_failed_low": "ECT sensor failed low - false cold reading",
            "coolant_leak": "Coolant leak - gradual system degradation",
            # Fuel
            "fuel_pump_weak": "Fuel pump weak - low fuel pressure",
            "fuel_filter_clogged": "Fuel filter clogged - restricted fuel flow",
            "fuel_pressure_regulator_stuck_open": "Fuel pressure regulator stuck open",
            "fuel_pressure_regulator_stuck_closed": "Fuel pressure regulator stuck closed",
            "injector_leak": "Injector leak - rich mixture",
            "maf_sensor_contaminated": "MAF sensor contaminated - incorrect air metering",
            # Ignition
            "spark_plug_fouled": "Spark plug fouled - weak spark",
            "ignition_coil_weak": "Ignition coil weak - misfire",
            "ckp_sensor_failing": "Crankshaft position sensor failing",
            "knock_sensor_failed": "Knock sensor failed - timing issue",
            # Charging
            "alternator_weak": "Alternator weak - low charging output",
            "battery_weak": "Battery weak - low capacity",
            "voltage_regulator_failed": "Voltage regulator failed",
            # Transmission
            "low_trans_fluid": "Low transmission fluid",
            "worn_clutch_packs": "Worn clutch packs - slipping",
            "solenoid_stuck": "Shift solenoid stuck",
            # Brakes
            "worn_brake_pads": "Worn brake pads",
            "warped_rotor": "Warped brake rotor - pulsation",
            "brake_fluid_leak": "Brake fluid leak - soft pedal",
            "master_cylinder_failing": "Master cylinder failing",
            "caliper_sticking": "Brake caliper sticking",
            # Engine
            "low_compression": "Low compression - worn rings/valves",
            "head_gasket_failure": "Head gasket failure",
            "timing_chain_stretched": "Timing chain stretched",
            "oil_pump_failure": "Oil pump failure - low pressure",
            "piston_ring_wear": "Piston ring wear - oil consumption",
        }
        return descriptions.get(failure_id, f"Failure: {failure_id.replace('_', ' ')}")
    
    def _get_discriminating_tests(self, system_id: str, failure_ids: List[str]) -> List[str]:
        """Get tests that can distinguish between the given failures."""
        # System-specific test recommendations
        tests_by_system = {
            "cooling": [
                "Compare actual vs reported coolant temp with infrared thermometer",
                "Pressure test cooling system",
                "Check thermostat opens in hot water bath",
                "Verify fan operation at operating temp",
            ],
            "fuel": [
                "Check fuel pressure with gauge",
                "Monitor fuel trims with scan tool",
                "Injector flow test",
                "MAF sensor cleaning or replacement",
            ],
            "ignition": [
                "Check spark with inline tester",
                "Scope ignition waveform",
                "Check for DTCs related to misfires",
                "Compression test all cylinders",
            ],
            "charging": [
                "Battery load test",
                "Check alternator output at idle and RPM",
                "Voltage drop test on charging circuit",
            ],
            "transmission": [
                "Check transmission fluid level and condition",
                "Line pressure test",
                "Scan for solenoid codes",
            ],
            "brakes": [
                "Measure brake pad thickness",
                "Check rotor runout with dial indicator",
                "Brake fluid condition and level",
                "Pedal travel test",
            ],
        }
        return tests_by_system.get(system_id, [
            "Check for related DTCs",
            "Perform system-specific diagnostic tests",
        ])
    
    def get_system_for_symptoms(self, symptoms: List[str]) -> Optional[str]:
        """
        Determine which system to diagnose based on symptoms.
        
        Args:
            symptoms: List of symptom descriptions
            
        Returns:
            System ID most likely affected
        """
        symptom_to_system = {
            "overheating": "cooling",
            "running hot": "cooling",
            "no heat": "cooling",
            "running cold": "cooling",
            "hard start": "fuel",
            "rough idle": "fuel",
            "stalling": "fuel",
            "hesitation": "fuel",
            "misfire": "ignition",
            "check engine light": "ignition",
            "battery light": "charging",
            "slow crank": "charging",
            "slipping": "transmission",
            "harsh shift": "transmission",
            "grinding brakes": "brakes",
            "soft pedal": "brakes",
            "pulsation": "brakes",
        }
        
        system_scores: Dict[str, int] = {}
        for symptom in symptoms:
            symptom_lower = symptom.lower()
            for key, system in symptom_to_system.items():
                if key in symptom_lower:
                    system_scores[system] = system_scores.get(system, 0) + 1
        
        if system_scores:
            return max(system_scores.items(), key=lambda x: x[1])[0]
        return None


# Singleton instance
_hierarchical_instance: Optional[HierarchicalInference] = None


def get_hierarchical_inference(model_path: Optional[str] = None) -> HierarchicalInference:
    """Get the hierarchical inference engine singleton."""
    global _hierarchical_instance
    
    if _hierarchical_instance is None:
        _hierarchical_instance = HierarchicalInference(model_path)
    
    return _hierarchical_instance
