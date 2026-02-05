"""
Predictive Diagnostics Module for Autotech AI

This module provides AI-powered automotive diagnostic capabilities using:
- Random Forest classifiers for PID-based fault classification
- Genetic Algorithms for automated failure mode discovery
- Fault trees generated from first principles + empirical data

Architecture:
- TRAINING PHASE: Uses Mitchell data + textbooks to learn patterns
- RUNTIME: Accepts scanner data (PIDs, DTCs, waveforms) → produces diagnosis
- NO Mitchell queries at runtime - fully pre-trained model

Components:
- models.py: Pydantic data models for all system components
- taxonomy.py: Universal component failure modes database
- signatures.py: Maps failures to observable signal patterns
- fault_tree.py: Fault tree data structures and generation
- classifier.py: Random Forest ensemble for fault classification
- genetic.py: GA for automated diagnostic rule discovery
- synthetic_data.py: Generate training data from fault trees
- training.py: End-to-end training pipeline
- reasoner.py: Runtime diagnostic reasoning engine
- extractor.py: Mitchell data extraction for training phase
- openwebui_tool.py: Open WebUI integration

Usage:
    # Training phase (done offline)
    from addons.predictive_diagnostics import TrainingPipeline
    pipeline = TrainingPipeline()
    result = await pipeline.train(extraction_result)
    
    # Runtime diagnosis
    from addons.predictive_diagnostics import DiagnosticReasoner
    reasoner = DiagnosticReasoner()
    reasoner.load_models("path/to/models")
    diagnosis = reasoner.diagnose(scanner_data, symptoms)
"""

__version__ = "0.1.0"

# Core data models
from .models import (
    Vehicle,
    ScannerData,
    PIDReading,
    DTCCode,
    FaultNode as FaultNodeModel,
    FaultTree as FaultTreeModel,
    DiagnosticResult,
    DiagnosticHypothesis,
    DiagnosticTest,
    TrainingExample,
    GeneticRule,
)

# Taxonomy and signatures
from .taxonomy import ComponentType, FailureMode, FAILURE_TAXONOMY
from .signatures import SignalPattern, FailureSignature, FAILURE_SIGNATURES

# Fault tree generation
from .fault_tree import FaultNode, FaultTree, FaultTreeGenerator, FaultTreeCache

# ML classifiers
from .classifier import DiagnosticClassifier, EnsembleClassifier, COMMON_PID_FEATURES

# Genetic algorithm
from .genetic import GeneticRuleDiscovery, DiagnosticRule, Condition, Operator

# Data generation
from .synthetic_data import SyntheticDataGenerator, SystemProfile

# Training
from .training import TrainingPipeline, TrainingConfig, TrainingResult, ModelManager

# Runtime inference
from .reasoner import DiagnosticReasoner, SymptomReport

# Data extraction
from .extractor import MitchellDataExtractor, ExtractionResult, ExtractedComponent, ExtractedTSB

# PID specifications and deviation detection
from .pid_specs import (
    PIDCategory,
    PIDSpec,
    STANDARD_PIDS,
    DerivedMetric,
    DERIVED_METRICS,
    VehicleSpecs,
    get_vehicle_specs,
    Deviation,
    detect_deviations,
)

__all__ = [
    # Version
    "__version__",
    
    # Models
    "Vehicle",
    "ScannerData", 
    "PIDReading",
    "DTCCode",
    "FaultNodeModel",
    "FaultTreeModel",
    "DiagnosticResult",
    "DiagnosticHypothesis",
    "DiagnosticTest",
    "TrainingExample",
    "GeneticRule",
    
    # Taxonomy
    "ComponentType",
    "FailureMode",
    "FAILURE_TAXONOMY",
    
    # Signatures
    "SignalPattern",
    "FailureSignature",
    "FAILURE_SIGNATURES",
    
    # Fault trees
    "FaultNode",
    "FaultTree",
    "FaultTreeGenerator",
    "FaultTreeCache",
    
    # Classifiers
    "DiagnosticClassifier",
    "EnsembleClassifier",
    "COMMON_PID_FEATURES",
    
    # Genetic algorithm
    "GeneticRuleDiscovery",
    "DiagnosticRule",
    "Condition",
    "Operator",
    
    # Data generation
    "SyntheticDataGenerator",
    "SystemProfile",
    
    # Training
    "TrainingPipeline",
    "TrainingConfig",
    "TrainingResult",
    "ModelManager",
    
    # Reasoner
    "DiagnosticReasoner",
    "SymptomReport",
    
    # Extraction
    "MitchellDataExtractor",
    "ExtractionResult",
    "ExtractedComponent",
    "ExtractedTSB",
    
    # PID Specs
    "PIDCategory",
    "PIDSpec",
    "STANDARD_PIDS",
    "DerivedMetric",
    "DERIVED_METRICS",
    "VehicleSpecs",
    "get_vehicle_specs",
    "Deviation",
    "detect_deviations",
]
