"""
Core simulation engine for physics-based failure modeling.

The simulation engine:
1. Takes a system model + failure mode
2. Simulates time evolution of state variables
3. Generates time-series data for training ML model

This is NOT a full physics simulator - it's a simplified model that
captures the CAUSAL STRUCTURE of how failures manifest over time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import random
import math


class OperatingCondition(Enum):
    """Vehicle operating conditions that affect system behavior."""
    COLD_START = "cold_start"      # Engine just started, everything cold
    IDLE = "idle"                  # Engine running, vehicle stationary
    CITY_DRIVING = "city_driving"  # Stop-and-go, low-medium load
    HIGHWAY = "highway"            # Steady high speed
    HEAVY_LOAD = "heavy_load"      # Towing, climbing, aggressive driving
    HOT_AMBIENT = "hot_ambient"    # High ambient temperature


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    
    # Time settings
    duration_seconds: float = 300.0  # 5 minutes default
    time_step: float = 1.0           # 1 second steps
    
    # Operating condition
    operating_condition: OperatingCondition = OperatingCondition.IDLE
    
    # Initial conditions
    initial_state: Dict[str, float] = field(default_factory=dict)
    
    # Environment
    ambient_temp_c: float = 25.0     # Ambient temperature
    
    # Noise settings
    add_noise: bool = True
    noise_level: float = 0.02        # 2% noise
    
    # Failure settings
    failure_id: Optional[str] = None
    failure_severity: float = 1.0    # 0-1, partial failures possible
    failure_onset_time: float = 0.0  # When failure begins (for progressive)


@dataclass
class TimeSeriesPoint:
    """A single point in a time series."""
    time: float
    values: Dict[str, float]
    
    def get(self, key: str, default: float = 0.0) -> float:
        return self.values.get(key, default)


@dataclass
class SimulationResult:
    """Results from a simulation run."""
    
    config: SimulationConfig
    time_series: List[TimeSeriesPoint]
    
    # Summary statistics
    final_state: Dict[str, float] = field(default_factory=dict)
    triggered_dtcs: List[str] = field(default_factory=list)
    
    # Labels for ML training
    failure_id: Optional[str] = None
    system_id: Optional[str] = None
    
    def get_variable_series(self, variable: str) -> List[float]:
        """Extract a single variable's time series."""
        return [point.get(variable) for point in self.time_series]
    
    def get_times(self) -> List[float]:
        """Get time values."""
        return [point.time for point in self.time_series]
    
    def to_training_sample(self) -> Dict[str, Any]:
        """Convert to format suitable for ML training."""
        return {
            "time_series": {
                var: self.get_variable_series(var)
                for var in self.time_series[0].values.keys()
            } if self.time_series else {},
            "times": self.get_times(),
            "final_state": self.final_state,
            "dtcs": self.triggered_dtcs,
            "failure_id": self.failure_id,
            "system_id": self.system_id,
            "operating_condition": self.config.operating_condition.value,
            "ambient_temp": self.config.ambient_temp_c,
        }


class SimulationEngine:
    """
    Core simulation engine.
    
    Runs time-stepped simulations of automotive systems with failures.
    """
    
    def __init__(self):
        # Registry of system simulators
        self._simulators: Dict[str, 'SystemSimulator'] = {}
    
    def register_simulator(self, system_id: str, simulator: 'SystemSimulator') -> None:
        """Register a simulator for a system."""
        self._simulators[system_id] = simulator
    
    def get_simulator(self, system_id: str) -> Optional['SystemSimulator']:
        """Get simulator for a system."""
        return self._simulators.get(system_id)
    
    def run(self, system_id: str, config: SimulationConfig) -> SimulationResult:
        """
        Run a simulation.
        
        Args:
            system_id: Which system to simulate
            config: Simulation configuration
            
        Returns:
            SimulationResult with time series data
        """
        simulator = self.get_simulator(system_id)
        if not simulator:
            raise ValueError(f"No simulator registered for system: {system_id}")
        
        return simulator.simulate(config)


