"""
Training Data Collection Module

Collects diagnostic conversations for fine-tuning automotive AI models.
"""

from .collector import (
    TrainingDataCollector,
    TrainingExample,
    VehicleContext,
    ScanToolData,
    DataCategory,
    get_collector,
    collect_training_example,
    export_training_data,
)

__all__ = [
    "TrainingDataCollector",
    "TrainingExample", 
    "VehicleContext",
    "ScanToolData",
    "DataCategory",
    "get_collector",
    "collect_training_example",
    "export_training_data",
]
