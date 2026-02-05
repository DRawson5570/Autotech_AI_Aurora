"""
Diagnostic Reasoner

The runtime reasoning engine that takes scanner data and produces diagnoses.
This is the main interface used by the Open WebUI tool.

The reasoner:
1. Accepts scanner data (PIDs, DTCs, symptoms)
2. Loads appropriate pre-trained models
3. Performs Bayesian inference using fault trees
4. Combines ML predictions with probabilistic reasoning
5. Returns ranked diagnoses with explanations and recommended tests

NO Mitchell queries at runtime - all knowledge is pre-trained.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from .models import (
    Vehicle, 
    ScannerData, 
    PIDReading, 
    DTCCode,
    DiagnosticResult,
    DiagnosticHypothesis,
    DiagnosticTest,
    Severity
)
from .fault_tree import FaultTree, FaultNode
from .signatures import FAILURE_SIGNATURES, get_signatures_for_dtc
from .training import ModelManager
from .classifier import COMMON_PID_FEATURES

logger = logging.getLogger(__name__)


@dataclass
class SymptomReport:
    """User-reported symptoms."""
    descriptions: List[str]    # Free-text symptom descriptions
    conditions: Dict[str, str] = field(default_factory=dict)  # Structured conditions
    # e.g., {"when": "accelerating", "temperature": "cold", "frequency": "intermittent"}


class DiagnosticReasoner:
    """
    Main diagnostic reasoning engine.
    
    Combines:
    - Pre-trained ML models (Random Forest + GA rules)
    - Fault tree probabilistic reasoning
    - Symptom-to-fault matching
    - Bayesian inference for evidence updating
    
    Usage:
        reasoner = DiagnosticReasoner()
        result = reasoner.diagnose(
            vehicle=Vehicle(year=2020, make="Chevrolet", model="Bolt EV"),
            scanner_data=ScannerData(...),
            symptoms=SymptomReport(descriptions=["reduced power", "high temp warning"])
        )
    """
    
    def __init__(self, model_dir: str = "/tmp/predictive_diagnostics/models"):
        """
        Initialize the reasoner.
        
        Args:
            model_dir: Directory containing trained models
        """
        self.model_manager = ModelManager(model_dir)
        self._symptom_keywords = self._build_symptom_keywords()
    
    def _build_symptom_keywords(self) -> Dict[str, List[str]]:
        """Build mapping of symptoms to related failure modes."""
        return {
            # Temperature symptoms
            "overheating": ["motor_open_winding", "relay_coil_open", "pump_motor_failure", 
                          "motor_seized", "valve_stuck_closed"],
            "running hot": ["motor_open_winding", "relay_coil_open", "valve_stuck_closed"],
            "temp warning": ["motor_open_winding", "sensor_stuck_low", "valve_stuck_closed"],
            "temp gauge high": ["motor_open_winding", "sensor_stuck_high"],
            
            # Power symptoms
            "reduced power": ["motor_weak", "connector_high_resistance", "sensor_erratic",
                            "coil_weak", "injector_clogged"],
            "no power": ["motor_open_winding", "relay_coil_open", "fuse_blown", 
                        "connector_open", "wiring_open"],
            "loss of power": ["motor_open_winding", "relay_coil_open", "sensor_stuck_low"],
            
            # Starting symptoms
            "no start": ["motor_open_winding", "relay_coil_open", "fuse_blown",
                        "coil_open_primary", "injector_stuck_closed"],
            "hard start": ["coil_weak", "plug_fouled", "injector_clogged", 
                          "sensor_slow_response"],
            "cranks no start": ["coil_open_primary", "injector_stuck_closed", 
                               "sensor_stuck_low"],
            
            # Running symptoms  
            "rough idle": ["coil_weak", "plug_fouled", "injector_clogged",
                          "sensor_erratic", "valve_leaking"],
            "misfire": ["coil_open_primary", "coil_weak", "plug_fouled",
                       "plug_cracked", "injector_clogged"],
            "stalling": ["sensor_stuck_low", "valve_stuck_closed", "relay_contacts_pitted"],
            
            # Fuel symptoms
            "poor fuel economy": ["injector_leaking", "sensor_offset_drift", 
                                 "valve_stuck_open"],
            "rich running": ["injector_leaking", "injector_stuck_open", "sensor_stuck_low"],
            "lean running": ["injector_clogged", "valve_stuck_closed", "sensor_stuck_high"],
            "fuel smell": ["injector_leaking", "injector_stuck_open"],
            
            # Electrical symptoms
            "battery drain": ["relay_contacts_welded", "motor_shorted_winding"],
            "check engine light": ["sensor_stuck_low", "sensor_stuck_high", 
                                   "coil_open_primary", "injector_clogged"],
            "warning light": ["sensor_erratic", "motor_open_winding"],
            
            # Noise symptoms
            "clicking": ["relay_coil_open", "relay_contacts_pitted"],
            "grinding": ["motor_seized", "motor_worn_brushes"],
            "whining": ["motor_weak", "pump_motor_failure"],
            
            # EV-specific
            "thermal event": ["motor_open_winding", "connector_high_resistance"],
            "charging issue": ["relay_coil_open", "connector_open"],
            # Isolation / insulation related symptoms
            "isolation": ["tesla_hv_isolation_fault", "hv_isolation_fault"],
            "isolation fault": ["tesla_hv_isolation_fault", "hv_isolation_fault"],
            "insulation": ["tesla_hv_isolation_fault", "hv_isolation_fault"],
        }
    
    def _match_symptoms_to_failures(
        self, 
        symptoms: SymptomReport
    ) -> Dict[str, float]:
        """
        Match reported symptoms to potential failure modes.
        
        Returns:
            Dict of failure_mode_id -> confidence boost
        """
        matches = {}
        
        for description in symptoms.descriptions:
            desc_lower = description.lower()
            
            for symptom_key, failure_modes in self._symptom_keywords.items():
                if symptom_key in desc_lower:
                    for mode in failure_modes:
                        matches[mode] = matches.get(mode, 0) + 0.15
        
        # Normalize to max 0.5 boost
        if matches:
            max_boost = max(matches.values())
            if max_boost > 0.5:
                factor = 0.5 / max_boost
                matches = {k: v * factor for k, v in matches.items()}
        
        return matches
    
    def _match_dtcs_to_failures(
        self,
        dtcs: List[DTCCode]
    ) -> Dict[str, float]:
        """
        Match DTCs to potential failure modes using signatures.
        
        Returns:
            Dict of failure_mode_id -> confidence boost
        """
        matches = {}
        
        for dtc in dtcs:
            signatures = get_signatures_for_dtc(dtc.code)
            for sig in signatures:
                matches[sig.failure_mode_id] = matches.get(sig.failure_mode_id, 0) + 0.25
        
        return matches

    def _match_signatures_to_pid_values(
        self,
        pid_values: Dict[str, float],
        active_dtcs: List[str]
    ) -> Dict[str, float]:
        """Existing signature matcher (kept above helper for extraction)."""
        matches = {}
        # Use the signature database to score signals
        for sig in FAILURE_SIGNATURES.values():
            score, evidence = sig.calculate_match_score(pid_values, active_dtcs=active_dtcs)
            if score > 0.35:
                matches[sig.failure_mode_id] = score
        return matches

    def _extract_pid_values_from_symptoms(self, symptoms: SymptomReport) -> Dict[str, float]:
        """
        Parse free-text symptom descriptions to extract numeric PID values.

        Currently supports:
        - insulation_resistance in MΩ or kΩ or Ω (e.g., "0.05 MΩ", "50 kΩ", "50kohm")

        Returns a dict mapping synthetic PID names to numeric values (in the same units expected
        by signatures, e.g., MOhm for insulation_resistance).
        """
        import re
        matches = {}
        if not symptoms:
            return matches

        text = " ".join(symptoms.descriptions).lower()

        # Match patterns like 'insulation 0.05 m', 'insulation resistance 0.05 mΩ', 'hv+ to chassis insulation 0.05 MOhm'
        m = re.search(r"(?:insulation(?:[_ ]resistance)?|insulation to chassis|hv\+ to chassis insulation)[^0-9\n\r\-]*([0-9]*\.?[0-9]+)\s*(m|k|kilo|mega|ohm|Ω|mΩ|mohm|mohms|kohm|kΩ)?", text)
        if m:
            raw_val = float(m.group(1))
            unit = (m.group(2) or "").lower()

            # Normalize to MOhm
            if unit.startswith("k") or unit.startswith("kilo"):
                val_mohm = raw_val / 1000.0
            elif unit.startswith("m") and ("ohm" in unit or "ω" in unit or unit == "m"):
                # 'm' could be ambiguous; if it's 'm' followed by ohm sign we treat as mega (M)
                # but if it's just 'm' without context, assume mega (MΩ) for common usage here
                val_mohm = raw_val
            elif unit.startswith("mega") or unit.startswith("m"):
                val_mohm = raw_val
            elif unit.startswith("ohm") or unit == "ω" or unit == "":
                # value in ohms -> convert to MOhm
                val_mohm = raw_val / 1_000_000.0
            else:
                # fallback: assume value already in MOhm
                val_mohm = raw_val

            matches["insulation_resistance"] = val_mohm

        return matches
        """
        Match PID/numeric sensor values against known failure signatures.

        Returns:
            Dict of failure_mode_id -> confidence score (0.0 - 1.0)
        """
        matches = {}
        # Use the signature database to score signals
        for sig in FAILURE_SIGNATURES.values():
            score, evidence = sig.calculate_match_score(pid_values, active_dtcs=active_dtcs)
            if score > 0.35:
                matches[sig.failure_mode_id] = score
        return matches
    
    def _compute_bayesian_probabilities(
        self,
        fault_tree: FaultTree,
        ml_predictions: List[Tuple[str, float]],
        symptom_matches: Dict[str, float],
        dtc_matches: Dict[str, float],
        signature_matches: Dict[str, float] = None,
    ) -> List[DiagnosticHypothesis]:
        """
        Compute final probabilities using Bayesian reasoning.
        
        Combines:
        - Prior probabilities from fault tree (including TSB boosts)
        - ML model predictions
        - Symptom matching evidence
        - DTC matching evidence
        """
        hypotheses = []
        
        # Build probability map from all sources
        all_fault_ids = set()
        for fault_id, _ in ml_predictions:
            all_fault_ids.add(fault_id)
        all_fault_ids.update(symptom_matches.keys())
        all_fault_ids.update(dtc_matches.keys())
        for node_id in fault_tree.fault_nodes.keys():
            all_fault_ids.add(node_id)
        
        for fault_id in all_fault_ids:
            # Get prior from fault tree
            node = fault_tree.fault_nodes.get(fault_id)
            if node:
                prior = node.effective_probability
            else:
                prior = 0.05  # Default prior
            
            # Get ML probability
            ml_prob = 0.0
            for fid, prob in ml_predictions:
                if fid == fault_id:
                    ml_prob = prob
                    break
            
            # Get symptom boost
            symptom_boost = symptom_matches.get(fault_id, 0.0)
            
            # Get DTC boost  
            dtc_boost = dtc_matches.get(fault_id, 0.0)

            # Get signature (PID) boost
            signature_boost = 0.0
            if signature_matches:
                signature_boost = signature_matches.get(fault_id, 0.0)
            
            # Combine using weighted formula
            # ML weight reduced when not available; DTCs and signal signatures get higher weight
            combined = (
                0.3 * ml_prob +
                0.35 * min(1.0, dtc_boost * 3) +  # Stronger DTC influence for safety-critical alerts
                0.3 * min(1.0, signature_boost) +
                0.1 * min(1.0, symptom_boost * 2) +
                0.05 * prior
            )

            # Safety-critical override handled later where evidence lists are available
            
            # Build evidence lists
            evidence_for = []
            evidence_against = []
            
            if ml_prob > 0.3:
                evidence_for.append(f"ML model predicts {ml_prob:.0%} probability")
            if dtc_boost > 0:
                evidence_for.append(f"DTC pattern match (confidence +{dtc_boost:.0%})")
            if signature_boost > 0:
                evidence_for.append(f"Signal signature match (confidence +{signature_boost:.0%})")
            if symptom_boost > 0:
                evidence_for.append(f"Symptom match (confidence +{symptom_boost:.0%})")
            if node and node.tsb_reference:
                evidence_for.append(f"Known issue: {node.tsb_reference}")

            # Safety-critical override: strong signature + DTC for HV isolation should yield high confidence
            if fault_id in ("tesla_hv_isolation_fault", "hv_isolation_fault") and signature_boost > 0.85 and dtc_boost > 0:
                combined = max(combined, 0.9)
                evidence_for.append("Sensor + DTC override applied for isolation fault")
            
            if combined < 0.1:
                evidence_against.append("Low overall probability")
            
            # Skip very low probability hypotheses
            if combined < 0.05 and not evidence_for:
                continue
            
            hypothesis = DiagnosticHypothesis(
                fault_node_id=fault_id,
                component=node.component.name if node else "Unknown",
                failure_mode=node.failure_mode.name if node else fault_id,
                probability=min(1.0, combined),
                confidence=0.7 if ml_prob > 0.3 else 0.5,
                supporting_evidence=evidence_for,
                contradicting_evidence=evidence_against,
            )
            hypotheses.append(hypothesis)
        
        # Sort by probability
        hypotheses.sort(key=lambda h: h.probability, reverse=True)
        
        return hypotheses
    
    def _generate_diagnostic_tests(
        self,
        hypotheses: List[DiagnosticHypothesis],
        fault_tree: FaultTree,
        max_tests: int = 5
    ) -> List[DiagnosticTest]:
        """
        Generate recommended diagnostic tests to discriminate between hypotheses.
        """
        tests = []
        seen_tests = set()
        
        for hyp in hypotheses[:max_tests]:
            node = fault_tree.fault_nodes.get(hyp.fault_node_id)
            if not node:
                continue
            
            test_desc = node.diagnostic_test or node.failure_mode.diagnostic_approach
            
            # Avoid duplicate tests
            if test_desc in seen_tests:
                continue
            seen_tests.add(test_desc)
            
            test = DiagnosticTest(
                name=f"Test for {node.failure_mode.name}",
                description=test_desc,
                procedure=test_desc,
                expected_result_if_faulty=f"Confirms {node.failure_mode.name}",
                expected_result_if_good="Component operating normally",
                tools_required=self._extract_tools(test_desc),
                difficulty="medium",
                time_estimate_minutes=15,
                discriminates_between=[hyp.fault_node_id],
            )
            tests.append(test)
        
        return tests
    
    def _extract_tools(self, test_description: str) -> List[str]:
        """Extract required tools from test description."""
        tools = []
        desc_lower = test_description.lower()
        
        if "multimeter" in desc_lower or "resistance" in desc_lower or "voltage" in desc_lower:
            tools.append("Digital Multimeter")
        if "scope" in desc_lower or "waveform" in desc_lower:
            tools.append("Oscilloscope")
        if "scan" in desc_lower or "dtc" in desc_lower:
            tools.append("OBD-II Scanner")
        if "pressure" in desc_lower:
            tools.append("Pressure Gauge")
        if "continuity" in desc_lower:
            tools.append("Continuity Tester")
        
        return tools if tools else ["Basic Hand Tools"]
    
    def diagnose(
        self,
        vehicle: Vehicle,
        scanner_data: ScannerData = None,
        symptoms: SymptomReport = None,
        system: str = "Cooling System",
        top_k: int = 5,
    ) -> DiagnosticResult:
        """
        Perform diagnostic analysis.
        
        Args:
            vehicle: Vehicle identification
            scanner_data: Scanner data with PIDs and DTCs
            symptoms: User-reported symptoms
            system: System to diagnose
            top_k: Number of top diagnoses to return
            
        Returns:
            DiagnosticResult with ranked hypotheses and recommended tests
        """
        start_time = datetime.now()
        
        # Extract PID values (from scanner data if present)
        pid_values = {}
        if scanner_data:
            for pid in scanner_data.pids:
                pid_values[pid.name] = pid.value

        # Also extract numeric measurements embedded in free-text symptoms
        # (e.g., "HV+ to chassis insulation 0.05 MΩ") and inject as synthetic PIDs
        pid_from_text = self._extract_pid_values_from_symptoms(symptoms) if symptoms else {}
        for k, v in pid_from_text.items():
            # Do not override scanner-provided PIDs
            if k not in pid_values:
                pid_values[k] = v
        
        # Extract DTCs
        dtc_codes = []
        dtc_objects = []
        if scanner_data:
            for dtc in scanner_data.dtcs:
                dtc_codes.append(dtc.code)
                dtc_objects.append(dtc)
        
        # Get ML predictions
        ml_result = self.model_manager.predict(
            year=vehicle.year,
            make=vehicle.make,
            model=vehicle.model,
            system=system,
            pid_values=pid_values,
            dtc_codes=dtc_codes,
            top_k=top_k * 2  # Get more to filter later
        )
        
        # If model missing or error, continue with empty ML predictions (we still use DTCs/signatures/symptoms)
        if "error" in ml_result:
            logger.warning("Model not found or model error; continuing with rule-based reasoning")
            ml_result = {"predictions": []}
        
        # Load fault tree for detailed reasoning
        key = f"{vehicle.year}_{vehicle.make.lower().replace(' ', '_')}_{vehicle.model.lower().replace(' ', '_')}_{system.lower().replace(' ', '_')}"
        model_data = self.model_manager.loaded_models.get(key, {})
        fault_tree = model_data.get("fault_tree")
        
        if not fault_tree:
            # Create minimal fault tree from predictions
            from .fault_tree import FaultTree, FaultNode, Component
            from .taxonomy import ComponentType, FailureMode
            
            fault_tree = FaultTree(
                vehicle_year=vehicle.year,
                vehicle_make=vehicle.make,
                vehicle_model=vehicle.model,
                vehicle_engine=vehicle.engine,
                system=system,
            )
        
        # Match symptoms to failure modes
        symptom_matches = {}
        if symptoms:
            symptom_matches = self._match_symptoms_to_failures(symptoms)
        
        # Match DTCs to failure modes
        dtc_matches = self._match_dtcs_to_failures(dtc_objects)
        
        # Match signatures against PID values and active DTCs
        signature_matches = self._match_signatures_to_pid_values(pid_values, dtc_codes)

        # Convert ML predictions to tuple format
        ml_predictions = [
            (p["fault_id"], p["probability"])
            for p in ml_result.get("predictions", [])
        ]
        
        # Compute Bayesian probabilities
        hypotheses = self._compute_bayesian_probabilities(
            fault_tree=fault_tree,
            ml_predictions=ml_predictions,
            symptom_matches=symptom_matches,
            dtc_matches=dtc_matches,
            signature_matches=signature_matches,
        )
        
        # Take top_k
        hypotheses = hypotheses[:top_k]
        
        # Generate diagnostic tests
        tests = self._generate_diagnostic_tests(hypotheses, fault_tree)
        
        # Determine confidence level
        if hypotheses and hypotheses[0].probability > 0.7:
            confidence = "high"
        elif hypotheses and hypotheses[0].probability > 0.4:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Build result
        result = DiagnosticResult(
            vehicle=vehicle,
            symptoms_analyzed=symptoms.descriptions if symptoms else [],
            hypotheses=hypotheses,
            recommended_tests=tests,
            most_likely_fault=hypotheses[0] if hypotheses else None,
            confidence_level=confidence,
        )
        
        # Add repair info for most likely fault
        if hypotheses:
            top_hyp = hypotheses[0]
            node = fault_tree.fault_nodes.get(top_hyp.fault_node_id)
            if node:
                result.repair_plan = node.repair_action
                result.estimated_repair_time = node.repair_time_hours
                result.estimated_cost = node.parts_cost
                if node.tsb_reference:
                    result.tsb_references.append(node.tsb_reference)
        
        return result
    
    def update_diagnosis(
        self,
        previous_result: DiagnosticResult,
        test_result: str,
        test_passed: bool,
    ) -> DiagnosticResult:
        """
        Update diagnosis based on a test result.
        
        This implements iterative diagnostic refinement - after each test,
        we update probabilities based on the outcome.
        
        Args:
            previous_result: Previous diagnostic result
            test_result: Description of test performed
            test_passed: Whether the test passed (component good) or failed (component bad)
            
        Returns:
            Updated DiagnosticResult with refined probabilities
        """
        # Find which hypothesis the test relates to
        updated_hypotheses = []
        
        for hyp in previous_result.hypotheses:
            new_prob = hyp.probability
            new_evidence = list(hyp.supporting_evidence)
            new_against = list(hyp.contradicting_evidence)
            
            # Check if test relates to this hypothesis
            test_lower = test_result.lower()
            component_lower = hyp.component.lower()
            
            if component_lower in test_lower or hyp.failure_mode.lower() in test_lower:
                if test_passed:
                    # Test passed = component is good = reduce probability
                    new_prob *= 0.3
                    new_against.append(f"Test passed: {test_result}")
                else:
                    # Test failed = component is bad = increase probability
                    new_prob = min(0.95, new_prob * 2.5)
                    new_evidence.append(f"Test confirmed: {test_result}")
            
            updated_hyp = DiagnosticHypothesis(
                fault_node_id=hyp.fault_node_id,
                component=hyp.component,
                failure_mode=hyp.failure_mode,
                probability=new_prob,
                confidence=hyp.confidence + 0.1,  # More confident after test
                supporting_evidence=new_evidence,
                contradicting_evidence=new_against,
            )
            updated_hypotheses.append(updated_hyp)
        
        # Re-sort by probability
        updated_hypotheses.sort(key=lambda h: h.probability, reverse=True)
        
        # Determine new confidence level
        if updated_hypotheses and updated_hypotheses[0].probability > 0.8:
            confidence = "high"
        elif updated_hypotheses and updated_hypotheses[0].probability > 0.5:
            confidence = "medium"
        else:
            confidence = "low"
        
        return DiagnosticResult(
            vehicle=previous_result.vehicle,
            symptoms_analyzed=previous_result.symptoms_analyzed + [f"Test: {test_result}"],
            hypotheses=updated_hypotheses,
            recommended_tests=previous_result.recommended_tests,  # Could regenerate
            most_likely_fault=updated_hypotheses[0] if updated_hypotheses else None,
            confidence_level=confidence,
            tsb_references=previous_result.tsb_references,
        )
    
    def format_diagnosis_text(self, result: DiagnosticResult) -> str:
        """
        Format diagnostic result as human-readable text.
        
        Suitable for display in Open WebUI chat.
        """
        lines = []
        
        lines.append(f"## Diagnostic Analysis: {result.vehicle}")
        lines.append("")
        
        if result.symptoms_analyzed:
            lines.append(f"**Symptoms Analyzed:** {', '.join(result.symptoms_analyzed)}")
            lines.append("")
        
        lines.append(f"**Confidence Level:** {result.confidence_level.upper()}")
        lines.append("")
        
        if result.most_likely_fault:
            top = result.most_likely_fault
            lines.append("### Most Likely Diagnosis")
            lines.append(f"**{top.component}** - {top.failure_mode}")
            lines.append(f"- Probability: {top.probability:.0%}")
            if top.supporting_evidence:
                lines.append(f"- Evidence: {', '.join(top.supporting_evidence)}")
            lines.append("")
        
        if len(result.hypotheses) > 1:
            lines.append("### Other Possibilities")
            for hyp in result.hypotheses[1:4]:
                lines.append(f"- **{hyp.component}** ({hyp.failure_mode}): {hyp.probability:.0%}")
            lines.append("")
        
        if result.recommended_tests:
            lines.append("### Recommended Tests")
            for i, test in enumerate(result.recommended_tests[:3], 1):
                lines.append(f"{i}. **{test.name}**")
                lines.append(f"   {test.procedure}")
            lines.append("")
        
        if result.repair_plan:
            lines.append("### Repair Recommendation")
            lines.append(result.repair_plan)
            if result.estimated_repair_time:
                lines.append(f"- Estimated Time: {result.estimated_repair_time:.1f} hours")
            if result.estimated_cost:
                lines.append(f"- Estimated Parts Cost: ${result.estimated_cost:.2f}")
            lines.append("")
        
        if result.tsb_references:
            lines.append("### Related TSBs")
            for tsb in result.tsb_references:
                lines.append(f"- {tsb}")
        
        return "\n".join(lines)
