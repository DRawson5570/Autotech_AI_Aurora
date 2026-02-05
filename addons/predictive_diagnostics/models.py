"""
Data models for the Predictive Diagnostics system.
Pydantic models for type safety and validation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


# =============================================================================
# Enums
# =============================================================================

class ComponentType(str, Enum):
    """Types of automotive components."""
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    RELAY = "relay"
    FUSE = "fuse"
    MOTOR = "motor"
    PUMP = "pump"
    VALVE = "valve"
    CONNECTOR = "connector"
    WIRING = "wiring"
    ECU = "ecu"
    BEARING = "bearing"
    SEAL = "seal"
    SWITCH = "switch"
    CAPACITOR = "capacitor"
    RESISTOR = "resistor"
    COIL = "coil"


class SignalType(str, Enum):
    """Types of observable signals."""
    VOLTAGE = "voltage"
    CURRENT = "current"
    RESISTANCE = "resistance"
    FREQUENCY = "frequency"
    DUTY_CYCLE = "duty_cycle"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    FLOW_RATE = "flow_rate"
    POSITION = "position"
    SPEED = "speed"
    DTC = "dtc"
    PID = "pid"


class SignalPattern(str, Enum):
    """Patterns observed in signals."""
    CONSTANT_MINIMUM = "constant_minimum"
    CONSTANT_MAXIMUM = "constant_maximum"
    ZERO = "zero"
    ERRATIC = "erratic"
    SLOW_RESPONSE = "slow_response"
    NO_RESPONSE = "no_response"
    INVERTED = "inverted"
    ELEVATED = "elevated"
    DEPRESSED = "depressed"
    RISING = "rising"
    FALLING = "falling"
    OSCILLATING = "oscillating"
    INTERMITTENT = "intermittent"
    NORMAL = "normal"


class Severity(str, Enum):
    """Severity levels for failures."""
    CRITICAL = "critical"      # Safety issue or imminent breakdown
    HIGH = "high"              # Significant performance impact
    MEDIUM = "medium"          # Noticeable but driveable
    LOW = "low"                # Minor issue
    INFO = "info"              # For monitoring only


# =============================================================================
# Vehicle and Scanner Data Models
# =============================================================================

class Vehicle(BaseModel):
    """Vehicle identification."""
    year: int
    make: str
    model: str
    engine: Optional[str] = None
    vin: Optional[str] = None
    mileage: Optional[int] = None
    
    def __str__(self) -> str:
        engine_str = f" {self.engine}" if self.engine else ""
        return f"{self.year} {self.make} {self.model}{engine_str}"


class PIDReading(BaseModel):
    """A single PID reading from scanner."""
    pid: str                   # e.g., "0x0C" or "ENGINE_RPM"
    name: str                  # Human-readable name
    value: float               # Numeric value
    unit: str                  # e.g., "RPM", "°C", "kPa"
    timestamp: datetime = Field(default_factory=datetime.now)
    raw_value: Optional[bytes] = None
    
    
class DTCCode(BaseModel):
    """A diagnostic trouble code."""
    code: str                  # e.g., "P0300"
    description: str           # e.g., "Random/Multiple Cylinder Misfire Detected"
    status: str = "active"     # active, pending, history
    freeze_frame: Optional[Dict[str, Any]] = None


class WaveformData(BaseModel):
    """Oscilloscope or lab scope waveform data."""
    signal_name: str
    samples: List[float]
    sample_rate_hz: float
    time_base_ms: float
    voltage_scale: float
    trigger_point: Optional[int] = None


class ScannerData(BaseModel):
    """Complete scanner data snapshot - RUNTIME INPUT."""
    vehicle: Vehicle
    pids: List[PIDReading] = []
    dtcs: List[DTCCode] = []
    waveforms: List[WaveformData] = []
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def get_pid(self, name: str) -> Optional[PIDReading]:
        """Get PID by name."""
        for pid in self.pids:
            if pid.name.lower() == name.lower() or pid.pid.lower() == name.lower():
                return pid
        return None
    
    def has_dtc(self, code: str) -> bool:
        """Check if DTC is present."""
        return any(d.code.upper() == code.upper() for d in self.dtcs)


# =============================================================================
# Failure and Fault Models
# =============================================================================

class FailureMode(BaseModel):
    """A specific way a component can fail."""
    id: str                    # Unique identifier, e.g., "sensor_stuck_low"
    name: str                  # Human-readable name
    description: str           # What happens physically
    component_types: List[ComponentType]  # Which components can fail this way
    severity: Severity = Severity.MEDIUM
    common_causes: List[str] = []
    
    
class SignatureMatch(BaseModel):
    """A signal pattern that indicates a failure mode."""
    signal_type: SignalType
    signal_name: str           # Specific signal, e.g., "coolant_temp_sensor"
    expected_pattern: SignalPattern
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    unit: Optional[str] = None


class FailureSignature(BaseModel):
    """Complete signature for identifying a failure mode."""
    failure_mode_id: str
    primary_signals: List[SignatureMatch]
    secondary_signals: List[SignatureMatch] = []
    associated_dtcs: List[str] = []
    diagnostic_test: str       # How to confirm this failure
    

class FaultNode(BaseModel):
    """A node in the fault tree."""
    id: str
    component: str             # e.g., "Coolant Pump M12"
    component_type: ComponentType
    failure_mode: str          # e.g., "motor_open_winding"
    description: str
    prior_probability: float = 0.05  # Base probability
    tsb_reference: Optional[str] = None
    tsb_boost: float = 1.0     # Multiplier if TSB exists (e.g., 3.0)
    signal_signatures: Dict[str, Any] = {}
    diagnostic_test: str
    repair_action: str
    estimated_repair_time: Optional[float] = None  # Hours
    estimated_parts_cost: Optional[float] = None   # USD
    children: List["FaultNode"] = []  # Sub-faults (AND/OR tree)
    

class FaultTree(BaseModel):
    """Complete fault tree for a vehicle system."""
    vehicle: Vehicle
    system: str                # e.g., "Cooling System"
    created_at: datetime = Field(default_factory=datetime.now)
    source: str = "generated" # "generated", "cached", "manual"
    nodes: List[FaultNode] = []
    
    def get_node(self, node_id: str) -> Optional[FaultNode]:
        """Find a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None


