"""
High-level diagnostic orchestrator.

Combines:
- ML predictions for initial hypotheses
- Bayesian reasoning for belief updates
- Causal knowledge for explanations
- Test recommendations for efficient diagnosis
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .bayesian import BayesianReasoner, BeliefState


@dataclass
class DiagnosticConclusion:
    """Final diagnostic conclusion with explanation."""
    
    # Most likely failure
    primary_diagnosis: str
    confidence: float
    
    # Alternative possibilities
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    
    # Explanation of reasoning
    explanation: str = ""
    
    # Evidence that led to conclusion
    supporting_evidence: List[str] = field(default_factory=list)
    
    # Recommended actions
    recommended_actions: List[str] = field(default_factory=list)
    
    # Was the diagnosis conclusive or needs more testing?
    is_conclusive: bool = False
    
    def __str__(self) -> str:
        lines = []
        lines.append("=" * 50)
        lines.append("DIAGNOSTIC CONCLUSION")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Primary Diagnosis: {self.primary_diagnosis}")
        lines.append(f"Confidence: {self.confidence:.1%}")
        
        if self.alternatives:
            lines.append("")
            lines.append("Alternative possibilities:")
            for alt, prob in self.alternatives[:3]:
                lines.append(f"  • {alt}: {prob:.1%}")
        
        if self.explanation:
            lines.append("")
            lines.append("Reasoning:")
            lines.append(f"  {self.explanation}")
        
        if self.supporting_evidence:
            lines.append("")
            lines.append("Supporting evidence:")
            for ev in self.supporting_evidence:
                lines.append(f"  ✓ {ev}")
        
        if self.recommended_actions:
            lines.append("")
            lines.append("Recommended actions:")
            for i, action in enumerate(self.recommended_actions, 1):
                lines.append(f"  {i}. {action}")
        
        if not self.is_conclusive:
            lines.append("")
            lines.append("⚠️ Additional testing recommended to confirm diagnosis")
        
        return "\n".join(lines)


@dataclass 
class DiagnosticSession:
    """
    Tracks an interactive diagnostic session.
    
    Records all observations, tests, and belief updates
    throughout the diagnostic process.
    """
    session_id: str
    started_at: datetime = field(default_factory=datetime.now)
    
    # Vehicle info
    vehicle_info: Dict[str, str] = field(default_factory=dict)
    
    # Initial complaint
    initial_symptoms: List[str] = field(default_factory=list)
    
    # Evidence collected during session
    observations: List[Dict] = field(default_factory=list)
    test_results: List[Dict] = field(default_factory=list)
    
    # Belief state history
    belief_history: List[BeliefState] = field(default_factory=list)
    
    # Final conclusion (if reached)
    conclusion: Optional[DiagnosticConclusion] = None


class Diagnostician:
    """
    Main diagnostic reasoning engine.
    
    Orchestrates the diagnostic process:
    1. Initializes from symptoms/sensor data
    2. Recommends tests to narrow down
    3. Updates beliefs as evidence arrives
    4. Reaches conclusion when confident
    
    Usage:
        diag = Diagnostician()
        session = diag.start_session(vehicle_info, symptoms)
        
        while not session.conclusion:
            test = diag.recommend_test(session)
            result = perform_test(test)  # User performs test
            diag.record_observation(session, test, result)
            
        print(session.conclusion)
    """
    
    def __init__(self, 
                 ml_model=None,
                 causal_graph=None):
        """
        Args:
            ml_model: Trained DiagnosticModel for initial predictions
            causal_graph: CausalGraph for explanations
        """
        self.ml_model = ml_model
        self.causal_graph = causal_graph
        self.reasoner = BayesianReasoner(causal_graph)
        
        # Session counter
        self._session_counter = 0
        
        # Failure descriptions for explanations
        self._failure_descriptions = {
            "normal": "System operating normally - no failure detected",
            "thermostat_stuck_closed": "Thermostat stuck in closed position, preventing coolant circulation to radiator",
            "thermostat_stuck_open": "Thermostat stuck open, causing engine to run cold and inefficient",
            "water_pump_failure": "Water pump failed, no coolant circulation through system",
            "water_pump_belt_slipping": "Water pump belt slipping, reduced coolant flow",
            "radiator_blocked_external": "Radiator fins blocked by debris, reducing airflow and heat dissipation",
            "radiator_blocked_internal": "Radiator passages blocked internally, restricting coolant flow",
            "radiator_blocked": "Radiator blockage impairing heat rejection",
            "cooling_fan_not_operating": "Cooling fan not running when needed, overheat at low speed/idle",
            "cooling_fan_always_on": "Cooling fan running continuously, possible sensor or relay issue",
            "pressure_cap_faulty": "Radiator pressure cap not holding pressure, lowered boiling point",
            "ect_sensor_failed_high": "Coolant temperature sensor failed high, false hot reading to ECU",
            "ect_sensor_failed_low": "Coolant temperature sensor failed low, false cold reading to ECU",
            "coolant_leak": "Coolant leak somewhere in system, gradual loss of coolant",
        }
        
        # Recommended repair actions
        self._repair_actions = {
            "thermostat_stuck_closed": [
                "Replace thermostat",
                "Flush cooling system",
                "Inspect housing gasket",
            ],
            "thermostat_stuck_open": [
                "Replace thermostat",
                "Check for prior overheating damage",
            ],
            "water_pump_failure": [
                "Replace water pump",
                "Inspect timing belt if driven",
                "Flush cooling system",
            ],
            "radiator_blocked_external": [
                "Clean radiator fins with compressed air/water",
                "Inspect AC condenser if applicable",
            ],
            "radiator_blocked_internal": [
                "Replace radiator",
                "Flush entire cooling system",
                "Check for contamination source",
            ],
            "cooling_fan_not_operating": [
                "Check fan fuse and relay",
                "Test fan motor directly",
                "Check coolant temp sensor signal",
            ],
            "ect_sensor_failed_high": [
                "Replace coolant temperature sensor",
                "Check wiring for shorts to ground",
            ],
            "ect_sensor_failed_low": [
                "Replace coolant temperature sensor",
                "Check wiring for open circuit",
            ],
            "coolant_leak": [
                "Pressure test system to locate leak",
                "Inspect hoses, clamps, and gaskets",
                "Check water pump weep hole",
            ],
            "pressure_cap_faulty": [
                "Replace radiator cap",
                "Pressure test old cap to confirm",
            ],
        }
    
    def start_session(self,
                      vehicle_info: Optional[Dict] = None,
                      initial_symptoms: Optional[List[str]] = None,
                      sensor_data: Optional[Dict] = None) -> DiagnosticSession:
        """
        Start a new diagnostic session.
        
        Args:
            vehicle_info: Vehicle year/make/model/engine
            initial_symptoms: Customer complaints or observed symptoms
            sensor_data: Initial sensor readings (for ML prediction)
            
        Returns:
            New DiagnosticSession
        """
        self._session_counter += 1
        session_id = f"diag_{self._session_counter}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = DiagnosticSession(
            session_id=session_id,
            vehicle_info=vehicle_info or {},
            initial_symptoms=initial_symptoms or [],
        )
        
        # Initialize beliefs
        prior_probs = None
        
        # Use ML model if available and we have sensor data
        if self.ml_model is not None and sensor_data is not None:
            try:
                # Get ML predictions
                # Allow ml_model to be either a model instance or a path
                from ..ml.inference import DiagnosticInference
                if isinstance(self.ml_model, str):
                    inference = DiagnosticInference.load(self.ml_model)
                else:
                    inference = DiagnosticInference(self.ml_model)

                # If sensor_data contains scalar observations (e.g., coolant_temp: 50),
                # use diagnose_from_observations which accepts point values.
                if isinstance(sensor_data, dict) and all(isinstance(v, (int, float, bool)) for v in sensor_data.values()):
                    result = inference.diagnose_from_observations(sensor_data)
                else:
                    result = inference.diagnose(sensor_data)

                prior_probs = result.all_probabilities
            except Exception as e:
                print(f"ML prediction failed, using uniform prior: {e}")
        
        # Create initial belief state
        initial_state = self.reasoner.create_initial_state(prior_probs)
        
        # Update with initial symptoms
        for symptom in (initial_symptoms or []):
            initial_state = self._symptom_to_evidence(initial_state, symptom)
        
        session.belief_history.append(initial_state)
        
        return session
    
    def _symptom_to_evidence(self, state: BeliefState, symptom: str) -> BeliefState:
        """Convert symptom description to evidence update."""
        # Map common symptom descriptions to evidence types
        symptom_map = {
            "overheating": "coolant_temp_high",
            "running hot": "coolant_temp_high",
            "temp gauge high": "coolant_temp_high",
            "engine hot": "coolant_temp_high",
            "running cold": "coolant_temp_low",
            "no heat": "coolant_temp_low",
            "heater not working": "coolant_temp_low",
            "coolant low": "coolant_level_low",
            "coolant leak": "coolant_level_low",
            "fan not working": "fan_not_running_when_hot",
            "fan always on": "fan_always_running",
            "p0217": "dtc_P0217",
            "p0128": "dtc_P0128",
            "p0118": "dtc_P0118",
            "p0117": "dtc_P0117",
        }
        
        symptom_lower = symptom.lower()
        for key, evidence_type in symptom_map.items():
            if key in symptom_lower:
                return self.reasoner.update(state, evidence_type, observed=True)
        
        return state
    
    def get_current_state(self, session: DiagnosticSession) -> BeliefState:
        """Get current belief state for session."""
        if session.belief_history:
            return session.belief_history[-1]
        return self.reasoner.create_initial_state()
    
    def record_observation(self, session: DiagnosticSession,
                          evidence_type: str,
                          observed: bool = True,
                          notes: str = "") -> BeliefState:
        """
        Record an observation and update beliefs.
        
        Args:
            session: Current diagnostic session
            evidence_type: Type of evidence observed
            observed: True if symptom/condition present, False if absent
            notes: Optional notes about the observation
            
        Returns:
            Updated belief state
        """
        current_state = self.get_current_state(session)
        new_state = self.reasoner.update(current_state, evidence_type, observed)
        
        session.belief_history.append(new_state)
        session.observations.append({
            "type": evidence_type,
            "observed": observed,
            "notes": notes,
            "timestamp": datetime.now().isoformat(),
        })
        
        # Check if we can reach a conclusion
        self._check_conclusion(session)
        
        return new_state
    
    def record_test_result(self, session: DiagnosticSession,
                          test_name: str,
                          result: str,
                          evidence_type: Optional[str] = None) -> BeliefState:
        """
        Record a test result and update beliefs.
        
        Args:
            session: Current diagnostic session
            test_name: Name of test performed
            result: Result description
            evidence_type: Evidence type for belief update
            
        Returns:
            Updated belief state
        """
        session.test_results.append({
            "test": test_name,
            "result": result,
            "timestamp": datetime.now().isoformat(),
        })
        
        if evidence_type:
            return self.record_observation(session, evidence_type, observed=True)
        
        return self.get_current_state(session)
    
    def recommend_test(self, session: DiagnosticSession) -> Optional[Dict]:
        """
        Recommend the most informative next test.
        
        Returns test recommendation or None if conclusion reached.
        """
        if session.conclusion is not None:
            return None
        
        current_state = self.get_current_state(session)
        return self.reasoner.get_best_test(current_state)
    
    def _check_conclusion(self, session: DiagnosticSession,
                         confidence_threshold: float = 0.7) -> None:
        """Check if we can reach a diagnostic conclusion."""
        state = self.get_current_state(session)
        
        if state.is_confident(confidence_threshold):
            # We're confident enough
            top_hyps = state.get_top_hypotheses(5)
            primary = top_hyps[0]
            
            session.conclusion = DiagnosticConclusion(
                primary_diagnosis=primary[0],
                confidence=primary[1],
                alternatives=top_hyps[1:4],
                explanation=self._failure_descriptions.get(primary[0], ""),
                supporting_evidence=[
                    e["type"] for e in state.evidence if e.get("observed", True)
                ],
                recommended_actions=self._repair_actions.get(primary[0], [
                    "Further diagnosis required"
                ]),
                is_conclusive=primary[1] >= 0.85,
            )
    
    def force_conclusion(self, session: DiagnosticSession) -> DiagnosticConclusion:
        """
        Force a conclusion even if not fully confident.
        
        Useful when we need to make a decision with available evidence.
        """
        state = self.get_current_state(session)
        top_hyps = state.get_top_hypotheses(5)
        
        # Safety override: if both numeric insulation PID and DTC evidence are present, force HV isolation conclusion
        obs_types = [o["type"] for o in session.observations]
        has_pid = any(t == "insulation_resistance_low" for t in obs_types)
        has_dtc = any(t == "dtc_insulation_resistance_low" for t in obs_types)
        if has_pid and has_dtc:
            primary_failure = "tesla_hv_isolation_fault" if "tesla_hv_isolation_fault" in self._failure_descriptions else "hv_isolation_fault"
            recommended_actions = self._repair_actions.get(primary_failure, ["Inspect HV system, perform megohmmeter test, isolate components"]) 
            conclusion = DiagnosticConclusion(
                primary_diagnosis=primary_failure,
                confidence=0.95,
                alternatives=[],
                explanation=self._failure_descriptions.get(primary_failure, "High voltage isolation fault"),
                supporting_evidence=[o["type"] for o in session.observations if o.get("observed", True)],
                recommended_actions=recommended_actions,
                is_conclusive=True,
            )
            session.conclusion = conclusion
            return conclusion

        if not top_hyps:
            return DiagnosticConclusion(
                primary_diagnosis="unknown",
                confidence=0.0,
                explanation="Insufficient evidence for diagnosis",
                is_conclusive=False,
            )
        
        primary = top_hyps[0]
        
        conclusion = DiagnosticConclusion(
            primary_diagnosis=primary[0],
            confidence=primary[1],
            alternatives=top_hyps[1:4],
            explanation=self._failure_descriptions.get(primary[0], ""),
            supporting_evidence=[
                e["type"] for e in state.evidence if e.get("observed", True)
            ],
            recommended_actions=self._repair_actions.get(primary[0], []),
            is_conclusive=primary[1] >= 0.85,
        )
        
        session.conclusion = conclusion
        return conclusion
    
    def explain_reasoning(self, session: DiagnosticSession) -> str:
        """
        Generate a human-readable explanation of the diagnostic reasoning.
        """
        state = self.get_current_state(session)
        lines = []
        
        lines.append("Diagnostic Reasoning Trace")
        lines.append("=" * 40)
        
        # Initial symptoms
        if session.initial_symptoms:
            lines.append("\nInitial symptoms:")
            for s in session.initial_symptoms:
                lines.append(f"  • {s}")
        
        # Evidence collected
        if state.evidence:
            lines.append("\nEvidence collected:")
            for e in state.evidence:
                status = "✓" if e.get("observed", True) else "✗"
                lines.append(f"  {status} {e['type']}")
        
        # Current beliefs
        lines.append("\nCurrent beliefs:")
        for failure, prob in state.get_top_hypotheses(5):
            bar = "█" * int(prob * 20)
            lines.append(f"  {failure}: {prob:.1%} {bar}")
        
        # Entropy (uncertainty)
        entropy = state.get_entropy()
        max_entropy = 3.7  # log2(13) for 13 classes
        certainty = 1.0 - (entropy / max_entropy)
        lines.append(f"\nCertainty: {certainty:.1%}")
        
        # Next recommendation
        if session.conclusion is None:
            next_test = self.recommend_test(session)
            if next_test:
                lines.append(f"\nRecommended next test:")
                lines.append(f"  {next_test['description']}")
        
        return "\n".join(lines)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

# Default model path
DEFAULT_MODEL_PATH = "/home/drawson/autotech_ai/addons/predictive_diagnostics/models/trained_model.pt"

def quick_diagnose(symptoms: List[str],
                   observations: Optional[Dict[str, bool]] = None,
                   model_path: Optional[str] = None) -> DiagnosticConclusion:
    """
    Quick diagnostic from symptoms and observations.
    
    Args:
        symptoms: List of symptom descriptions
        observations: Optional dict of evidence_type -> True/False
        model_path: Path to trained ML model (optional)
        
    Returns:
        DiagnosticConclusion
    """
    import os
    
    # Load ML model if available
    ml_model = None
    mp = model_path or DEFAULT_MODEL_PATH
    if os.path.exists(mp):
        ml_model = mp  # Diagnostician will load it as path
    
    diag = Diagnostician(ml_model=ml_model)
    session = diag.start_session(initial_symptoms=symptoms)
    
    # Add observations
    if observations:
        for evidence_type, observed in observations.items():
            diag.record_observation(session, evidence_type, observed)
    
    # Force conclusion
    return diag.force_conclusion(session)
