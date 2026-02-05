"""
Failure modes for automotive components.

DEPRECATED: This file now re-exports from the refactored modules.
Direct imports from this file are supported for backward compatibility.

New code should import from:
- addons.predictive_diagnostics.knowledge.base (FailureMode, FailureCategory, etc.)
- addons.predictive_diagnostics.knowledge.registry (FAILURE_REGISTRY, utility functions)
- addons.predictive_diagnostics.knowledge.failures_<system> (individual failure modes)
"""

# Re-export base classes
from .base import (
    FailureMode,
    FailureCategory,
    SymptomSeverity,
    PIDEffect,
    Symptom,
)

# Re-export registry and functions
from .registry import (
    FAILURE_REGISTRY,
    get_failure_modes_for_component,
    get_failure_modes_for_system,
    get_all_failure_modes,
    get_failure_by_id,
    get_failures_for_dtc,
    get_failures_for_symptom,
)

# Re-export all failure modes for backward compatibility
from .failures_body import *
from .failures_brakes import *
from .failures_charging import *
from .failures_communication import *
from .failures_cooling import *
from .failures_drivetrain import *
from .failures_electrical import *
from .failures_emissions import *
from .failures_engine import *
from .failures_exhaust import *
from .failures_fuel import *
from .failures_hvac import *
from .failures_ignition import *
from .failures_intake import *
from .failures_lighting import *
from .failures_safety import *
from .failures_starting import *
from .failures_steering import *
from .failures_suspension import *
from .failures_tpms import *
from .failures_transmission import *
from .failures_turbo import *
from .failures_ev import *
from .failures_phev import *
from .failures_tesla import *