class SystemSimulator:
    """
    Base class for system-specific simulators.
    
    Subclasses implement the physics for specific systems.
    """
    
    def __init__(self, system_id: str):
        self.system_id = system_id
        
        # State variables and their initial values
        self.state_variables: Dict[str, float] = {}
        
        # DTC thresholds: (variable, condition, threshold, dtc)
        self.dtc_thresholds: List[tuple] = []
    
    def initialize_state(self, config: SimulationConfig) -> Dict[str, float]:
        """Initialize state from config or defaults."""
        state = self.state_variables.copy()
        state.update(config.initial_state)
        return state
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """
        Advance simulation by one time step.
        
        Override in subclasses to implement system physics.
        
        Args:
            state: Current state variables
            dt: Time step in seconds
            config: Simulation config (for operating condition, failure, etc.)
            
        Returns:
            Updated state variables
        """
        raise NotImplementedError("Subclass must implement step()")
    
    def apply_failure(self, state: Dict[str, float], failure_id: str, 
                      severity: float, config: SimulationConfig) -> Dict[str, float]:
        """
        Apply failure effects to state.
        
        Override in subclasses to implement failure effects.
        """
        return state
    
    def add_noise(self, state: Dict[str, float], noise_level: float) -> Dict[str, float]:
        """Add realistic measurement noise to state."""
        noisy_state = {}
        for var, value in state.items():
            noise = random.gauss(0, noise_level * abs(value) + 0.1)
            noisy_state[var] = value + noise
        return noisy_state
    
    def check_dtcs(self, state: Dict[str, float]) -> List[str]:
        """Check if any DTC thresholds are exceeded."""
        triggered = []
        for var, condition, threshold, dtc in self.dtc_thresholds:
            value = state.get(var, 0)
            if condition == ">" and value > threshold:
                triggered.append(dtc)
            elif condition == "<" and value < threshold:
                triggered.append(dtc)
            elif condition == "==" and abs(value - threshold) < 0.01:
                triggered.append(dtc)
        return triggered
    
    def simulate(self, config: SimulationConfig) -> SimulationResult:
        """
        Run full simulation with given config.
        """
        # Initialize
        state = self.initialize_state(config)
        time_series = []
        all_dtcs = set()
        
        # Time loop
        t = 0.0
        while t <= config.duration_seconds:
            # Apply failure if active
            if config.failure_id and t >= config.failure_onset_time:
                state = self.apply_failure(
                    state, config.failure_id, config.failure_severity, config
                )
            
            # Physics step
            state = self.step(state, config.time_step, config)
            
            # Add noise if enabled
            if config.add_noise:
                observed_state = self.add_noise(state, config.noise_level)
            else:
                observed_state = state.copy()
            
            # Record
            time_series.append(TimeSeriesPoint(time=t, values=observed_state.copy()))
            
            # Check DTCs
            dtcs = self.check_dtcs(state)
            all_dtcs.update(dtcs)
            
            t += config.time_step
        
        return SimulationResult(
            config=config,
            time_series=time_series,
            final_state=state.copy(),
            triggered_dtcs=list(all_dtcs),
            failure_id=config.failure_id,
            system_id=self.system_id,
        )


# ==============================================================================
# OPERATING CONDITION PARAMETERS
# ==============================================================================

# Heat generation rates by operating condition (relative to baseline)
HEAT_GENERATION_FACTORS = {
    OperatingCondition.COLD_START: 0.3,     # Low heat initially
    OperatingCondition.IDLE: 0.5,           # Low load
    OperatingCondition.CITY_DRIVING: 0.8,   # Medium load
    OperatingCondition.HIGHWAY: 1.0,        # Steady load
    OperatingCondition.HEAVY_LOAD: 1.5,     # High load
    OperatingCondition.HOT_AMBIENT: 1.0,    # Normal heat gen, reduced rejection
}

# Airflow factors (affects radiator cooling)
AIRFLOW_FACTORS = {
    OperatingCondition.COLD_START: 0.0,     # No airflow initially
    OperatingCondition.IDLE: 0.1,           # Minimal airflow
    OperatingCondition.CITY_DRIVING: 0.5,   # Some airflow
    OperatingCondition.HIGHWAY: 1.0,        # Full airflow
    OperatingCondition.HEAVY_LOAD: 0.7,     # May be climbing (less airflow)
    OperatingCondition.HOT_AMBIENT: 0.5,    # Reduced effectiveness
}

# Engine RPM by condition (affects water pump flow)
RPM_BY_CONDITION = {
    OperatingCondition.COLD_START: 1200,    # Fast idle
    OperatingCondition.IDLE: 750,           # Normal idle
    OperatingCondition.CITY_DRIVING: 2000,  # Average
    OperatingCondition.HIGHWAY: 2500,       # Cruise
    OperatingCondition.HEAVY_LOAD: 3500,    # Higher RPM
    OperatingCondition.HOT_AMBIENT: 750,    # Idle in traffic
}


def get_operating_params(condition: OperatingCondition) -> Dict[str, float]:
    """Get simulation parameters for an operating condition."""
    return {
        "heat_generation_factor": HEAT_GENERATION_FACTORS.get(condition, 1.0),
        "airflow_factor": AIRFLOW_FACTORS.get(condition, 0.5),
        "engine_rpm": RPM_BY_CONDITION.get(condition, 2000),
    }
