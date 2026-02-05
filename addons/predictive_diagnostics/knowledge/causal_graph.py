"""
Causal graph for diagnostic reasoning.

The causal graph compiles all knowledge from systems, components, and failures
into a queryable structure that supports:
1. Forward reasoning: failure → symptoms
2. Backward reasoning: symptoms → probable failures
3. Discriminating test selection

This is the key data structure for diagnostic inference.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

from .systems import SystemModel, get_system, get_all_systems
from .components import ComponentModel, get_components_for_system
from .failures import (
    FailureMode, get_failure_modes_for_system, get_all_failure_modes,
    get_failure_modes_for_component, get_failures_for_dtc
)


@dataclass
class CausalEdge:
    """
    An edge in the causal graph from failure to symptom.
    
    Encodes: "Failure X causes symptom Y with strength Z under conditions C"
    """
    failure_id: str
    symptom_id: str
    strength: float  # 0-1, how strongly failure causes symptom
    conditions: str = ""  # When this relationship holds
    bidirectional_strength: float = 0.5  # How strongly symptom suggests failure (for backward reasoning)


@dataclass
class SymptomNode:
    """
    A node representing an observable symptom.
    
    Symptoms can be:
    - PID readings (coolant_temp > 220)
    - DTCs (P0128)
    - Physical observations (steam from hood)
    """
    id: str
    name: str
    symptom_type: str  # "pid", "dtc", "observation"
    description: str = ""
    
    # For PID symptoms
    pid_name: Optional[str] = None
    condition: Optional[str] = None  # "high", "low", "erratic"
    threshold: Optional[str] = None  # ">220°F"


@dataclass
class FailureNode:
    """
    A node representing a possible failure.
    """
    id: str
    name: str
    system_id: str
    component_id: str
    
    # Prior probability (how common is this failure?)
    prior_probability: float = 0.1
    
    # Link to full failure mode details
    failure_mode: Optional[FailureMode] = None


class CausalGraph:
    """
    Graph connecting failures to observable symptoms.
    
    Supports:
    1. Forward inference: given failure, what symptoms?
    2. Backward inference: given symptoms, what failures?
    3. Discriminating test selection
    """
    
    def __init__(self):
        # Nodes
        self.failure_nodes: Dict[str, FailureNode] = {}
        self.symptom_nodes: Dict[str, SymptomNode] = {}
        
        # Edges (failure_id, symptom_id) → CausalEdge
        self.edges: Dict[Tuple[str, str], CausalEdge] = {}
        
        # Indexes for fast lookup
        self._symptoms_by_failure: Dict[str, Set[str]] = defaultdict(set)
        self._failures_by_symptom: Dict[str, Set[str]] = defaultdict(set)
        self._failures_by_dtc: Dict[str, Set[str]] = defaultdict(set)
        self._failures_by_system: Dict[str, Set[str]] = defaultdict(set)
    
    def add_failure_node(self, failure: FailureMode) -> FailureNode:
        """Add a failure node from a FailureMode."""
        node = FailureNode(
            id=failure.id,
            name=failure.name,
            system_id=failure.system_id,
            component_id=failure.component_id,
            prior_probability=failure.relative_frequency * 0.2,  # Scale to reasonable prior
            failure_mode=failure,
        )
        self.failure_nodes[failure.id] = node
        self._failures_by_system[failure.system_id].add(failure.id)
        return node
    
    def add_symptom_node(self, symptom: SymptomNode) -> None:
        """Add a symptom node."""
        self.symptom_nodes[symptom.id] = symptom
    
    def add_edge(self, failure_id: str, symptom_id: str, strength: float = 0.8,
                 bidirectional_strength: float = 0.5, conditions: str = "") -> None:
        """Add a causal edge from failure to symptom."""
        edge = CausalEdge(
            failure_id=failure_id,
            symptom_id=symptom_id,
            strength=strength,
            bidirectional_strength=bidirectional_strength,
            conditions=conditions,
        )
        self.edges[(failure_id, symptom_id)] = edge
        self._symptoms_by_failure[failure_id].add(symptom_id)
        self._failures_by_symptom[symptom_id].add(failure_id)
    
    def compile_from_failures(self, failures: List[FailureMode]) -> None:
        """
        Build graph from failure mode definitions.
        
        Extracts symptoms from each failure mode and creates nodes/edges.
        """
        for failure in failures:
            # Add failure node
            self.add_failure_node(failure)
            
            # Extract and add DTC symptoms
            for dtc in failure.expected_dtcs:
                symptom_id = f"dtc_{dtc}"
                if symptom_id not in self.symptom_nodes:
                    self.add_symptom_node(SymptomNode(
                        id=symptom_id,
                        name=f"DTC {dtc}",
                        symptom_type="dtc",
                        description=f"Diagnostic trouble code {dtc}",
                    ))
                self.add_edge(failure.id, symptom_id, strength=0.9, bidirectional_strength=0.7)
                self._failures_by_dtc[dtc].add(failure.id)
            
            # Extract and add PID symptoms
            for pid_effect in failure.pid_effects:
                symptom_id = f"pid_{pid_effect.pid_name}_{pid_effect.effect}"
                if symptom_id not in self.symptom_nodes:
                    self.add_symptom_node(SymptomNode(
                        id=symptom_id,
                        name=f"{pid_effect.pid_name} {pid_effect.effect}",
                        symptom_type="pid",
                        description=pid_effect.description,
                        pid_name=pid_effect.pid_name,
                        condition=pid_effect.effect,
                        threshold=pid_effect.typical_value,
                    ))
                self.add_edge(failure.id, symptom_id, strength=0.8, bidirectional_strength=0.5)
            
            # Extract and add observation symptoms
            for symptom in failure.symptoms:
                # Create ID from description
                symptom_id = f"obs_{symptom.description.lower().replace(' ', '_')[:40]}"
                if symptom_id not in self.symptom_nodes:
                    self.add_symptom_node(SymptomNode(
                        id=symptom_id,
                        name=symptom.description,
                        symptom_type="observation",
                        description=symptom.conditions,
                    ))
                # Strength based on severity
                strength_map = {"subtle": 0.5, "moderate": 0.7, "obvious": 0.85, "severe": 0.95}
                strength = strength_map.get(symptom.severity.value, 0.7)
                self.add_edge(failure.id, symptom_id, strength=strength, bidirectional_strength=0.4)
    
    # ==========================================================================
    # FORWARD REASONING: Failure → Symptoms
    # ==========================================================================
    
    def get_symptoms_for_failure(self, failure_id: str) -> List[Tuple[str, float]]:
        """
        Given a failure, return expected symptoms with probabilities.
        
        Returns: List of (symptom_id, probability) sorted by probability descending
        """
        symptom_ids = self._symptoms_by_failure.get(failure_id, set())
        results = []
        for symptom_id in symptom_ids:
            edge = self.edges.get((failure_id, symptom_id))
            if edge:
                results.append((symptom_id, edge.strength))
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def describe_failure_manifestation(self, failure_id: str) -> str:
        """
        Human-readable description of how a failure manifests.
        """
        failure_node = self.failure_nodes.get(failure_id)
        if not failure_node:
            return f"Unknown failure: {failure_id}"
        
        lines = [f"## {failure_node.name}"]
        
        if failure_node.failure_mode:
            fm = failure_node.failure_mode
            lines.append(f"\n**Immediate Effect:** {fm.immediate_effect}")
            
            if fm.cascade_effects:
                lines.append("\n**Cascade Effects:**")
                for effect in fm.cascade_effects:
                    lines.append(f"  → {effect}")
        
        symptoms = self.get_symptoms_for_failure(failure_id)
        if symptoms:
            lines.append("\n**Observable Symptoms:**")
            for symptom_id, prob in symptoms:
                symptom = self.symptom_nodes.get(symptom_id)
                if symptom:
                    lines.append(f"  - {symptom.name} ({prob*100:.0f}% likely)")
        
        return "\n".join(lines)
    
    # ==========================================================================
    # BACKWARD REASONING: Symptoms → Failures
    # ==========================================================================
    
    def get_failures_for_symptoms(self, symptom_ids: List[str], 
                                   dtcs: Optional[List[str]] = None) -> List[Tuple[str, float]]:
        """
        Given observed symptoms, return probable failures with probabilities.
        
        Uses simple Bayesian-like reasoning:
        - Start with prior probability for each failure
        - Update based on observed symptoms
        - Failures that explain more symptoms get higher scores
        
        Returns: List of (failure_id, probability) sorted by probability descending
        """
        # Collect all candidate failures
        candidate_failures: Set[str] = set()
        
        # Add failures from symptom matches
        for symptom_id in symptom_ids:
            candidate_failures.update(self._failures_by_symptom.get(symptom_id, set()))
        
        # Add failures from DTCs
        if dtcs:
            for dtc in dtcs:
                candidate_failures.update(self._failures_by_dtc.get(dtc, set()))
        
        if not candidate_failures:
            return []
        
        # Score each candidate
        scores: Dict[str, float] = {}
        
        for failure_id in candidate_failures:
            failure_node = self.failure_nodes.get(failure_id)
            if not failure_node:
                continue
            
            # Start with prior
            score = failure_node.prior_probability
            
            # Count how many observed symptoms this failure explains
            explained_symptoms = 0
            total_evidence_strength = 0.0
            
            for symptom_id in symptom_ids:
                edge = self.edges.get((failure_id, symptom_id))
                if edge:
                    explained_symptoms += 1
                    total_evidence_strength += edge.bidirectional_strength
            
            # Add DTCs
            if dtcs and failure_node.failure_mode:
                for dtc in dtcs:
                    if dtc in failure_node.failure_mode.expected_dtcs:
                        explained_symptoms += 1
                        total_evidence_strength += 0.8  # DTCs are strong evidence
            
            # Combine: prior × evidence strength × coverage
            if explained_symptoms > 0:
                coverage = explained_symptoms / max(len(symptom_ids) + (len(dtcs) if dtcs else 0), 1)
                score = score * (1 + total_evidence_strength) * (1 + coverage)
            
            scores[failure_id] = score
        
        # Normalize to probabilities
        total = sum(scores.values())
        if total > 0:
            for failure_id in scores:
                scores[failure_id] /= total
        
        # Sort by score
        results = [(f_id, score) for f_id, score in scores.items()]
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    def get_failures_for_dtc(self, dtc: str) -> List[Tuple[str, float]]:
        """Get failures that can cause a specific DTC."""
        failure_ids = self._failures_by_dtc.get(dtc, set())
        results = []
        for failure_id in failure_ids:
            failure_node = self.failure_nodes.get(failure_id)
            if failure_node:
                results.append((failure_id, failure_node.prior_probability))
        return sorted(results, key=lambda x: x[1], reverse=True)
    
    # ==========================================================================
    # DISCRIMINATING TESTS
    # ==========================================================================
    
    def get_discriminating_test(self, candidate_failures: List[str]) -> Optional[str]:
        """
        Find a test that best distinguishes between candidate failures.
        
        A good discriminating test is one where:
        - One candidate expects a positive result
        - Other candidates expect a negative result
        
        Returns the best test description, or None if no good test found.
        """
        if len(candidate_failures) < 2:
            return None
        
        # Collect all tests from candidates
        test_candidates: Dict[str, List[str]] = defaultdict(list)  # test → [failures that suggest it]
        
        for failure_id in candidate_failures:
            failure_node = self.failure_nodes.get(failure_id)
            if failure_node and failure_node.failure_mode:
                for test in failure_node.failure_mode.discriminating_tests:
                    test_candidates[test].append(failure_id)
        
        # Find tests that discriminate (suggested by some but not all)
        best_test = None
        best_discrimination = 0
        
        for test, suggesting_failures in test_candidates.items():
            # Discrimination score: how many does it separate?
            suggesting = len(suggesting_failures)
            not_suggesting = len(candidate_failures) - suggesting
            discrimination = min(suggesting, not_suggesting)  # Best when equal split
            
            if discrimination > best_discrimination:
                best_discrimination = discrimination
                best_test = test
        
        return best_test
    
    def get_all_discriminating_tests(self, failure_id: str) -> List[str]:
        """Get all discriminating tests for a specific failure."""
        failure_node = self.failure_nodes.get(failure_id)
        if failure_node and failure_node.failure_mode:
            return failure_node.failure_mode.discriminating_tests
        return []
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def get_failure_details(self, failure_id: str) -> Optional[Dict]:
        """Get full details for a failure."""
        failure_node = self.failure_nodes.get(failure_id)
        if not failure_node:
            return None
        
        fm = failure_node.failure_mode
        if not fm:
            return {"id": failure_id, "name": failure_node.name}
        
        return {
            "id": failure_id,
            "name": fm.name,
            "system": fm.system_id,
            "component": fm.component_id,
            "immediate_effect": fm.immediate_effect,
            "cascade_effects": fm.cascade_effects,
            "expected_dtcs": fm.expected_dtcs,
            "symptoms": [s.description for s in fm.symptoms],
            "discriminating_tests": fm.discriminating_tests,
            "repair_actions": fm.repair_actions,
        }
    
    def get_statistics(self) -> Dict:
        """Get graph statistics."""
        return {
            "num_failures": len(self.failure_nodes),
            "num_symptoms": len(self.symptom_nodes),
            "num_edges": len(self.edges),
            "systems": list(self._failures_by_system.keys()),
            "failures_per_system": {
                sys_id: len(failures) 
                for sys_id, failures in self._failures_by_system.items()
            },
        }


# ==============================================================================
# GRAPH BUILDER
# ==============================================================================

def build_causal_graph() -> CausalGraph:
    """
    Build the complete causal graph from all registered knowledge.
    
    This is the main entry point for creating the diagnostic graph.
    """
    graph = CausalGraph()
    
    # Compile from all failure modes
    all_failures = get_all_failure_modes()
    graph.compile_from_failures(all_failures)
    
    return graph


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

_GRAPH_INSTANCE: Optional[CausalGraph] = None


def get_causal_graph() -> CausalGraph:
    """Get the singleton causal graph instance."""
    global _GRAPH_INSTANCE
    if _GRAPH_INSTANCE is None:
        _GRAPH_INSTANCE = build_causal_graph()
    return _GRAPH_INSTANCE


def reset_causal_graph() -> None:
    """Reset the singleton (for testing)."""
    global _GRAPH_INSTANCE
    _GRAPH_INSTANCE = None
