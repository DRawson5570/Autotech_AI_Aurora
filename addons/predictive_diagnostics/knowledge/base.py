"""
Base classes for failure mode knowledge.

This module contains the core data structures used to define failure modes:
- FailureCategory: Types of failures (stuck, leak, electrical, etc.)
- SymptomSeverity: How obvious symptoms are
- PIDEffect: How failures affect PID readings
- Symptom: Observable symptoms
- FailureMode: Complete failure definition
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class FailureCategory(Enum):
    """High-level categories of failure modes."""
    STUCK = "stuck"           # Component stuck in one position
    LEAK = "leak"             # Fluid/air escaping
    BLOCKAGE = "blockage"     # Flow restriction
    ELECTRICAL = "electrical" # Electrical fault
    MECHANICAL = "mechanical" # Mechanical wear/damage
    DRIFT = "drift"           # Gradual deviation from spec
    THERMAL = "thermal"       # Thermal fault / over-temperature
    INTERMITTENT = "intermittent"  # Comes and goes


class SymptomSeverity(Enum):
    """How obvious/severe the symptom is."""
    SUBTLE = "subtle"       # Hard to notice without instruments
    MODERATE = "moderate"   # Noticeable to attentive driver
    OBVIOUS = "obvious"     # Very noticeable
    SEVERE = "severe"       # Undriveable condition


@dataclass
class PIDEffect:
    """How a failure affects a PID reading."""
    pid_name: str
    effect: str  # "high", "low", "erratic", "stuck", "slow_response"
    typical_value: Optional[str] = None  # e.g., ">230°F" or "<10%"
    description: str = ""


@dataclass
class Symptom:
    """An observable symptom of a failure."""
    description: str
    severity: SymptomSeverity
    conditions: str = ""  # When symptom appears (e.g., "at idle", "under load")


@dataclass
class FailureMode:
    """
    A specific way a component can fail.
    
    This is the core of the causal knowledge - it encodes:
    1. WHAT happens (immediate_effect)
    2. WHY it matters (cascade_effects)
    3. WHAT we observe (pid_effects, symptoms, expected_dtcs)
    4. HOW to confirm (discriminating_tests)
    5. WHAT to do (repair_actions)
    """
    
    id: str
    name: str
    category: FailureCategory
    
    # Which component this applies to
    component_id: str
    system_id: str
    
    # Causal chain (physics-based reasoning)
    immediate_effect: str  # What happens first
    cascade_effects: List[str] = field(default_factory=list)  # Chain of consequences
    
    # Observable evidence
    pid_effects: List[PIDEffect] = field(default_factory=list)
    expected_dtcs: List[str] = field(default_factory=list)
    symptoms: List[Symptom] = field(default_factory=list)
    
    # Diagnostic
    discriminating_tests: List[str] = field(default_factory=list)
    
    # Repair
    repair_actions: List[str] = field(default_factory=list)
    repair_time_hours: Optional[float] = None  # Labor time estimate
    parts_cost_low: Optional[float] = None     # Parts cost range low ($)
    parts_cost_high: Optional[float] = None    # Parts cost range high ($)
    labor_rate_default: float = 120.0          # Default shop labor rate $/hr
    
    # Probability/prevalence (if known)
    relative_frequency: float = 0.5  # 0-1, higher = more common

    # Provenance / OEM-specific signals
    expected_alerts: List[str] = field(default_factory=list)  # OEM proprietary alert names or codes
    references: List[str] = field(default_factory=list)  # URLs or citation strings for sources
    
    def get_repair_estimate(self, labor_rate: float = None) -> Optional[str]:
        """Get formatted repair cost estimate."""
        if self.repair_time_hours is None:
            return None
        rate = labor_rate or self.labor_rate_default
        labor_cost = self.repair_time_hours * rate
        if self.parts_cost_low and self.parts_cost_high:
            total_low = labor_cost + self.parts_cost_low
            total_high = labor_cost + self.parts_cost_high
            return f"${total_low:.0f}-${total_high:.0f} ({self.repair_time_hours:.1f} hr labor + ${self.parts_cost_low:.0f}-${self.parts_cost_high:.0f} parts)"
        elif self.parts_cost_low:
            total = labor_cost + self.parts_cost_low
            return f"~${total:.0f} ({self.repair_time_hours:.1f} hr labor + ~${self.parts_cost_low:.0f} parts)"
        else:
            return f"~${labor_cost:.0f} labor ({self.repair_time_hours:.1f} hr)"
