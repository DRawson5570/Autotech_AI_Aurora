"""
Unified Diagnostic Engine

This module integrates all physics-based system models to provide
comprehensive automotive diagnostics. Given symptoms (DTCs, PIDs, 
customer complaints), it simulates each possible fault and ranks
them by how well they explain the observed symptoms.

This is the "brain" of the predictive diagnostics system.

Architecture:
1. Parse input symptoms (DTCs, abnormal PIDs, complaints)
2. Map symptoms to potentially affected systems
3. For each system, simulate all possible faults
4. Score each fault by symptom match quality
5. Return ranked list of probable causes with confidence scores
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import math

# Import all physics models
from .cooling_system import CoolingSystemModel, CoolingSystemState
from .fuel_system import FuelSystemModel, FuelSystemState
from .ignition_system import IgnitionSystemModel, IgnitionSystemState
from .charging_system import ChargingSystemModel, ChargingSystemState


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SystemType(Enum):
    """Automotive system categories."""
    COOLING = "cooling"
    FUEL = "fuel"
    IGNITION = "ignition"
    CHARGING = "charging"


@dataclass
class Symptom:
    """A single observed symptom."""
    type: str  # "dtc", "pid", "complaint"
    code: str  # DTC code, PID name, or complaint keyword
    value: Optional[float] = None  # For PIDs
    description: str = ""


@dataclass
class DiagnosticCandidate:
    """A potential diagnosis with confidence score."""
    fault_id: str
    system: SystemType
    description: str
    confidence: float  # 0-1
    
    # Evidence
    symptoms_explained: List[str] = field(default_factory=list)
    symptoms_not_explained: List[str] = field(default_factory=list)
    
    # Predicted state if this fault is present
    predicted_state: Optional[Any] = None
    
    # Recommended actions
    verification_tests: List[str] = field(default_factory=list)
    repair_actions: List[str] = field(default_factory=list)
    
    # Additional info
    severity: str = "medium"  # low, medium, high, critical
    estimated_repair_cost: str = ""


@dataclass
class DiagnosticResult:
    """Complete diagnostic result."""
    candidates: List[DiagnosticCandidate]
    input_symptoms: List[Symptom]
    systems_analyzed: List[SystemType]
    
    # Summary
    most_likely_cause: Optional[DiagnosticCandidate] = None
    confidence_in_diagnosis: float = 0.0
    
    # Recommendations
    next_steps: List[str] = field(default_factory=list)


# =============================================================================
# SYMPTOM MAPPINGS
# =============================================================================

# Map DTCs to systems and potential faults
DTC_FAULT_MAP: Dict[str, Dict] = {
    # Cooling system
    "P0115": {"system": SystemType.COOLING, "faults": ["ect_sensor_failed", "wiring"], "desc": "ECT sensor circuit"},
    "P0116": {"system": SystemType.COOLING, "faults": ["ect_sensor_failed", "thermostat_stuck"], "desc": "ECT range/performance"},
    "P0117": {"system": SystemType.COOLING, "faults": ["ect_sensor_failed"], "desc": "ECT low input"},
    "P0118": {"system": SystemType.COOLING, "faults": ["ect_sensor_failed"], "desc": "ECT high input"},
    "P0125": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_open"], "desc": "Insufficient coolant temp"},
    "P0128": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_open"], "desc": "Thermostat rationality"},
    "P0217": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_closed", "radiator_clogged", "fan_failed", "water_pump_failed"], "desc": "Engine overtemp"},
    
    # Fuel system
    "P0171": {"system": SystemType.FUEL, "faults": ["maf_contaminated", "vacuum_leak", "injector_clogged", "fuel_pump_weak"], "desc": "System too lean bank 1"},
    "P0172": {"system": SystemType.FUEL, "faults": ["maf_contaminated", "injector_leaking", "o2_bank1_biased_rich"], "desc": "System too rich bank 1"},
    "P0174": {"system": SystemType.FUEL, "faults": ["maf_contaminated", "vacuum_leak", "injector_clogged"], "desc": "System too lean bank 2"},
    "P0175": {"system": SystemType.FUEL, "faults": ["maf_contaminated", "injector_leaking"], "desc": "System too rich bank 2"},
    "P0101": {"system": SystemType.FUEL, "faults": ["maf_failed", "maf_contaminated"], "desc": "MAF range/performance"},
    "P0102": {"system": SystemType.FUEL, "faults": ["maf_failed"], "desc": "MAF low input"},
    "P0103": {"system": SystemType.FUEL, "faults": ["maf_failed"], "desc": "MAF high input"},
    "P0130": {"system": SystemType.FUEL, "faults": ["o2_bank1_failed"], "desc": "O2 sensor circuit bank 1"},
    "P0133": {"system": SystemType.FUEL, "faults": ["o2_bank1_lazy"], "desc": "O2 slow response bank 1"},
    "P0134": {"system": SystemType.FUEL, "faults": ["o2_bank1_failed"], "desc": "O2 no activity bank 1"},
    "P0190": {"system": SystemType.FUEL, "faults": ["fuel_pump_failed", "fuel_pump_weak"], "desc": "Fuel rail pressure sensor"},
    "P0191": {"system": SystemType.FUEL, "faults": ["fuel_pump_weak"], "desc": "Fuel rail pressure range"},
    "P0230": {"system": SystemType.FUEL, "faults": ["fuel_pump_failed"], "desc": "Fuel pump circuit"},
    
    # Ignition system
    "P0300": {"system": SystemType.IGNITION, "faults": ["all_coils_weak", "all_plugs_fouled", "low_battery_voltage"], "desc": "Random misfire"},
    "P0301": {"system": SystemType.IGNITION, "faults": ["coil_failed", "coil_weak", "plug_fouled", "plug_worn"], "desc": "Cyl 1 misfire", "cylinder": 0},
    "P0302": {"system": SystemType.IGNITION, "faults": ["coil_failed", "coil_weak", "plug_fouled", "plug_worn"], "desc": "Cyl 2 misfire", "cylinder": 1},
    "P0303": {"system": SystemType.IGNITION, "faults": ["coil_failed", "coil_weak", "plug_fouled", "plug_worn"], "desc": "Cyl 3 misfire", "cylinder": 2},
    "P0304": {"system": SystemType.IGNITION, "faults": ["coil_failed", "coil_weak", "plug_fouled", "plug_worn"], "desc": "Cyl 4 misfire", "cylinder": 3},
    "P0351": {"system": SystemType.IGNITION, "faults": ["coil_failed"], "desc": "Ignition coil 1 circuit", "cylinder": 0},
    "P0352": {"system": SystemType.IGNITION, "faults": ["coil_failed"], "desc": "Ignition coil 2 circuit", "cylinder": 1},
    "P0353": {"system": SystemType.IGNITION, "faults": ["coil_failed"], "desc": "Ignition coil 3 circuit", "cylinder": 2},
    "P0354": {"system": SystemType.IGNITION, "faults": ["coil_failed"], "desc": "Ignition coil 4 circuit", "cylinder": 3},
    
    # Charging system
    "P0562": {"system": SystemType.CHARGING, "faults": ["alternator_failed", "battery_weak", "belt_slipping"], "desc": "System voltage low"},
    "P0563": {"system": SystemType.CHARGING, "faults": ["alternator_overcharging"], "desc": "System voltage high"},
    "P0620": {"system": SystemType.CHARGING, "faults": ["alternator_failed"], "desc": "Generator control circuit"},
    "P0621": {"system": SystemType.CHARGING, "faults": ["alternator_failed"], "desc": "Generator lamp circuit"},
}

# Map complaints to systems and faults
COMPLAINT_FAULT_MAP: Dict[str, Dict] = {
    "overheating": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_closed", "radiator_clogged", "fan_failed", "water_pump_failed"]},
    "runs_cold": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_open"]},
    "no_heat": {"system": SystemType.COOLING, "faults": ["thermostat_stuck_open", "low_coolant"]},
    
    "rough_idle": {"system": SystemType.FUEL, "faults": ["vacuum_leak", "injector_clogged", "maf_contaminated"]},
    "hesitation": {"system": SystemType.FUEL, "faults": ["fuel_pump_weak", "maf_contaminated", "injector_clogged"]},
    "poor_fuel_economy": {"system": SystemType.FUEL, "faults": ["o2_bank1_biased_rich", "injector_leaking", "maf_contaminated"]},
    "hard_start": {"system": SystemType.FUEL, "faults": ["fuel_pump_weak", "injector_clogged"]},
    "stalling": {"system": SystemType.FUEL, "faults": ["fuel_pump_failed", "maf_failed"]},
    
    "misfire": {"system": SystemType.IGNITION, "faults": ["coil_weak", "plug_fouled", "plug_worn"]},
    "rough_running": {"system": SystemType.IGNITION, "faults": ["coil_weak", "plug_fouled", "all_coils_weak"]},
    "no_start": {"system": SystemType.IGNITION, "faults": ["coil_failed", "all_coils_weak"]},
    
    "battery_light": {"system": SystemType.CHARGING, "faults": ["alternator_failed", "belt_slipping"]},
    "battery_dead": {"system": SystemType.CHARGING, "faults": ["alternator_failed", "battery_weak", "battery_dead_cell"]},
    "slow_crank": {"system": SystemType.CHARGING, "faults": ["battery_weak", "battery_dead_cell", "high_resistance_connection"]},
    "dim_lights": {"system": SystemType.CHARGING, "faults": ["alternator_failed", "battery_weak"]},
}

# Fault details
FAULT_DETAILS: Dict[str, Dict] = {
    # Cooling
    "thermostat_stuck_closed": {
        "description": "Thermostat stuck closed - coolant cannot flow to radiator",
        "severity": "critical",
        "verification": ["Check coolant temp rises quickly", "Feel upper radiator hose (cold = stuck closed)"],
        "repair": ["Replace thermostat"],
        "cost": "$150-300"
    },
    "thermostat_stuck_open": {
        "description": "Thermostat stuck open - engine never reaches operating temp",
        "severity": "medium",
        "verification": ["Check if temp gauge stays low", "Monitor warmup time"],
        "repair": ["Replace thermostat"],
        "cost": "$150-300"
    },
    "radiator_clogged": {
        "description": "Radiator passages blocked - reduced heat dissipation",
        "severity": "high",
        "verification": ["Check for temp difference across radiator", "Inspect coolant condition"],
        "repair": ["Flush cooling system", "Replace radiator if severe"],
        "cost": "$100-600"
    },
    "fan_failed": {
        "description": "Cooling fan not operating - overheats at idle/low speed",
        "severity": "high",
        "verification": ["Check if fan runs when hot", "Test fan relay and motor"],
        "repair": ["Replace fan motor or relay"],
        "cost": "$200-500"
    },
    "water_pump_failed": {
        "description": "Water pump failed - no coolant circulation",
        "severity": "critical",
        "verification": ["Check for weeping from pump", "Listen for bearing noise"],
        "repair": ["Replace water pump"],
        "cost": "$300-700"
    },
    
    # Fuel
    "maf_contaminated": {
        "description": "MAF sensor contaminated - underreads airflow causing lean condition",
        "severity": "medium",
        "verification": ["Check MAF readings vs spec", "Look for positive fuel trims"],
        "repair": ["Clean MAF sensor", "Replace if cleaning doesn't help"],
        "cost": "$20-300"
    },
    "maf_failed": {
        "description": "MAF sensor failed - ECU has no airflow data",
        "severity": "high",
        "verification": ["Check for MAF voltage/frequency signal", "Monitor live data"],
        "repair": ["Replace MAF sensor"],
        "cost": "$100-300"
    },
    "vacuum_leak": {
        "description": "Vacuum leak - unmetered air causes lean condition",
        "severity": "medium",
        "verification": ["Smoke test intake system", "Listen for hissing at idle"],
        "repair": ["Repair/replace leaking hose or gasket"],
        "cost": "$50-400"
    },
    "fuel_pump_weak": {
        "description": "Fuel pump weakening - pressure drops under load",
        "severity": "high",
        "verification": ["Test fuel pressure at idle and under load", "Check pressure drop on WOT"],
        "repair": ["Replace fuel pump"],
        "cost": "$400-900"
    },
    "fuel_pump_failed": {
        "description": "Fuel pump failed - no fuel delivery",
        "severity": "critical",
        "verification": ["Listen for pump prime", "Test fuel pressure (0 psi)"],
        "repair": ["Replace fuel pump"],
        "cost": "$400-900"
    },
    "injector_clogged": {
        "description": "Fuel injector clogged - lean on affected cylinder",
        "severity": "medium",
        "verification": ["Check balance rates", "Injector flow test"],
        "repair": ["Clean injectors", "Replace if cleaning fails"],
        "cost": "$100-600"
    },
    "injector_leaking": {
        "description": "Fuel injector leaking - rich condition, possible fuel smell",
        "severity": "high",
        "verification": ["Check for fuel smell", "Leak-down test"],
        "repair": ["Replace injector"],
        "cost": "$150-400"
    },
    "o2_bank1_failed": {
        "description": "O2 sensor failed - stuck voltage, ECU goes open loop",
        "severity": "medium",
        "verification": ["Monitor O2 voltage (stuck ~450mV)", "Check switching frequency"],
        "repair": ["Replace O2 sensor"],
        "cost": "$100-300"
    },
    "o2_bank1_lazy": {
        "description": "O2 sensor lazy - slow response affects fuel trim accuracy",
        "severity": "low",
        "verification": ["Check O2 switching frequency (<1Hz = lazy)"],
        "repair": ["Replace O2 sensor"],
        "cost": "$100-300"
    },
    
    # Ignition
    "coil_failed": {
        "description": "Ignition coil failed - no spark on cylinder",
        "severity": "high",
        "verification": ["Swap coil to different cylinder", "Check resistance"],
        "repair": ["Replace ignition coil"],
        "cost": "$50-200"
    },
    "coil_weak": {
        "description": "Ignition coil weak - insufficient spark energy",
        "severity": "medium",
        "verification": ["Check secondary voltage with scope", "Swap test"],
        "repair": ["Replace ignition coil"],
        "cost": "$50-200"
    },
    "plug_fouled": {
        "description": "Spark plug fouled - deposits increasing required voltage",
        "severity": "low",
        "verification": ["Remove and inspect plug", "Check for carbon/oil deposits"],
        "repair": ["Clean or replace spark plug"],
        "cost": "$20-100"
    },
    "plug_worn": {
        "description": "Spark plug worn - increased gap reduces spark reliability",
        "severity": "low",
        "verification": ["Remove and measure gap", "Inspect electrode condition"],
        "repair": ["Replace spark plug"],
        "cost": "$20-100"
    },
    "all_coils_weak": {
        "description": "All coils weak - system-wide low spark energy (often low voltage related)",
        "severity": "medium",
        "verification": ["Check battery voltage", "Test all coil outputs"],
        "repair": ["Fix root cause (charging system)", "Replace coils if needed"],
        "cost": "$200-800"
    },
    "all_plugs_fouled": {
        "description": "All plugs fouled - often indicates rich condition or oil consumption",
        "severity": "medium",
        "verification": ["Remove all plugs, inspect", "Check for oil consumption"],
        "repair": ["Replace spark plugs", "Address root cause"],
        "cost": "$100-300"
    },
    "low_battery_voltage": {
        "description": "Low battery voltage affecting ignition - weak spark all cylinders",
        "severity": "medium",
        "verification": ["Check battery voltage", "Test charging system"],
        "repair": ["Charge/replace battery", "Fix charging system"],
        "cost": "$100-500"
    },
    
    # Charging
    "alternator_failed": {
        "description": "Alternator not charging - running on battery only",
        "severity": "critical",
        "verification": ["Check voltage at battery (should be 13.5-14.5V running)", "Belt inspection"],
        "repair": ["Replace alternator or repair belt"],
        "cost": "$300-700"
    },
    "alternator_overcharging": {
        "description": "Alternator overcharging - voltage regulator failed",
        "severity": "high",
        "verification": ["Check voltage >15V at battery", "Battery may be gassing"],
        "repair": ["Replace alternator/regulator"],
        "cost": "$300-700"
    },
    "battery_weak": {
        "description": "Weak battery - reduced capacity and high internal resistance",
        "severity": "medium",
        "verification": ["Load test battery", "Check CCA rating"],
        "repair": ["Replace battery"],
        "cost": "$100-300"
    },
    "battery_dead_cell": {
        "description": "Battery has dead cell - ~2V lower than normal",
        "severity": "high",
        "verification": ["Check resting voltage (~10.5V vs 12.6V)", "Load test"],
        "repair": ["Replace battery"],
        "cost": "$100-300"
    },
    "belt_slipping": {
        "description": "Drive belt slipping - intermittent charging",
        "severity": "medium",
        "verification": ["Inspect belt condition", "Listen for squealing"],
        "repair": ["Replace/adjust belt"],
        "cost": "$50-200"
    },
    "high_resistance_connection": {
        "description": "High resistance in battery/ground connections",
        "severity": "medium",
        "verification": ["Voltage drop test on cables", "Inspect connections"],
        "repair": ["Clean and tighten connections"],
        "cost": "$0-100"
    },
}


# =============================================================================
# DIAGNOSTIC ENGINE
# =============================================================================

class DiagnosticEngine:
    """
    Unified diagnostic engine using physics-based reasoning.
    
    For each potential fault:
    1. Inject fault into appropriate physics model
    2. Simulate system behavior
    3. Compare predicted symptoms with observed symptoms
    4. Score match quality
    5. Rank candidates by confidence
    """
    
    def __init__(self):
        # Initialize all physics models
        self.cooling_model = CoolingSystemModel()
        self.fuel_model = FuelSystemModel()
        self.ignition_model = IgnitionSystemModel()
        self.charging_model = ChargingSystemModel()
        
        # Default operating conditions for simulation
        self.default_conditions = {
            "rpm": 2000,
            "load_fraction": 0.4,
            "ambient_temp_c": 25,
            "vehicle_speed_kph": 50,
        }
    
    def diagnose(
        self,
        dtcs: List[str] = None,
        pids: Dict[str, float] = None,
        complaints: List[str] = None,
        operating_conditions: Dict[str, float] = None
    ) -> DiagnosticResult:
        """
        Perform comprehensive diagnosis.
        
        Args:
            dtcs: List of DTC codes (e.g., ["P0171", "P0128"])
            pids: Dict of PID values (e.g., {"coolant_temp": 110, "stft_b1": 15})
            complaints: List of customer complaints (e.g., ["overheating", "rough_idle"])
            operating_conditions: Override default conditions
            
        Returns:
            DiagnosticResult with ranked candidates
        """
        dtcs = dtcs or []
        pids = pids or {}
        complaints = complaints or []
        conditions = {**self.default_conditions, **(operating_conditions or {})}
        
        # Parse input symptoms
        symptoms = self._parse_symptoms(dtcs, pids, complaints)
        
        # Determine which systems to analyze
        systems = self._identify_affected_systems(symptoms)
        
        # Collect all candidate faults
        candidates = []
        
        for system in systems:
            system_candidates = self._analyze_system(system, symptoms, conditions)
            candidates.extend(system_candidates)
        
        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        
        # Build result
        result = DiagnosticResult(
            candidates=candidates,
            input_symptoms=symptoms,
            systems_analyzed=systems,
        )
        
        if candidates:
            result.most_likely_cause = candidates[0]
            result.confidence_in_diagnosis = candidates[0].confidence
            result.next_steps = candidates[0].verification_tests[:3]
        
        return result
    
    def _parse_symptoms(
        self,
        dtcs: List[str],
        pids: Dict[str, float],
        complaints: List[str]
    ) -> List[Symptom]:
        """Convert raw inputs to Symptom objects."""
        symptoms = []
        
        for dtc in dtcs:
            desc = DTC_FAULT_MAP.get(dtc, {}).get("desc", "Unknown DTC")
            symptoms.append(Symptom(type="dtc", code=dtc, description=desc))
        
        for pid_name, value in pids.items():
            symptoms.append(Symptom(type="pid", code=pid_name, value=value))
        
        for complaint in complaints:
            symptoms.append(Symptom(type="complaint", code=complaint.lower().replace(" ", "_")))
        
        return symptoms
    
    def _identify_affected_systems(self, symptoms: List[Symptom]) -> List[SystemType]:
        """Determine which systems are potentially affected."""
        systems = set()
        
        for symptom in symptoms:
            if symptom.type == "dtc" and symptom.code in DTC_FAULT_MAP:
                systems.add(DTC_FAULT_MAP[symptom.code]["system"])
            elif symptom.type == "complaint" and symptom.code in COMPLAINT_FAULT_MAP:
                systems.add(COMPLAINT_FAULT_MAP[symptom.code]["system"])
            elif symptom.type == "pid":
                # Map PIDs to systems
                if "coolant" in symptom.code or "ect" in symptom.code:
                    systems.add(SystemType.COOLING)
                elif "fuel" in symptom.code or "stft" in symptom.code or "ltft" in symptom.code or "maf" in symptom.code:
                    systems.add(SystemType.FUEL)
                elif "misfire" in symptom.code or "timing" in symptom.code:
                    systems.add(SystemType.IGNITION)
                elif "voltage" in symptom.code or "battery" in symptom.code:
                    systems.add(SystemType.CHARGING)
        
        return list(systems) if systems else list(SystemType)
    
    def _analyze_system(
        self,
        system: SystemType,
        symptoms: List[Symptom],
        conditions: Dict[str, float]
    ) -> List[DiagnosticCandidate]:
        """Analyze a single system for potential faults."""
        candidates = []
        
        # Get potential faults for this system
        faults = self._get_system_faults(system, symptoms)
        
        for fault_id, cylinder in faults:
            candidate = self._evaluate_fault(system, fault_id, cylinder, symptoms, conditions)
            if candidate.confidence > 0.1:  # Filter very low confidence
                candidates.append(candidate)
        
        return candidates
    
    def _get_system_faults(
        self,
        system: SystemType,
        symptoms: List[Symptom]
    ) -> List[Tuple[str, Optional[int]]]:
        """Get list of (fault_id, cylinder) tuples to evaluate."""
        faults = set()
        
        for symptom in symptoms:
            if symptom.type == "dtc" and symptom.code in DTC_FAULT_MAP:
                mapping = DTC_FAULT_MAP[symptom.code]
                if mapping["system"] == system:
                    cylinder = mapping.get("cylinder")
                    for fault in mapping["faults"]:
                        faults.add((fault, cylinder))
            
            elif symptom.type == "complaint" and symptom.code in COMPLAINT_FAULT_MAP:
                mapping = COMPLAINT_FAULT_MAP[symptom.code]
                if mapping["system"] == system:
                    for fault in mapping["faults"]:
                        faults.add((fault, None))
        
        return list(faults)
    
    def _evaluate_fault(
        self,
        system: SystemType,
        fault_id: str,
        cylinder: Optional[int],
        symptoms: List[Symptom],
        conditions: Dict[str, float]
    ) -> DiagnosticCandidate:
        """Evaluate how well a fault explains the symptoms."""
        
        # Get fault details
        details = FAULT_DETAILS.get(fault_id, {})
        
        # Reset and inject fault into appropriate model
        # We recreate models to ensure clean state
        if system == SystemType.COOLING:
            self.cooling_model = CoolingSystemModel()  # Fresh model
            try:
                self.cooling_model.inject_fault(fault_id)
            except:
                pass
            state = self.cooling_model.simulate_steady_state(
                rpm=conditions["rpm"],
                load_fraction=conditions["load_fraction"],
                ambient_temp_c=conditions["ambient_temp_c"],
                vehicle_speed_kph=conditions["vehicle_speed_kph"]
            )
            predicted_state = state
            
        elif system == SystemType.FUEL:
            self.fuel_model = FuelSystemModel()  # Reset
            try:
                self.fuel_model.inject_fault(fault_id, cylinder=cylinder or 0)
            except:
                pass
            state = self.fuel_model.simulate_steady_state(
                rpm=conditions["rpm"],
                load_fraction=conditions["load_fraction"],
                ambient_temp_c=conditions["ambient_temp_c"]
            )
            predicted_state = state
            
        elif system == SystemType.IGNITION:
            self.ignition_model.reset()
            try:
                self.ignition_model.inject_fault(fault_id, cylinder=cylinder or 0)
            except:
                pass
            state = self.ignition_model.simulate_cycle(
                rpm=conditions["rpm"],
                load_fraction=conditions["load_fraction"]
            )
            predicted_state = state
            
        elif system == SystemType.CHARGING:
            self.charging_model.reset()
            try:
                self.charging_model.inject_fault(fault_id)
            except:
                pass
            state = self.charging_model.simulate_steady_state(
                engine_rpm=conditions["rpm"]
            )
            predicted_state = state
        else:
            predicted_state = None
        
        # Score symptom match
        explained = []
        not_explained = []
        
        for symptom in symptoms:
            if self._symptom_matches_fault(symptom, fault_id, system, predicted_state):
                explained.append(symptom.code)
            else:
                not_explained.append(symptom.code)
        
        # Calculate confidence
        if not symptoms:
            confidence = 0.5
        else:
            match_ratio = len(explained) / len(symptoms)
            confidence = match_ratio * 0.8 + 0.2  # Base confidence of 0.2
        
        return DiagnosticCandidate(
            fault_id=fault_id,
            system=system,
            description=details.get("description", f"Fault: {fault_id}"),
            confidence=confidence,
            symptoms_explained=explained,
            symptoms_not_explained=not_explained,
            predicted_state=predicted_state,
            verification_tests=details.get("verification", []),
            repair_actions=details.get("repair", []),
            severity=details.get("severity", "medium"),
            estimated_repair_cost=details.get("cost", "Unknown")
        )
    
    def _symptom_matches_fault(
        self,
        symptom: Symptom,
        fault_id: str,
        system: SystemType,
        state: Any
    ) -> bool:
        """Check if a symptom is consistent with a fault."""
        
        # DTC matching
        if symptom.type == "dtc":
            mapping = DTC_FAULT_MAP.get(symptom.code, {})
            if fault_id in mapping.get("faults", []):
                return True
        
        # Complaint matching  
        if symptom.type == "complaint":
            mapping = COMPLAINT_FAULT_MAP.get(symptom.code, {})
            if fault_id in mapping.get("faults", []):
                return True
        
        # PID matching with predicted state
        if symptom.type == "pid" and state:
            return self._pid_matches_state(symptom, state, system)
        
        return False
    
    def _pid_matches_state(self, symptom: Symptom, state: Any, system: SystemType) -> bool:
        """Check if PID value matches predicted state."""
        
        if system == SystemType.COOLING and isinstance(state, CoolingSystemState):
            if "coolant_temp" in symptom.code and symptom.value:
                return abs(state.coolant_temp_c - symptom.value) < 15
                
        elif system == SystemType.FUEL and isinstance(state, FuelSystemState):
            if "stft" in symptom.code and symptom.value:
                return (state.short_term_fuel_trim > 10) == (symptom.value > 10)
            if "ltft" in symptom.code and symptom.value:
                return (state.long_term_fuel_trim > 10) == (symptom.value > 10)
                
        elif system == SystemType.CHARGING and isinstance(state, ChargingSystemState):
            if "voltage" in symptom.code and symptom.value:
                return abs(state.system_voltage - symptom.value) < 1.0
        
        return True  # Default to match if we can't verify


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quick_diagnose(
    dtcs: List[str] = None,
    complaints: List[str] = None
) -> DiagnosticResult:
    """Quick diagnosis from DTCs and complaints."""
    engine = DiagnosticEngine()
    return engine.diagnose(dtcs=dtcs, complaints=complaints)


def print_diagnosis(result: DiagnosticResult) -> None:
    """Pretty-print diagnostic result."""
    print("\n" + "=" * 70)
    print("DIAGNOSTIC RESULTS")
    print("=" * 70)
    
    print(f"\nInput symptoms: {[s.code for s in result.input_symptoms]}")
    print(f"Systems analyzed: {[s.value for s in result.systems_analyzed]}")
    
    print(f"\n{'─' * 70}")
    print("TOP DIAGNOSTIC CANDIDATES:")
    print(f"{'─' * 70}")
    
    for i, candidate in enumerate(result.candidates[:5], 1):
        print(f"\n{i}. {candidate.fault_id} ({candidate.system.value})")
        print(f"   Confidence: {candidate.confidence:.0%}")
        print(f"   Description: {candidate.description}")
        print(f"   Severity: {candidate.severity.upper()}")
        print(f"   Symptoms explained: {candidate.symptoms_explained}")
        if candidate.verification_tests:
            print(f"   Verify: {candidate.verification_tests[0]}")
        if candidate.repair_actions:
            print(f"   Repair: {candidate.repair_actions[0]}")
        print(f"   Est. cost: {candidate.estimated_repair_cost}")
    
    if result.next_steps:
        print(f"\n{'─' * 70}")
        print("RECOMMENDED NEXT STEPS:")
        for i, step in enumerate(result.next_steps, 1):
            print(f"  {i}. {step}")
