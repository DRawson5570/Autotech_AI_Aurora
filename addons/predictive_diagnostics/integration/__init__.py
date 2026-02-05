"""
Integration Module - Phase 5

Unified diagnostic API tying all modules together:
- Knowledge encoding (systems, components, failures)
- Physics simulation (sensor generation)
- ML model (pattern recognition)
- Diagnostic reasoning (Bayesian inference)

Main entry point: DiagnosticEngine
"""

from .api import DiagnosticEngine, DiagnosticResult, SensorReading

__all__ = [
    'DiagnosticEngine',
    'DiagnosticResult', 
    'SensorReading',
]