# =============================================================================
# Diagnostic Models
# =============================================================================

class DiagnosticHypothesis(BaseModel):
    """A potential diagnosis with probability."""
    fault_node_id: str
    component: str
    failure_mode: str
    probability: float         # 0.0 to 1.0
    confidence: float          # How confident we are in the probability
    supporting_evidence: List[str] = []
    contradicting_evidence: List[str] = []
    

class DiagnosticTest(BaseModel):
    """A recommended diagnostic test."""
    name: str
    description: str
    procedure: str
    expected_result_if_faulty: str
    expected_result_if_good: str
    tools_required: List[str] = []
    difficulty: str = "medium"  # easy, medium, hard
    time_estimate_minutes: int = 15
    discriminates_between: List[str] = []  # Fault node IDs this test helps distinguish


class DiagnosticResult(BaseModel):
    """Complete diagnostic result - RUNTIME OUTPUT."""
    vehicle: Vehicle
    symptoms_analyzed: List[str]
    hypotheses: List[DiagnosticHypothesis]
    recommended_tests: List[DiagnosticTest]
    most_likely_fault: Optional[DiagnosticHypothesis] = None
    repair_plan: Optional[str] = None
    estimated_repair_time: Optional[float] = None
    estimated_cost: Optional[float] = None
    tsb_references: List[str] = []
    confidence_level: str = "medium"  # low, medium, high
    timestamp: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Training Models
# =============================================================================

class TrainingExample(BaseModel):
    """A single training example for the classifier."""
    id: str
    vehicle: Vehicle
    scanner_data: ScannerData
    correct_diagnosis: str     # Fault node ID
    source: str                # "synthetic", "real", "tsb"
    

class GeneticRule(BaseModel):
    """A diagnostic rule discovered by GA."""
    id: str
    conditions: List[Dict[str, Any]]  # [(pid, operator, threshold), ...]
    diagnosis: str             # Fault node ID
    fitness: float             # How good is this rule
    coverage: float            # What % of cases does it cover
    precision: float           # When it fires, how often is it right
    generation: int            # Which GA generation created it


# Forward reference resolution
FaultNode.model_rebuild()
