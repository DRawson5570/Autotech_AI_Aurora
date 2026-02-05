"""
Physics-based simulation module for predictive diagnostics.

This module generates realistic failure progressions by simulating
how automotive systems behave when components fail.

Key capabilities:
- Time-series generation showing failure evolution
- Multiple operating conditions (idle, cruise, load)
- Compound failures (multiple things wrong)
- Realistic noise and variation
"""

from .engine import SimulationEngine, SimulationConfig, SimulationResult
from .thermal import ThermalModel, CoolingSystemSimulator
from .data_generator import (
    TrainingDataGenerator, 
    DataGeneratorConfig,
    generate_cooling_dataset,
    visualize_simulation,
)

__all__ = [
    'SimulationEngine',
    'SimulationConfig',
    'SimulationResult',
    'ThermalModel',
    'CoolingSystemSimulator',
    'TrainingDataGenerator',
    'DataGeneratorConfig',
    'generate_cooling_dataset',
    'visualize_simulation',
]
