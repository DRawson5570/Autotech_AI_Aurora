"""
Diagnostic reasoning module.

Combines ML predictions with causal knowledge to:
- Update beliefs as new evidence arrives (Bayesian)
- Recommend discriminating tests
- Explain diagnostic conclusions
- Handle compound/multiple failures
"""

from .bayesian import BayesianReasoner, BeliefState
from .diagnostician import Diagnostician, DiagnosticSession, DiagnosticConclusion, quick_diagnose

__all__ = [
    'BayesianReasoner',
    'BeliefState',
    'Diagnostician',
    'DiagnosticSession',
    'DiagnosticConclusion',
    'quick_diagnose',
]
