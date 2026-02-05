"""
Knowledge encoding module for predictive diagnostics.

This module encodes automotive physics as computable models,
enabling causal reasoning about failures and symptoms.
"""

from .systems import SystemModel, CoolingSystem
from .components import ComponentModel, ComponentType
from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect
from .causal_graph import CausalGraph

# Import registry functions and FAILURE_REGISTRY for backward compatibility
from .registry import (
    FAILURE_REGISTRY,
    get_failure_modes_for_component,
    get_failure_modes_for_system,
    get_all_failure_modes,
    get_failure_by_id,
    get_failures_for_dtc,
    get_failures_for_symptom,
)

__all__ = [
    'SystemModel',
    'CoolingSystem',
    'ComponentModel',
    'ComponentType',
    'FailureMode',
    'FailureCategory',
    'Symptom',
    'SymptomSeverity',
    'PIDEffect',
    'CausalGraph',
    'FAILURE_REGISTRY',
    'get_failure_modes_for_component',
    'get_failure_modes_for_system',
    'get_all_failure_modes',
    'get_failure_by_id',
    'get_failures_for_dtc',
    'get_failures_for_symptom',
]
