"""
Machine Learning module for predictive diagnostics.

This module trains on simulated failure data to learn the mapping
from sensor observations to failure probabilities.

Key components:
- DiagnosticModel: Neural network for failure classification
- ModelTrainer: Training pipeline with data loading
- DiagnosticInference: Runtime inference with uncertainty
"""

from .model import DiagnosticModel, SimpleDiagnosticModel, ModelConfig
from .trainer import ModelTrainer, TrainingConfig
from .inference import DiagnosticInference, DiagnosticResult

__all__ = [
    'DiagnosticModel',
    'SimpleDiagnosticModel',
    'ModelConfig',
    'ModelTrainer',
    'TrainingConfig',
    'DiagnosticInference',
    'DiagnosticResult',
]
